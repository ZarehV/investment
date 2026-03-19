"""Momentum-driver (MomentumRider) strategy.

Ranks a multi-asset universe — equities, bonds, commodities, gold, and
Bitcoin — by momentum score and allocates capital across the top-N assets.
Bitcoin receives a dedicated 4 % sleeve; when it is absent from the basket
the remaining assets share capital equally at 25 % each (or 24 % when
Bitcoin is present).
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from investment.logging import get_logger
from investment.strategies.common import (
    check_investment_percentage,
    clustered_lows,
    get_all_data,
    get_assets_by_momentum,
    get_closing_data,
    get_return,
    get_top_assets,
    load_config,
    swing_lows,
)

logger = get_logger(__name__)

EXECUTION_HISTORY = "momentum_driver_execution_history.csv"


def prep_investment_breakdown(
    top_momentum_df: pd.DataFrame,
    investment_capital: float,
    bitcoin_symbol: str,
    hold_symbol: str,
    score_threshold: float,
    is_bitcoin_in_top: bool = False,
) -> None:
    """Calculate per-asset allocations and print the investment breakdown.

    Assets whose momentum score falls below *score_threshold* are skipped and
    their capital is redirected to *hold_symbol*.  For each invested asset the
    function derives a long-term support (90-day clustered lows) and a
    short-term support (15-day swing lows), then prints and persists the
    allocation to the execution-history CSV.

    Args:
        top_momentum_df: Top-ranked assets from
            :func:`~investment.strategies.common.get_top_assets`.
        investment_capital: Total capital to deploy (in dollars).
        bitcoin_symbol: Ticker symbol representing Bitcoin (special 4 % allocation).
        hold_symbol: Ticker to accumulate when assets are skipped.
        score_threshold: Minimum momentum score required to invest in an asset.
        is_bitcoin_in_top: Whether Bitcoin appears in the selected basket.
    """
    investment_allocation: dict[str, dict] = {}
    hold_folds = 0

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

        stock = yf.Ticker(symbol)
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

        investment_pct = check_investment_percentage(symbol, bitcoin_symbol, is_bitcoin_in_top)
        investment_allocation[symbol] = {
            "price": price,
            "momentum_score": score,
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

        investment_pct = (
            check_investment_percentage(hold_symbol, bitcoin_symbol, is_bitcoin_in_top) * hold_folds
        )
        investment_allocation[hold_symbol] = {
            "price": price,
            "momentum_score": "N/A",
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


def momentum_driver_flow() -> None:
    """Load configuration and run the momentum-driver strategy end-to-end."""
    config = load_config(os.getenv("CONFIG_PATH"))
    logger.info("Loaded configuration")

    start_date = datetime.today() - timedelta(days=365 * 1.1)
    symbols = list(config["momentumrider"]["assets"].keys())

    daily_data_pd = get_closing_data(symbols, start_date, config["momentumrider"]["interval"])

    if config["momentumrider"]["debug"]:
        daily_data_pd.to_csv("momentum_rider_raw.csv")

    returns_pd = get_return(daily_data_pd)

    if config["momentumrider"]["debug"]:
        returns_pd.to_csv("returns.csv")

    momentum_df = get_assets_by_momentum(
        list(config["momentumrider"]["assets"].keys()),
        returns_pd,
        list(config["momentumrider"]["periods"]["months"].keys()),
    )

    top_momentum_df, is_bitcoin_in_top = get_top_assets(
        momentum_df,
        config["momentumrider"]["bitcoin_symbol"],
        config["momentumrider"]["top_n"],
    )

    prep_investment_breakdown(
        top_momentum_df,
        config["momentumrider"]["investment_capital"],
        config["momentumrider"]["bitcoin_symbol"],
        config["momentumrider"]["hold_symbol"],
        config["momentumrider"]["score_threshold"],
        is_bitcoin_in_top,
    )
