"""MetaTrader 5 Auto Trader.

The `strategies` subpackage is pure-pandas and can be imported and tested
without the Windows-only MetaTrader5 SDK. The engine (which talks to a live
MT5 terminal) is imported lazily so strategy logic stays testable anywhere.
"""

__all__ = ["AutoTrader", "AutoTraderConfig", "get_strategy"]


def __getattr__(name):
    if name in ("AutoTrader",):
        from .engine import AutoTrader
        return AutoTrader
    if name in ("AutoTraderConfig",):
        from .config import AutoTraderConfig
        return AutoTraderConfig
    if name in ("get_strategy",):
        from .strategies import get_strategy
        return get_strategy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
