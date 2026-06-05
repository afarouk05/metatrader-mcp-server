"""Tests for the auto_trader CLI wiring.

The MT5 client is stubbed and AutoTrader.start is intercepted, so these
verify that command-line flags build the intended config without ever
connecting to a terminal.
"""
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# Stub the Windows-only client before importing the CLI (engine imports it).
_stub = types.ModuleType("metatrader_client")
_stub.MT5Client = MagicMock
sys.modules.setdefault("metatrader_client", _stub)

pytest.importorskip("click")
from click.testing import CliRunner

from auto_trader import cli as cli_mod


def invoke(args):
    """Run the CLI with start() intercepted; return (result, config, strategy_name)."""
    captured = {}

    def fake_start(self):
        captured["config"] = self.config
        captured["strategy"] = type(self.strategy).__name__

    with patch.object(cli_mod.AutoTrader, "start", fake_start):
        result = CliRunner().invoke(cli_mod.main, args)
    return result, captured.get("config"), captured.get("strategy")


BASE = ["--login", "12345", "--password", "secret", "--server", "Broker-Demo"]


def test_dry_run_rsi_multi_symbol():
    result, cfg, strat = invoke(BASE + [
        "--strategy", "rsi", "--symbol", "EURUSD", "--symbol", "GBPUSD",
        "--timeframe", "M5", "--volume", "0.01",
        "--stop-loss-pips", "25", "--take-profit-pips", "50",
        "--poll-interval", "30", "--dry-run",
    ])
    assert result.exit_code == 0
    assert strat == "RSIStrategy"
    assert cfg.dry_run is True
    assert cfg.symbols == ["EURUSD", "GBPUSD"]
    assert cfg.timeframe == "M5"
    assert cfg.stop_loss_pips == 25.0
    assert cfg.take_profit_pips == 50.0
    assert cfg.poll_interval == 30
    assert cfg.strategy_params == {"period": 14, "oversold": 30.0, "overbought": 70.0}


def test_defaults_ma_crossover_single_symbol():
    result, cfg, strat = invoke(BASE)
    assert result.exit_code == 0
    assert strat == "MACrossoverStrategy"
    assert cfg.dry_run is False
    assert cfg.symbols == ["EURUSD"]
    assert cfg.timeframe == "M15"
    assert cfg.strategy_params == {"fast_period": 9, "slow_period": 21}


def test_missing_credentials_errors():
    result, _, _ = invoke(["--strategy", "rsi"])
    assert result.exit_code != 0


def test_invalid_strategy_rejected():
    result, _, _ = invoke(BASE + ["--strategy", "does_not_exist"])
    assert result.exit_code != 0
