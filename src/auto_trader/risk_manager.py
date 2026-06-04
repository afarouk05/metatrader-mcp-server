import logging
from typing import Tuple

from metatrader_client import MT5Client
from .config import AutoTraderConfig

logger = logging.getLogger(__name__)


class RiskManager:
    """Gate-checks before opening a new position."""

    def __init__(self, client: MT5Client, config: AutoTraderConfig):
        self.client = client
        self.config = config

    def can_open(self, symbol: str) -> Tuple[bool, str]:
        """Return (True, 'OK') or (False, reason) for a new position on symbol."""
        if not self.client.account.is_trade_allowed():
            return False, "trading not allowed on this account"

        if self.config.min_margin_level > 0:
            margin_level = self.client.account.get_margin_level()
            if margin_level > 0 and margin_level < self.config.min_margin_level:
                return False, f"margin level {margin_level:.1f}% < minimum {self.config.min_margin_level}%"

        positions = self.client.order.get_positions_by_symbol(symbol)
        if not positions.empty and len(positions) >= self.config.max_positions_per_symbol:
            return False, f"already at max {self.config.max_positions_per_symbol} position(s) for {symbol}"

        all_positions = self.client.order.get_all_positions()
        if not all_positions.empty and len(all_positions) >= self.config.max_total_positions:
            return False, f"already at max {self.config.max_total_positions} total positions"

        return True, "OK"
