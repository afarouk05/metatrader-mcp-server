"""Tests for auto_trader strategy logic.

These run anywhere (pure pandas) — no MetaTrader5 terminal required.
"""
import numpy as np
import pandas as pd
import pytest

from auto_trader.strategies import get_strategy
from auto_trader.strategies.signal import Signal
from auto_trader.strategies.ma_crossover import MACrossoverStrategy
from auto_trader.strategies.rsi import RSIStrategy


def make_df(close):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({
        "open": close,
        "high": close + 0.0005,
        "low": close - 0.0005,
        "close": close,
        "tick_volume": 100,
    })


# ── MA crossover ────────────────────────────────────────────────────────

def test_ma_buy_on_upward_cross():
    # Downtrend establishes fast < slow; series ends exactly as the rally
    # pushes the fast EMA up through the slow EMA.
    down = np.linspace(1.12, 1.10, 25)
    rally = np.linspace(1.10, 1.15, 6)[:3]
    df = make_df(np.concatenate([down, rally]))
    strat = MACrossoverStrategy(fast_period=5, slow_period=15)
    assert strat.generate_signal(df) == Signal.BUY


def test_ma_sell_on_downward_cross():
    up = np.linspace(1.10, 1.12, 25)
    drop = np.linspace(1.12, 1.07, 6)[:3]
    df = make_df(np.concatenate([up, drop]))
    strat = MACrossoverStrategy(fast_period=5, slow_period=15)
    assert strat.generate_signal(df) == Signal.SELL


def test_ma_hold_when_no_cross():
    flat = np.full(30, 1.10) + np.random.RandomState(0).normal(0, 1e-6, 30)
    df = make_df(flat)
    strat = MACrossoverStrategy(fast_period=5, slow_period=15)
    assert strat.generate_signal(df) == Signal.HOLD


def test_ma_rejects_bad_periods():
    with pytest.raises(ValueError):
        MACrossoverStrategy(fast_period=20, slow_period=10)


# ── RSI ─────────────────────────────────────────────────────────────────

def test_rsi_buy_exits_oversold():
    # Decline pushes RSI below 30; the rally's 2nd candle lifts it back above 30.
    decline = np.linspace(1.20, 1.17, 16)
    bounce = np.array([1.178, 1.186])
    df = make_df(np.concatenate([decline, bounce]))
    strat = RSIStrategy(period=14, oversold=30, overbought=70)
    assert strat.generate_signal(df) == Signal.BUY


def test_rsi_sell_exits_overbought():
    climb = np.linspace(1.10, 1.13, 16)
    pullback = np.array([1.122, 1.114])
    df = make_df(np.concatenate([climb, pullback]))
    strat = RSIStrategy(period=14, oversold=30, overbought=70)
    assert strat.generate_signal(df) == Signal.SELL


def test_rsi_hold_in_neutral_zone():
    flat = np.full(25, 1.10) + np.random.RandomState(1).normal(0, 1e-5, 25)
    df = make_df(flat)
    strat = RSIStrategy(period=14)
    assert strat.generate_signal(df) == Signal.HOLD


# ── Factory ─────────────────────────────────────────────────────────────

def test_get_strategy_returns_correct_type():
    assert isinstance(get_strategy("ma_crossover", {}), MACrossoverStrategy)
    assert isinstance(get_strategy("rsi", {}), RSIStrategy)


def test_get_strategy_unknown_raises():
    with pytest.raises(ValueError):
        get_strategy("does_not_exist", {})


def test_get_strategy_filters_unknown_params():
    # Extra params (e.g. from a shared config) should be ignored, not crash.
    strat = get_strategy("rsi", {"period": 7, "fast_period": 99})
    assert strat.period == 7
