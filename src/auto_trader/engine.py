import logging
import time
from typing import Optional

from metatrader_client import MT5Client
from .config import AutoTraderConfig
from .risk_manager import RiskManager
from .strategies.base import Strategy
from .strategies.signal import Signal

logger = logging.getLogger(__name__)


class AutoTrader:
    """Runs a strategy in a loop against a live MT5 terminal."""

    def __init__(self, config: AutoTraderConfig, strategy: Strategy):
        self.config = config
        self.strategy = strategy
        self.client: Optional[MT5Client] = None
        self.risk: Optional[RiskManager] = None
        self._running = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Connect to MT5 and enter the trading loop (blocking)."""
        self._connect()
        self._running = True
        mode = "[DRY RUN] " if self.config.dry_run else ""
        logger.info(
            "%sAutoTrader started | strategy=%s symbols=%s timeframe=%s poll=%ds",
            mode, self.config.strategy, self.config.symbols,
            self.config.timeframe, self.config.poll_interval,
        )
        try:
            while self._running:
                self._tick()
                time.sleep(self.config.poll_interval)
        except KeyboardInterrupt:
            logger.info("Shutdown requested by user")
        finally:
            self.stop()

    def stop(self) -> None:
        self._running = False
        if self.client:
            self.client.disconnect()
            logger.info("Disconnected from MT5")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        mt5_config: dict = {
            "login": self.config.login,
            "password": self.config.password,
            "server": self.config.server,
            "debug": self.config.debug,
        }
        if self.config.path:
            mt5_config["path"] = self.config.path

        self.client = MT5Client(mt5_config)
        if not self.client.connect():
            raise RuntimeError("Failed to connect to MT5 terminal")

        self.risk = RiskManager(self.client, self.config)
        info = self.client.account.get_account_info()
        logger.info(
            "Connected | account=%s balance=%.2f %s type=%s",
            info.get("login"), info.get("balance", 0),
            info.get("currency", ""), info.get("trade_mode", ""),
        )

    def _tick(self) -> None:
        try:
            for symbol in self.config.symbols:
                self._process(symbol)
        except Exception as exc:
            logger.error("Tick error: %s", exc, exc_info=self.config.debug)

    def _process(self, symbol: str) -> None:
        needed = self.strategy.required_candles() + 5
        candles = self.client.market.get_candles_latest(symbol, self.config.timeframe, needed)

        if candles is None or candles.empty or len(candles) < self.strategy.required_candles():
            logger.warning("%s: insufficient candle data (%d candles)", symbol, len(candles) if candles is not None else 0)
            return

        signal = self.strategy.generate_signal(candles)
        positions = self.client.order.get_positions_by_symbol(symbol)
        n_open = len(positions) if not positions.empty else 0

        logger.info("%s | signal=%-4s | open_positions=%d", symbol, signal.value, n_open)

        if signal == Signal.HOLD:
            return

        # Close any positions running against the new signal
        if not positions.empty:
            for _, pos in positions.iterrows():
                pos_type = str(pos.get("type", "")).upper()
                if (signal == Signal.BUY and "SELL" in pos_type) or \
                   (signal == Signal.SELL and "BUY" in pos_type):
                    self._close(symbol, int(pos["id"]))

        # Open new position if risk checks pass
        allowed, reason = self.risk.can_open(symbol)
        if not allowed:
            logger.info("%s: skipping %s — %s", symbol, signal.value, reason)
            return

        self._open(symbol, signal)

    def _open(self, symbol: str, signal: Signal) -> None:
        price_data = self.client.market.get_symbol_price(symbol)
        if not price_data:
            logger.error("%s: could not get current price", symbol)
            return

        entry = price_data.get("ask") if signal == Signal.BUY else price_data.get("bid")

        # Calculate SL/TP distances in price units
        try:
            info = self.client.market.get_symbol_info(symbol)
            point = info.get("point", 0.00001)
            digits = info.get("digits", 5)
            # For 5- or 3-digit brokers one pip = 10 points; for 4- or 2-digit it equals 1 point
            pip = 10 * point if digits % 2 == 1 else point
        except Exception:
            pip = 0.0001  # safe default for most FX

        sl_dist = self.config.stop_loss_pips * pip
        tp_dist = self.config.take_profit_pips * pip

        if signal == Signal.BUY:
            sl = round(entry - sl_dist, 5)
            tp = round(entry + tp_dist, 5)
        else:
            sl = round(entry + sl_dist, 5)
            tp = round(entry - tp_dist, 5)

        if self.config.dry_run:
            logger.info("[DRY RUN] %s %s %.2f lots @ %.5f  SL=%.5f  TP=%.5f",
                        signal.value, symbol, self.config.volume, entry, sl, tp)
            return

        result = self.client.order.place_market_order(
            type=signal.value,
            symbol=symbol,
            volume=self.config.volume,
        )

        if result.get("error"):
            logger.error("%s: order failed — %s", symbol, result.get("message"))
            return

        data = result.get("data")
        ticket = getattr(data, "order", None)
        logger.info("%s: %s order placed | ticket=%s volume=%.2f @ %.5f",
                    symbol, signal.value, ticket, self.config.volume, entry)

        # Apply SL/TP via modify (the wrapper doesn't forward them on placement)
        if ticket and (sl or tp):
            mod = self.client.order.modify_position(ticket, stop_loss=sl, take_profit=tp)
            if mod.get("error"):
                logger.warning("%s: SL/TP modify failed — %s", symbol, mod.get("message"))

    def _close(self, symbol: str, ticket: int) -> None:
        if self.config.dry_run:
            logger.info("[DRY RUN] close position #%d for %s", ticket, symbol)
            return
        result = self.client.order.close_position(ticket)
        if result.get("error"):
            logger.error("%s: close position #%d failed — %s", symbol, ticket, result.get("message"))
        else:
            logger.info("%s: closed position #%d", symbol, ticket)
