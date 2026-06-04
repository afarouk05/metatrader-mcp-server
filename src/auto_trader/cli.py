import logging
import click

from .config import AutoTraderConfig
from .engine import AutoTrader
from .strategies import get_strategy


@click.command()
# ── MT5 connection ──────────────────────────────────────────────────────
@click.option("--login",    required=True, envvar="LOGIN",    type=int,   help="MT5 account login")
@click.option("--password", required=True, envvar="PASSWORD",             help="MT5 account password")
@click.option("--server",   required=True, envvar="SERVER",               help="MT5 server name")
@click.option("--path",     default=None,  envvar="MT5_PATH",             help="Path to MT5 terminal (auto-detect if omitted)")
# ── What to trade ───────────────────────────────────────────────────────
@click.option("--symbol",      "symbols",   multiple=True, default=["EURUSD"], envvar="SYMBOLS",          help="Symbol(s) to trade (repeat for multiple)")
@click.option("--timeframe",                               default="M15",      envvar="TIMEFRAME",        show_default=True, help="Candle timeframe (M1 M5 M15 M30 H1 H4 D1)")
@click.option("--volume",                                  default=0.01, type=float, envvar="VOLUME",     show_default=True, help="Lot size per order")
@click.option("--stop-loss-pips",                          default=30.0, type=float, envvar="SL_PIPS",    show_default=True, help="Stop loss in pips")
@click.option("--take-profit-pips",                        default=60.0, type=float, envvar="TP_PIPS",    show_default=True, help="Take profit in pips")
# ── Risk controls ───────────────────────────────────────────────────────
@click.option("--max-positions",    default=1,     type=int,   envvar="MAX_POSITIONS",   show_default=True, help="Max open positions per symbol")
@click.option("--max-total",        default=3,     type=int,   envvar="MAX_TOTAL",       show_default=True, help="Max total open positions across all symbols")
@click.option("--min-margin-level", default=200.0, type=float, envvar="MIN_MARGIN",      show_default=True, help="Minimum margin level %% before trades are blocked (0 = disabled)")
# ── Strategy selection ──────────────────────────────────────────────────
@click.option("--strategy", default="ma_crossover", envvar="STRATEGY", show_default=True,
              type=click.Choice(["ma_crossover", "rsi"]), help="Trading strategy")
@click.option("--fast-period",    default=9,    type=int,   show_default=True, help="[ma_crossover] Fast EMA period")
@click.option("--slow-period",    default=21,   type=int,   show_default=True, help="[ma_crossover] Slow EMA period")
@click.option("--rsi-period",     default=14,   type=int,   show_default=True, help="[rsi] RSI period")
@click.option("--rsi-oversold",   default=30.0, type=float, show_default=True, help="[rsi] Oversold threshold")
@click.option("--rsi-overbought", default=70.0, type=float, show_default=True, help="[rsi] Overbought threshold")
# ── Engine ──────────────────────────────────────────────────────────────
@click.option("--poll-interval", default=60,  type=int,  envvar="POLL_INTERVAL", show_default=True, help="Seconds between strategy checks")
@click.option("--dry-run",  is_flag=True, envvar="DRY_RUN",  help="Log signals without placing orders")
@click.option("--debug",    is_flag=True, envvar="DEBUG",    help="Enable verbose debug logging")
def main(
    login, password, server, path,
    symbols, timeframe, volume, stop_loss_pips, take_profit_pips,
    max_positions, max_total, min_margin_level,
    strategy, fast_period, slow_period, rsi_period, rsi_oversold, rsi_overbought,
    poll_interval, dry_run, debug,
):
    """MetaTrader 5 Auto Trader — runs a strategy loop against a live MT5 terminal.

    Credentials can be supplied via CLI flags or environment variables
    (LOGIN, PASSWORD, SERVER). All other options have sensible defaults.

    Example (dry run on EURUSD with RSI strategy):

        metatrader-auto-trader --login 12345 --password secret --server Demo-Server \\
            --strategy rsi --dry-run
    """
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    strategy_params: dict = {}
    if strategy == "ma_crossover":
        strategy_params = {"fast_period": fast_period, "slow_period": slow_period}
    elif strategy == "rsi":
        strategy_params = {"period": rsi_period, "oversold": rsi_oversold, "overbought": rsi_overbought}

    config = AutoTraderConfig(
        login=login,
        password=password,
        server=server,
        path=path,
        symbols=list(symbols),
        timeframe=timeframe,
        volume=volume,
        stop_loss_pips=stop_loss_pips,
        take_profit_pips=take_profit_pips,
        max_positions_per_symbol=max_positions,
        max_total_positions=max_total,
        min_margin_level=min_margin_level,
        strategy=strategy,
        strategy_params=strategy_params,
        poll_interval=poll_interval,
        dry_run=dry_run,
        debug=debug,
    )

    strat = get_strategy(strategy, strategy_params)
    trader = AutoTrader(config, strat)
    trader.start()


if __name__ == "__main__":
    main()
