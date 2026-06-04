from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class AutoTraderConfig:
    # MT5 connection
    login: int
    password: str
    server: str
    path: Optional[str] = None

    # Symbols and timeframe
    symbols: List[str] = field(default_factory=lambda: ["EURUSD"])
    timeframe: str = "M15"

    # Order sizing
    volume: float = 0.01
    stop_loss_pips: float = 30.0
    take_profit_pips: float = 60.0

    # Risk controls
    max_positions_per_symbol: int = 1
    max_total_positions: int = 3
    min_margin_level: float = 200.0  # percent; 0 disables check

    # Strategy
    strategy: str = "ma_crossover"
    strategy_params: dict = field(default_factory=dict)

    # Engine behaviour
    poll_interval: int = 60   # seconds between ticks
    dry_run: bool = False      # log signals without placing orders
    debug: bool = False
