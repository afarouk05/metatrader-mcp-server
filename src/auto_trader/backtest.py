"""Offline backtester for auto_trader strategies.

Runs a strategy candle-by-candle over a historical OHLCV DataFrame and
simulates a single-position trading account with fixed SL/TP. No MT5
terminal required — ideal for local validation.

The DataFrame must have at least a `close` column; `high`/`low` are used
for intrabar SL/TP fills when present (otherwise `close` is used).
"""
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from .strategies.base import Strategy
from .strategies.signal import Signal


@dataclass
class Trade:
    direction: str          # "BUY" or "SELL"
    entry_index: int
    entry_price: float
    exit_index: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""    # "sl", "tp", "signal", "end"
    pips: float = 0.0


@dataclass
class BacktestResult:
    trades: List[Trade] = field(default_factory=list)
    pip_size: float = 0.0001

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.pips > 0)

    @property
    def losses(self) -> int:
        return sum(1 for t in self.trades if t.pips <= 0)

    @property
    def win_rate(self) -> float:
        return (self.wins / self.total_trades * 100) if self.trades else 0.0

    @property
    def net_pips(self) -> float:
        return sum(t.pips for t in self.trades)

    def summary(self) -> str:
        if not self.trades:
            return "No trades were generated."
        avg = self.net_pips / self.total_trades
        gross_win = sum(t.pips for t in self.trades if t.pips > 0)
        gross_loss = abs(sum(t.pips for t in self.trades if t.pips <= 0))
        pf = (gross_win / gross_loss) if gross_loss else float("inf")
        return (
            f"Trades: {self.total_trades} | Wins: {self.wins} | Losses: {self.losses} | "
            f"Win rate: {self.win_rate:.1f}%\n"
            f"Net: {self.net_pips:+.1f} pips | Avg/trade: {avg:+.1f} pips | "
            f"Profit factor: {pf:.2f}"
        )


def run_backtest(
    candles: pd.DataFrame,
    strategy: Strategy,
    *,
    stop_loss_pips: float = 30.0,
    take_profit_pips: float = 60.0,
    pip_size: float = 0.0001,
) -> BacktestResult:
    """Simulate a strategy over historical candles.

    One position at a time. On an opposing signal the open trade is closed
    at the current close and a new one opened. SL/TP are checked intrabar
    using high/low (or close as a fallback).
    """
    candles = candles.reset_index(drop=True)
    has_hl = "high" in candles.columns and "low" in candles.columns
    result = BacktestResult(pip_size=pip_size)
    open_trade: Optional[Trade] = None
    warmup = strategy.required_candles()

    sl_dist = stop_loss_pips * pip_size
    tp_dist = take_profit_pips * pip_size

    def close_trade(trade: Trade, idx: int, price: float, reason: str) -> None:
        trade.exit_index = idx
        trade.exit_price = price
        trade.exit_reason = reason
        raw = (price - trade.entry_price) if trade.direction == "BUY" else (trade.entry_price - price)
        trade.pips = raw / pip_size
        result.trades.append(trade)

    for i in range(len(candles)):
        row = candles.iloc[i]
        close = float(row["close"])
        high = float(row["high"]) if has_hl else close
        low = float(row["low"]) if has_hl else close

        # 1. Check SL/TP on any open trade first (intrabar).
        if open_trade is not None:
            if open_trade.direction == "BUY":
                sl_price = open_trade.entry_price - sl_dist
                tp_price = open_trade.entry_price + tp_dist
                if low <= sl_price:
                    close_trade(open_trade, i, sl_price, "sl"); open_trade = None
                elif high >= tp_price:
                    close_trade(open_trade, i, tp_price, "tp"); open_trade = None
            else:  # SELL
                sl_price = open_trade.entry_price + sl_dist
                tp_price = open_trade.entry_price - tp_dist
                if high >= sl_price:
                    close_trade(open_trade, i, sl_price, "sl"); open_trade = None
                elif low <= tp_price:
                    close_trade(open_trade, i, tp_price, "tp"); open_trade = None

        # 2. Need enough history to compute a signal.
        if i + 1 < warmup:
            continue

        signal = strategy.generate_signal(candles.iloc[: i + 1])
        if signal == Signal.HOLD:
            continue

        # 3. Reverse on opposing signal, then open if flat.
        if open_trade is not None:
            opposing = (
                (signal == Signal.BUY and open_trade.direction == "SELL") or
                (signal == Signal.SELL and open_trade.direction == "BUY")
            )
            if opposing:
                close_trade(open_trade, i, close, "signal"); open_trade = None

        if open_trade is None:
            open_trade = Trade(direction=signal.value, entry_index=i, entry_price=close)

    # Close any trade still open at the end of the series.
    if open_trade is not None:
        last = len(candles) - 1
        close_trade(open_trade, last, float(candles.iloc[last]["close"]), "end")

    return result
