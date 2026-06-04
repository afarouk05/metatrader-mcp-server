from abc import ABC, abstractmethod
import pandas as pd
from .signal import Signal


class Strategy(ABC):
    """Base class for all trading strategies."""

    @abstractmethod
    def required_candles(self) -> int:
        """Minimum number of candles needed to compute a signal."""
        ...

    @abstractmethod
    def generate_signal(self, candles: pd.DataFrame) -> Signal:
        """Generate a trading signal from OHLCV candle data.

        Args:
            candles: DataFrame with columns open, high, low, close, tick_volume

        Returns:
            Signal.BUY, Signal.SELL, or Signal.HOLD
        """
        ...
