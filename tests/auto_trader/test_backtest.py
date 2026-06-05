"""Tests for the offline backtester P&L mechanics."""
import numpy as np
import pandas as pd

from auto_trader.backtest import run_backtest, Trade, BacktestResult
from auto_trader.strategies.signal import Signal


class AlwaysSignal:
    """Emits a fixed signal once warmup has passed — for deterministic fills."""
    def __init__(self, signal, warmup=2):
        self._signal = signal
        self._warmup = warmup

    def required_candles(self):
        return self._warmup

    def generate_signal(self, candles):
        return self._signal


def df_from_close(close, hl_spread=0.0):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({
        "open": close,
        "high": close + hl_spread,
        "low": close - hl_spread,
        "close": close,
        "tick_volume": 100,
    })


def test_tp_hit_logs_positive_pips():
    # BUY at 1.1000, TP 20 pips away → price rises to hit it.
    close = [1.1000, 1.1000, 1.1010, 1.1025]
    res = run_backtest(
        df_from_close(close), AlwaysSignal(Signal.BUY),
        stop_loss_pips=50, take_profit_pips=20, pip_size=0.0001,
    )
    assert res.total_trades >= 1
    first = res.trades[0]
    assert first.direction == "BUY"
    assert first.exit_reason == "tp"
    assert round(first.pips, 1) == 20.0


def test_sl_hit_logs_negative_pips():
    close = [1.1000, 1.1000, 1.0995, 1.0980]
    res = run_backtest(
        df_from_close(close), AlwaysSignal(Signal.BUY),
        stop_loss_pips=15, take_profit_pips=100, pip_size=0.0001,
    )
    first = res.trades[0]
    assert first.exit_reason == "sl"
    assert round(first.pips, 1) == -15.0


def test_sell_tp_direction():
    # SELL at 1.1000, profit when price falls.
    close = [1.1000, 1.1000, 1.0990, 1.0975]
    res = run_backtest(
        df_from_close(close), AlwaysSignal(Signal.SELL),
        stop_loss_pips=50, take_profit_pips=20, pip_size=0.0001,
    )
    first = res.trades[0]
    assert first.direction == "SELL"
    assert first.exit_reason == "tp"
    assert round(first.pips, 1) == 20.0


def test_open_trade_closed_at_series_end():
    # Gentle uptrend that never reaches SL or TP → closed at "end".
    close = np.linspace(1.1000, 1.1005, 10)
    res = run_backtest(
        df_from_close(close), AlwaysSignal(Signal.BUY),
        stop_loss_pips=100, take_profit_pips=100, pip_size=0.0001,
    )
    assert res.total_trades == 1
    assert res.trades[0].exit_reason == "end"


def test_no_signal_no_trades():
    close = np.linspace(1.1000, 1.1050, 30)
    res = run_backtest(
        df_from_close(close), AlwaysSignal(Signal.HOLD),
        pip_size=0.0001,
    )
    assert res.total_trades == 0
    assert "No trades" in res.summary()


def test_result_aggregates():
    res = BacktestResult(pip_size=0.0001)
    res.trades = [
        Trade("BUY", 0, 1.10, 1, 1.106, "tp", 60),
        Trade("BUY", 2, 1.10, 3, 1.097, "sl", -30),
        Trade("SELL", 4, 1.10, 5, 1.094, "tp", 60),
    ]
    assert res.total_trades == 3
    assert res.wins == 2
    assert res.losses == 1
    assert round(res.win_rate, 1) == 66.7
    assert round(res.net_pips, 1) == 90.0
