# Auto Trader

A configurable strategy-loop trader built on top of the `metatrader_client`
library. It fetches candles, computes a signal, applies risk checks, and
places/manages orders against a live MT5 terminal.

The strategy logic and the backtester are **pure pandas** — they run and are
tested anywhere. Only the live engine requires the Windows-only MetaTrader5
SDK and a running terminal.

## Layout

```
auto_trader/
├── strategies/
│   ├── signal.py        # Signal enum (BUY/SELL/HOLD)
│   ├── base.py          # Strategy ABC
│   ├── ma_crossover.py  # EMA fast/slow crossover
│   ├── rsi.py           # RSI mean-reversion
│   └── __init__.py      # get_strategy() factory
├── config.py            # AutoTraderConfig dataclass
├── risk_manager.py      # Margin + position-count gates
├── engine.py            # Live trading loop (needs MT5)
├── backtest.py          # Offline backtester (no MT5)
└── cli.py               # `metatrader-auto-trader` entry point
```

## Local testing (no MT5 required)

```bash
# Unit + engine + backtest tests (client is mocked / pure pandas)
pytest tests/auto_trader/

# Run a backtest on synthetic data
PYTHONPATH=src python3 examples/backtest_demo.py
```

To backtest **real** data, export candles from MT5 to CSV (needs a `close`
column; `high`/`low` improve SL/TP fill accuracy) and feed them to
`run_backtest`:

```python
import pandas as pd
from auto_trader.strategies import get_strategy
from auto_trader.backtest import run_backtest

candles = pd.read_csv("EURUSD_M15.csv")
strat = get_strategy("ma_crossover", {"fast_period": 9, "slow_period": 21})
result = run_backtest(candles, strat, stop_loss_pips=30, take_profit_pips=60)
print(result.summary())
```

## Live trading (Windows + MT5 terminal)

```bash
pip install -e .

# Always validate signals first with --dry-run (no orders placed)
metatrader-auto-trader --login 12345 --password secret --server Broker-Demo --dry-run

# Go live on a demo account
metatrader-auto-trader --login 12345 --password secret --server Broker-Demo \
  --strategy rsi --symbol EURUSD --symbol GBPUSD \
  --volume 0.01 --stop-loss-pips 25 --take-profit-pips 50
```

Credentials and most options can also come from environment variables
(`LOGIN`, `PASSWORD`, `SERVER`, `STRATEGY`, `VOLUME`, `SL_PIPS`, `TP_PIPS`, …).

## Risk controls

`risk_manager.py` blocks a new position when any of these fail:
- account-level trading is disabled
- margin level is below `--min-margin-level` (default 200%)
- the per-symbol position cap is reached (`--max-positions`)
- the total position cap is reached (`--max-total`)

## Safety

This places real orders. Test thoroughly on a **demo account** with
`--dry-run` first. Backtest results on synthetic data are not indicative of
live performance.
