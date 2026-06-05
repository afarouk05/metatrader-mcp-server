"""Tests for the AutoTrader engine decision flow.

The MT5 client is fully mocked, so these run anywhere — they verify the
open/close/risk logic without a live terminal.
"""
import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# The engine imports `from metatrader_client import MT5Client` at module load.
# Stub that package so the import succeeds without the Windows-only SDK.
_stub = types.ModuleType("metatrader_client")
_stub.MT5Client = MagicMock
sys.modules.setdefault("metatrader_client", _stub)

from auto_trader.config import AutoTraderConfig
from auto_trader.engine import AutoTrader
from auto_trader.strategies.signal import Signal


class StubStrategy:
    def __init__(self, signal):
        self.signal = signal

    def required_candles(self):
        return 20

    def generate_signal(self, candles):
        return self.signal


def make_candles(n=30):
    close = np.linspace(1.10, 1.11, n)
    return pd.DataFrame({
        "open": close, "high": close + 0.0005,
        "low": close - 0.0005, "close": close, "tick_volume": 100,
    })


def build_trader(signal, *, positions=None, dry_run=False, margin_level=500.0,
                 trade_allowed=True, max_per_symbol=1, max_total=3):
    config = AutoTraderConfig(
        login=1, password="x", server="s",
        symbols=["EURUSD"], dry_run=dry_run,
        max_positions_per_symbol=max_per_symbol, max_total_positions=max_total,
    )
    trader = AutoTrader(config, StubStrategy(signal))

    client = MagicMock()
    client.market.get_candles_latest.return_value = make_candles()
    client.market.get_symbol_price.return_value = {"bid": 1.1000, "ask": 1.1001}
    client.market.get_symbol_info.return_value = {"point": 0.00001, "digits": 5}

    pos_df = positions if positions is not None else pd.DataFrame()
    client.order.get_positions_by_symbol.return_value = pos_df
    client.order.get_all_positions.return_value = pos_df
    client.order.place_market_order.return_value = {
        "error": False, "message": "ok", "data": MagicMock(order=12345),
    }
    client.order.modify_position.return_value = {"error": False, "message": "ok"}
    client.order.close_position.return_value = {"error": False, "message": "ok"}

    client.account.is_trade_allowed.return_value = trade_allowed
    client.account.get_margin_level.return_value = margin_level

    trader.client = client
    from auto_trader.risk_manager import RiskManager
    trader.risk = RiskManager(client, config)
    return trader, client


def positions_df(ptype):
    return pd.DataFrame([{"id": 999, "symbol": "EURUSD", "type": ptype, "volume": 0.01}])


# ── Opening ─────────────────────────────────────────────────────────────

def test_buy_signal_opens_buy_when_flat():
    trader, client = build_trader(Signal.BUY)
    trader._process("EURUSD")
    client.order.place_market_order.assert_called_once()
    assert client.order.place_market_order.call_args.kwargs["type"] == "BUY"


def test_sell_signal_opens_sell_when_flat():
    trader, client = build_trader(Signal.SELL)
    trader._process("EURUSD")
    assert client.order.place_market_order.call_args.kwargs["type"] == "SELL"


def test_hold_signal_does_nothing():
    trader, client = build_trader(Signal.HOLD)
    trader._process("EURUSD")
    client.order.place_market_order.assert_not_called()
    client.order.close_position.assert_not_called()


def test_sl_tp_applied_after_open():
    trader, client = build_trader(Signal.BUY)
    trader._process("EURUSD")
    client.order.modify_position.assert_called_once()
    kwargs = client.order.modify_position.call_args.kwargs
    # BUY: SL below entry, TP above entry
    assert kwargs["stop_loss"] < 1.1001 < kwargs["take_profit"]


# ── Position reversal ───────────────────────────────────────────────────

def test_buy_signal_closes_existing_sell():
    trader, client = build_trader(Signal.BUY, positions=positions_df("SELL"))
    trader._process("EURUSD")
    client.order.close_position.assert_called_once_with(999)


def test_buy_signal_keeps_existing_buy_and_does_not_stack():
    # Already long, max 1 per symbol → no new order, no close.
    trader, client = build_trader(Signal.BUY, positions=positions_df("BUY"))
    trader._process("EURUSD")
    client.order.close_position.assert_not_called()
    client.order.place_market_order.assert_not_called()


# ── Risk gates ──────────────────────────────────────────────────────────

def test_low_margin_blocks_open():
    trader, client = build_trader(Signal.BUY, margin_level=100.0)  # below default 200
    trader._process("EURUSD")
    client.order.place_market_order.assert_not_called()


def test_trade_not_allowed_blocks_open():
    trader, client = build_trader(Signal.BUY, trade_allowed=False)
    trader._process("EURUSD")
    client.order.place_market_order.assert_not_called()


# ── Dry run ─────────────────────────────────────────────────────────────

def test_dry_run_places_no_orders():
    trader, client = build_trader(Signal.BUY, dry_run=True)
    trader._process("EURUSD")
    client.order.place_market_order.assert_not_called()
