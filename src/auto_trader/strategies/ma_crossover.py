import pandas as pd
from .base import Strategy
from .signal import Signal


class MACrossoverStrategy(Strategy):
    """EMA crossover: fast crosses above slow → BUY, crosses below → SELL."""

    def __init__(self, fast_period: int = 9, slow_period: int = 21):
        if fast_period >= slow_period:
            raise ValueError("fast_period must be less than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def required_candles(self) -> int:
        return self.slow_period + 5

    def generate_signal(self, candles: pd.DataFrame) -> Signal:
        close = candles["close"]
        fast = close.ewm(span=self.fast_period, adjust=False).mean()
        slow = close.ewm(span=self.slow_period, adjust=False).mean()

        # Use last two candles to detect a crossover event
        prev_diff = fast.iloc[-2] - slow.iloc[-2]
        curr_diff = fast.iloc[-1] - slow.iloc[-1]

        if prev_diff <= 0 and curr_diff > 0:
            return Signal.BUY
        if prev_diff >= 0 and curr_diff < 0:
            return Signal.SELL
        return Signal.HOLD
