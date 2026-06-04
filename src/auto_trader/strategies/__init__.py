from .signal import Signal
from .base import Strategy
from .ma_crossover import MACrossoverStrategy
from .rsi import RSIStrategy


def get_strategy(name: str, params: dict) -> Strategy:
    """Instantiate a strategy by name with the given parameters."""
    if name == "ma_crossover":
        allowed = {"fast_period", "slow_period"}
        return MACrossoverStrategy(**{k: v for k, v in params.items() if k in allowed})
    if name == "rsi":
        allowed = {"period", "oversold", "overbought"}
        return RSIStrategy(**{k: v for k, v in params.items() if k in allowed})
    raise ValueError(f"Unknown strategy '{name}'. Choose from: ma_crossover, rsi")


__all__ = ["Signal", "Strategy", "MACrossoverStrategy", "RSIStrategy", "get_strategy"]
