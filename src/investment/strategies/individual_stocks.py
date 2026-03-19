import os
from datetime import datetime, timedelta

import pandas as pd

from investment.strategies.common import (
    clustered_lows,
    get_all_data,
    get_assets_by_momentum,
    get_closing_data,
    get_return,
    get_symbol_current_data,
    load_config,
    swing_lows,
)

EXECUTION_HISTORY = "individual_stocks_execution_history.csv"


def check_investment_percentage(total_list: int) -> float:
    return 100 / total_list


def prep_investment_breakdown(
    symbols_list: list[str],
    investment_capital: float,
    hold_symbol: str,
    score_threshold: float,
    momentum_df: pd.DataFrame,
) -> None:
    investment_pct = check_investment_percentage(len(symbols_list))
    investment_allocation = {}
    momentum_lookup = momentum_df.set_index("symbol")["momentum_score"].to_dict()

    for symbol in symbols_list:
        stock = get_symbol_current_data(symbol)
        price = stock.info["regularMarketPrice"]

        # Long-term support (90 days) — for bi-weekly rebalancing decisions
        long_data_df = get_all_data(symbol, datetime.today() - timedelta(days=90), "1d")
        long_swing_lows_df = swing_lows(long_data_df)
        long_zones = clustered_lows(long_data_df)
        if not long_zones.empty:
            best_zone = long_zones.sort_values("touches", ascending=False).iloc[0]
            support_long = (best_zone["zone_low"] + best_zone["zone_high"]) / 2
            support_long_date = None
        else:
            support_long = long_swing_lows_df.min()
            support_long_date = long_swing_lows_df.idxmin()

        # Short-term support (15 days) — for weekly stop-loss adjustments
        short_data_df = get_all_data(symbol, datetime.today() - timedelta(days=15), "1d")
        short_swing_lows_df = swing_lows(short_data_df)
        support_short = short_swing_lows_df.min()
        support_short_date = short_swing_lows_df.idxmin()

        investment_allocation[symbol] = {
            "price": price,
            "momentum_score": momentum_lookup.get(symbol),
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


def individual_stocks_flow() -> None:
    config = load_config(os.getenv("CONFIG_PATH"))
    print("Loaded configuration")
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
