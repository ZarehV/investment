"""Individual-stocks momentum strategy.

Ranks a configurable set of individual equities by momentum score and
allocates capital equally across all of them, computing both a long-term
(90-day) and a short-term (15-day) support level for each position.
"""

import os
from datetime import datetime, timedelta

import pandas as pd

from investment.logging import get_logger
from investment.strategies.common import (
    clustered_lows,
    get_all_data,
    get_assets_by_momentum,
    get_closing_data,
    get_return,
    get_short_term_momentum_score,
    get_symbol_current_data,
    load_config,
    swing_lows,
)

logger = get_logger(__name__)

EXECUTION_HISTORY = "individual_stocks_execution_history.csv"


def check_investment_percentage(total_list: int) -> float:
    """Return the equal-weight allocation fraction for a basket of *total_list* assets.

    Args:
        total_list: Number of assets in the portfolio.

    Returns:
        Allocation percentage as a plain number, e.g. ``25.0`` for four assets.
    """
    return 100 / total_list


def prep_investment_breakdown(
    symbols_list: list[str],
    investment_capital: float,
    hold_symbol: str,
    score_threshold: float,
    momentum_df: pd.DataFrame,
) -> None:
    """Calculate per-symbol allocations and print the investment breakdown.

    For each symbol the function fetches the current price, derives a
    long-term support (90-day clustered lows) and a short-term support
    (15-day swing lows), then prints and persists the allocation to the
    execution-history CSV.

    Args:
        symbols_list: Ticker symbols to allocate capital across.
        investment_capital: Total capital to deploy (in dollars).
        hold_symbol: Ticker to use when a position is held in cash.
        score_threshold: Minimum momentum score required to invest.
        momentum_df: Scored DataFrame from
            :func:`~investment.strategies.common.get_assets_by_momentum`.
    """
    investment_pct = check_investment_percentage(len(symbols_list))
    investment_allocation: dict[str, dict] = {}
    momentum_lookup = momentum_df.set_index("symbol")["momentum_score"].to_dict()

    st_closes = get_closing_data(symbols_list, datetime.today() - timedelta(days=60), "1d")
    st_scores_df = get_short_term_momentum_score(symbols_list, st_closes)
    st_score_lookup: dict[str, float] = st_scores_df.set_index("symbol")["momentum_score"].to_dict()

    for symbol in symbols_list:
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

        investment_allocation[symbol] = {
            "price": price,
            "momentum_score": momentum_lookup.get(symbol),
            "short_term_momentum_score": st_score_lookup.get(symbol, "N/A"),
            "amount_to_invest": investment_capital * investment_pct,
            "num_shares": int((investment_capital * investment_pct) / price),
            "investment_pct": investment_pct,
            "support_long": support_long,
            "support_long_date": support_long_date,
            "support_short": support_short,
            "support_short_date": support_short_date,
        }

    display_df = pd.DataFrame.from_dict(investment_allocation, orient="index")[
        [
            "momentum_score",
            "short_term_momentum_score",
            "price",
            "num_shares",
            "amount_to_invest",
            "investment_pct",
            "support_long",
            "support_short",
        ]
    ].rename(
        columns={
            "momentum_score": "Long Mom.",
            "short_term_momentum_score": "Short Mom.",
            "price": "Price",
            "num_shares": "Shares",
            "amount_to_invest": "Amount ($)",
            "investment_pct": "Alloc",
            "support_long": "Sup 90d",
            "support_short": "Sup 15d",
        }
    )
    display_df.index.name = "Symbol"
    for col in ["Long Mom.", "Short Mom.", "Price", "Sup 90d", "Sup 15d"]:
        display_df[col] = pd.to_numeric(display_df[col], errors="coerce").round(4)
    print(display_df.to_string())

    if os.path.exists(EXECUTION_HISTORY):
        df = pd.DataFrame.from_dict(investment_allocation, orient="index")
        current = pd.read_csv(EXECUTION_HISTORY, index_col=0)
        df = pd.concat([current, df])
        df["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        df = pd.DataFrame.from_dict(investment_allocation, orient="index")
        df["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    df.to_csv(EXECUTION_HISTORY, index=True)


def individual_stocks_flow() -> None:
    """Load configuration and run the individual-stocks strategy end-to-end."""
    config = load_config(os.getenv("CONFIG_PATH"))
    logger.info("Loaded configuration")
    start_date = datetime.today() - timedelta(days=365 * 1.1)
    symbols = list(config["individual_stocks"]["assets"].keys())

    closing_data = get_closing_data(symbols, start_date, config["individual_stocks"]["interval"])
    returns_pd = get_return(closing_data)
    momentum_df = get_assets_by_momentum(
        symbols,
        returns_pd,
        list(config["individual_stocks"]["periods"]["months"].keys()),
    )

    print("\nMomentum Rankings:")
    print(momentum_df.to_string(index=False))
    print()

    prep_investment_breakdown(
        symbols,
        config["individual_stocks"]["investment_capital"],
        config["individual_stocks"]["hold_symbol"],
        config["individual_stocks"]["score_threshold"],
        momentum_df,
    )
