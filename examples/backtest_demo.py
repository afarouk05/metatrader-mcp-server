"""Local backtest demo — no MetaTrader5 terminal required.

Generates synthetic random-walk price data and runs both strategies over it,
printing trade-by-trade results and a performance summary.

Run from the repo root:

    PYTHONPATH=src python3 examples/backtest_demo.py

To backtest real data, export candles from MT5 to CSV (with at least a
`close` column, ideally `high`/`low` too) and load them with pandas instead
of `generate_synthetic_candles`.
"""
import numpy as np
import pandas as pd

from auto_trader.strategies import get_strategy
from auto_trader.backtest import run_backtest


def generate_synthetic_candles(n=2000, start=1.1000, seed=42):
    """Random walk with mild trending bias — stands in for real OHLC data."""
    rng = np.random.RandomState(seed)
    # Blend small random steps with slow sine drift to create trends.
    drift = 0.0008 * np.sin(np.linspace(0, 12 * np.pi, n))
    steps = rng.normal(0, 0.0004, n) + drift
    close = start + np.cumsum(steps)
    # Build plausible high/low around each close.
    spread = np.abs(rng.normal(0, 0.0003, n))
    high = close + spread
    low = close - spread
    open_ = np.concatenate([[start], close[:-1]])
    return pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "tick_volume": rng.randint(50, 500, n),
    })


def main():
    candles = generate_synthetic_candles()
    print(f"Generated {len(candles)} synthetic candles "
          f"(range {candles['close'].min():.5f} – {candles['close'].max():.5f})\n")

    configs = [
        ("MA Crossover (9/21)", "ma_crossover", {"fast_period": 9, "slow_period": 21}),
        ("RSI (14, 30/70)", "rsi", {"period": 14, "oversold": 30, "overbought": 70}),
    ]

    for label, name, params in configs:
        strat = get_strategy(name, params)
        result = run_backtest(
            candles, strat,
            stop_loss_pips=30, take_profit_pips=60, pip_size=0.0001,
        )
        print("=" * 60)
        print(label)
        print("=" * 60)
        print(result.summary())
        if result.trades:
            print("\nFirst 5 trades:")
            print(f"  {'#':>3} {'dir':>4} {'entry':>9} {'exit':>9} {'reason':>7} {'pips':>8}")
            for i, t in enumerate(result.trades[:5], 1):
                print(f"  {i:>3} {t.direction:>4} {t.entry_price:>9.5f} "
                      f"{t.exit_price:>9.5f} {t.exit_reason:>7} {t.pips:>+8.1f}")
        print()


if __name__ == "__main__":
    main()
