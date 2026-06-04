import pandas as pd
from .base import Strategy
from .signal import Signal


class RSIStrategy(Strategy):
    """RSI mean-reversion: BUY when RSI recovers from oversold, SELL when it falls from overbought."""

    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def required_candles(self) -> int:
        return self.period + 5

    def generate_signal(self, candles: pd.DataFrame) -> Signal:
        close = candles["close"]
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)

        avg_gain = gain.ewm(com=self.period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=self.period - 1, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, float("inf"))
        rsi = 100 - (100 / (1 + rs))

        prev_rsi = rsi.iloc[-2]
        curr_rsi = rsi.iloc[-1]

        # BUY when RSI exits oversold territory (crosses back above oversold threshold)
        if prev_rsi < self.oversold and curr_rsi >= self.oversold:
            return Signal.BUY
        # SELL when RSI exits overbought territory (crosses back below overbought threshold)
        if prev_rsi > self.overbought and curr_rsi <= self.overbought:
            return Signal.SELL
        return Signal.HOLD
