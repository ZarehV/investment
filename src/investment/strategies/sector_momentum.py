"""Sector-rotation momentum strategy.

Ranks SPDR sector ETFs by momentum score and allocates capital equally
across the top-N sectors, computing both a long-term (90-day) and a
short-term (15-day) support level for each position.

Momentum is calculated using data through the last day of the previous
month to avoid look-ahead bias.
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from investment.logging import get_logger
from investment.strategies.common import (
    clustered_lows,
    get_all_data,
    get_assets_by_momentum,
    get_closing_data,
    get_return,
    get_short_term_momentum_score,
    get_symbol_current_data,
    get_top_assets,
    load_config,
    swing_lows,
)

logger = get_logger(__name__)

EXECUTION_HISTORY = "sector_momentum_execution_history.csv"


def check_investment_percentage() -> float:
    """Return the fixed per-sector allocation fraction (33 %).

    Returns:
        ``0.33`` — one third of capital per selected sector.
    """
    return 0.33


def prep_investment_breakdown(
    top_momentum_df: pd.DataFrame,
    investment_capital: float,
    hold_symbol: str,
    score_threshold: float,
) -> None:
    """Calculate per-sector allocations and print the investment breakdown.

    Sectors whose momentum score falls below *score_threshold* are skipped and
    their capital is redirected to *hold_symbol*.  For each invested sector the
    function derives a long-term support (90-day clustered lows) and a
    short-term support (15-day swing lows), then prints and persists the
    allocation to the execution-history CSV.

    Args:
        top_momentum_df: Top-ranked sectors from
            :func:`~investment.strategies.common.get_top_assets`.
        investment_capital: Total capital to deploy (in dollars).
        hold_symbol: Ticker to accumulate when sectors are skipped.
        score_threshold: Minimum momentum score required to invest in a sector.
    """
    investment_allocation: dict[str, dict] = {}
    hold_folds = 0

    symbols_to_score = top_momentum_df["symbol"].tolist()
    st_closes = get_closing_data(symbols_to_score, datetime.today() - timedelta(days=60), "1d")
    st_scores_df = get_short_term_momentum_score(symbols_to_score, st_closes)
    st_score_lookup: dict[str, float] = st_scores_df.set_index("symbol")["momentum_score"].to_dict()

    for _, row in top_momentum_df.iterrows():
        symbol: str = row["symbol"]
        score: float = row["momentum_score"]

        if score < score_threshold:
            logger.info(
                "Skipping symbol due to low momentum score",
                extra={"symbol": symbol, "score": score},
            )
            hold_folds += 1
            continue

        stock = get_symbol_current_data(symbol)
        price: float = stock.info["regularMarketPrice"]

        # Long-term support (90 days) — for bi-weekly rebalancing decisions.
        long_data_df = get_all_data(symbol, datetime.today() - timedelta(days=90), "1d")
        long_swing_lows_df = swing_lows(long_data_df)
        long_zones = clustered_lows(long_data_df)
        if not long_zones.empty:
            best_zone = long_zones.sort_values("touches", ascending=False).iloc[0]
            support_long: float = (best_zone["zone_low"] + best_zone["zone_high"]) / 2
            zone_touches = long_swing_lows_df[
                (long_swing_lows_df >= best_zone["zone_low"])
                & (long_swing_lows_df <= best_zone["zone_high"])
            ]
            support_long_date = zone_touches.index[-1] if not zone_touches.empty else None
        else:
            support_long = long_swing_lows_df.min()
            support_long_date = long_swing_lows_df.idxmin()

        # Short-term support (15 days) — for weekly stop-loss adjustments.
        short_data_df = get_all_data(symbol, datetime.today() - timedelta(days=15), "1d")
        short_swing_lows_df = swing_lows(short_data_df)
        support_short: float = short_swing_lows_df.min()
        support_short_date = short_swing_lows_df.idxmin()

        investment_pct = check_investment_percentage()
        investment_allocation[symbol] = {
            "price": price,
            "momentum_score": score,
            "short_term_momentum_score": st_score_lookup.get(symbol, "N/A"),
            "amount_to_invest": investment_capital * investment_pct,
            "num_shares": int((investment_capital * investment_pct) / price),
            "investment_pct": investment_pct,
            "support_long": support_long,
            "support_long_date": support_long_date,
            "support_short": support_short,
            "support_short_date": support_short_date,
        }

    if hold_folds > 0:
        logger.info(
            "Redirecting skipped allocations to hold symbol",
            extra={"hold_folds": hold_folds, "hold_symbol": hold_symbol},
        )
        stock = yf.Ticker(hold_symbol)
        price = stock.info["regularMarketPrice"]

        long_data_df = get_all_data(hold_symbol, datetime.today() - timedelta(days=90), "1d")
        long_swing_lows_df = swing_lows(long_data_df)
        long_zones = clustered_lows(long_data_df)
        if not long_zones.empty:
            best_zone = long_zones.sort_values("touches", ascending=False).iloc[0]
            support_long = (best_zone["zone_low"] + best_zone["zone_high"]) / 2
            zone_touches = long_swing_lows_df[
                (long_swing_lows_df >= best_zone["zone_low"])
                & (long_swing_lows_df <= best_zone["zone_high"])
            ]
            support_long_date = zone_touches.index[-1] if not zone_touches.empty else None
        else:
            support_long = long_swing_lows_df.min()
            support_long_date = long_swing_lows_df.idxmin()

        short_data_df = get_all_data(hold_symbol, datetime.today() - timedelta(days=15), "1d")
        short_swing_lows_df = swing_lows(short_data_df)
        support_short = short_swing_lows_df.min()
        support_short_date = short_swing_lows_df.idxmin()

        investment_pct = check_investment_percentage() * hold_folds
        investment_allocation[hold_symbol] = {
            "price": price,
            "momentum_score": "N/A",
            "short_term_momentum_score": "N/A",
            "amount_to_invest": investment_capital * investment_pct,
            "num_shares": int((investment_capital * investment_pct) / price),
            "investment_pct": investment_pct,
            "support_long": support_long,
            "support_long_date": support_long_date,
            "support_short": support_short,
            "support_short_date": support_short_date,
        }

    for symbol, allocation in investment_allocation.items():
        print(f"Investment for {symbol}:")
        print(f"  Momentum Score: {allocation['momentum_score']}")
        print(f"  Short-term Momentum Score: {allocation['short_term_momentum_score']}")
        print(f"  Price: {allocation['price']}")
        print(f"  Amount to Invest: {allocation['amount_to_invest']}")
        print(f"  Number of Shares: {allocation['num_shares']}")
        print(f"  Investment Percentage: {allocation['investment_pct']}")
        print(f"  Support (90d): {allocation['support_long']}  [{allocation['support_long_date']}]")
        print(
            f"  Support (15d): {allocation['support_short']}  [{allocation['support_short_date']}]"
        )

    if os.path.exists(EXECUTION_HISTORY):
        df = pd.DataFrame.from_dict(investment_allocation, orient="index")
        current = pd.read_csv(EXECUTION_HISTORY, index_col=0)
        df = pd.concat([current, df])
        df["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        df = pd.DataFrame.from_dict(investment_allocation, orient="index")
        df["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    df.to_csv(EXECUTION_HISTORY, index=True)


def sector_momentum_flow() -> None:
    """Load configuration and run the sector-momentum strategy end-to-end."""
    config = load_config(os.getenv("CONFIG_PATH"))
    logger.info("Loaded configuration")

    today = datetime.today()
    first_day_this_month = today.replace(day=1)
    last_day_prev_month = first_day_this_month - timedelta(days=1)
    start_date = last_day_prev_month - timedelta(days=365)

    logger.info(
        "Fetching sector data",
        extra={
            "start_date": str(start_date),
            "end_date": str(last_day_prev_month),
        },
    )

    symbols = list(config["sector_momentum"]["assets"].keys())
    daily_data_pd = get_closing_data(
        symbols,
        start_date,
        config["sector_momentum"]["interval"],
        last_day_prev_month,
    )

    if config["sector_momentum"]["debug"]:
        daily_data_pd.to_csv("sector_momentum_raw.csv")

    returns_pd = get_return(daily_data_pd)

    if config["sector_momentum"]["debug"]:
        returns_pd.to_csv("returns.csv")

    momentum_df = get_assets_by_momentum(
        list(config["sector_momentum"]["assets"].keys()),
        returns_pd,
        list(config["sector_momentum"]["periods"]["months"].keys()),
    )

    if config["sector_momentum"]["debug"]:
        momentum_df.to_csv("momentum_df.csv")

    top_momentum_df, _ = get_top_assets(
        momentum_df,
        config["sector_momentum"]["bitcoin_symbol"],
        config["sector_momentum"]["top_n"],
    )

    prep_investment_breakdown(
        top_momentum_df,
        config["sector_momentum"]["investment_capital"],
        config["sector_momentum"]["hold_symbol"],
        config["sector_momentum"]["score_threshold"],
    )
