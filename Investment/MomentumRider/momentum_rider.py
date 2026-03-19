import numpy as np
import yaml
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


def load_config():
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)
    return config


def get_data(symbols, start_date, interval):
    data = yf.download(symbols, start=start_date.strftime("%Y-%m-%d"), interval=interval)["Close"]
    return data


def get_return(data):
    return_pd = data.pct_change()
    return return_pd


def get_top_assets(symbols, returns_pd, periods, bitcoin_symbol, total_periods=12, top_n=4):
    print("Calculating momentum scores...")
    momentum_scores = {}
    for symbol in symbols:
        last_12 = returns_pd[symbol].dropna()[-total_periods:]
        if len(last_12) < total_periods:
            continue
        total = 0
        for period in periods:
            total += last_12[-period:].mean()
        avg_return = total / len(periods)
        momentum_scores[symbol] = avg_return

    momentum_df = pd.DataFrame.from_dict(
        momentum_scores, orient="index", columns=["momentum_score"]
    )
    top_momentum_df = (
        momentum_df.sort_values(by="momentum_score", ascending=False)
        .reset_index()
        .rename(columns={"index": "symbol"})
        .head(top_n)
    )
    is_bitcoin_in_top = False
    for top_symbol in top_momentum_df["symbol"].unique():
        if bitcoin_symbol == top_symbol:
            is_bitcoin_in_top = True

    if is_bitcoin_in_top:
        print("Bitcoin is in the top 4...")
        top_momentum_df = (
            momentum_df.sort_values(by="momentum_score", ascending=False)
            .reset_index()
            .rename(columns={"index": "symbol"})
            .head(top_n + 1)
        )

    return top_momentum_df, is_bitcoin_in_top


def identify_support(
    symbol: str,
    period: str = "1mo",
    interval: str = "1d",
    price_choice: str = "top",  # "top", "mid", or "bottom"
    weights: dict | None = None,  # {"dist":0.45,"hits":0.35,"fresh":0.15,"tight":0.05}
    auto_adjust: bool = True,
):
    """
    Return the strongest clustered-low support zone and a single actionable price.

    Parameters
    ----------
    symbol : str
        Symbol understood by yfinance.
    period : str
        e.g. "6mo", "1y", "2y".
    interval : str
        e.g. "1d", "1h".
    bins : int
        Histogram bins for lows → finer granularity with larger numbers.
    touch_threshold : int
        Minimum # of low-prints inside a bin for it to count as a cluster.
    price_choice : str
        'top' = zone_high, 'mid' = midpoint, 'bottom' = zone_low.
    weights : dict
        Keys 'dist', 'hits', 'fresh', 'tight'; values must sum to 1.
    plot : bool
        If True, draw price series with support bands.
    auto_adjust : bool
        Pass-through to yfinance (adjusts for splits & dividends).

    Returns
    -------
    support_price : float | None
    best_zone      : pandas.Series | None   (columns: zone_low, zone_high, touches, score, …)
    price_df       : pandas.DataFrame       (the downloaded OHLCV data)
    """

    # ------------------------------------------------------------------ helpers
    def clustered_lows(df, bins=50, threshold=3):
        hist, edges = np.histogram(df["Low"], bins=bins)
        zones, run = [], None
        for i, hits in enumerate(hist):
            if hits >= threshold:
                if run is None:
                    run = [edges[i], hits]
                else:
                    run[1] += hits
            elif run:
                zones.append((run[0], edges[i], run[1]))  # low, high, touches
                run = None
        if run:  # handle trailing run
            zones.append((run[0], edges[-1], run[1]))
        return pd.DataFrame(zones, columns=["zone_low", "zone_high", "touches"])

    # ------------------------------------------------------------------ download
    start_date = datetime.today() - timedelta(days=60 * 1.1)
    df = yf.download(symbol, start=start_date.strftime("%Y-%m-%d"), interval="1d").dropna()
    clustered_lows(df)
    if df.empty:
        raise ValueError("No data returned; check ticker/period/interval")

    zones = clustered_lows(df)
    _last_close = df["Close"].iloc[-1]
    close = float(_last_close.squeeze())
    zones = zones[zones["zone_high"] < close]
    if zones.empty:
        return None, None, df

    # ------------------------------------------------------------------ scores
    zones = zones.copy()
    zones["dist"] = close - zones["zone_high"]  # lower = closer → stronger
    low_series = df["Low"]
    if isinstance(low_series, pd.DataFrame):  # happens only with MultiIndex cols
        low_series = low_series.iloc[:, 0]  # pick the first (only) column

    zones["fresh"] = [
        (df.index[-1] - low_series[low_series.between(lo, hi)].index.max()).days
        for lo, hi in zip(zones.zone_low, zones.zone_high)
    ]  # lower = fresher
    zones["tight"] = zones["zone_high"] - zones["zone_low"]  # lower = tighter

    # normalise 0-1; invert columns where ‘smaller is better’
    for col in ["dist", "fresh", "tight"]:
        rng = zones[col].max() - zones[col].min() + 1e-9
        zones[col] = 1 - (zones[col] - zones[col].min()) / rng
    rng = zones["touches"].max() - zones["touches"].min() + 1e-9
    zones["hits"] = (zones["touches"] - zones["touches"].min()) / rng

    # default weights
    if weights is None:
        weights = {"dist": 0.45, "hits": 0.35, "fresh": 0.15, "tight": 0.05}
    w = weights

    zones["score"] = (
        w["dist"] * zones["dist"]
        + w["hits"] * zones["hits"]
        + w["fresh"] * zones["fresh"]
        + w["tight"] * zones["tight"]
    )

    best = zones.sort_values("score", ascending=False).iloc[0]

    # ------------------------------------------------------------------ pick number
    if price_choice == "mid":
        support = (best.zone_low + best.zone_high) / 2
    elif price_choice == "bottom":
        support = best.zone_low
    else:  # "top"
        support = best.zone_high

    return float(round(support, 2)), best, df


def prep_investment_breakdown(
    top_momentum_df,
    investment_capital,
    bitcoin_symbol,
    hold_symbold,
    score_threshold,
    is_bitcoin_in_top=False,
):
    investment_allocation = {}
    hold_folds = 0
    for index, row in top_momentum_df.iterrows():
        symbol = row["symbol"]
        score = row["momentum_score"]
        if score < score_threshold:
            print(f"Skipping {symbol} due to low momentum score: {score}")
            hold_folds += 1
            continue
        stock = yf.Ticker(symbol)
        price = stock.info["regularMarketPrice"]
        support, zone, df = identify_support(symbol)

        if symbol == bitcoin_symbol:
            investment_allocation[symbol] = {
                "price": price,
                "amount_to_invest": investment_capital * 0.04,
                "num_shares": int((investment_capital * 0.04) / price),
                "support": support,
                "zone": zone,
            }
        elif symbol != bitcoin_symbol and is_bitcoin_in_top:
            investment_allocation[symbol] = {
                "price": price,
                "amount_to_invest": investment_capital * 0.24,
                "num_shares": int((investment_capital * 0.24) / price),
                "support": support,
                "zone": zone,
            }
        else:
            investment_allocation[symbol] = {
                "price": price,
                "amount_to_invest": investment_capital * 0.25,
                "num_shares": int((investment_capital * 0.25) / price),
                "support": support,
                "zone": zone,
            }

    if hold_folds > 0:
        stock = yf.Ticker(symbol)
        price = stock.info["regularMarketPrice"]
        support, zone, df = identify_support(symbol)
        investment_allocation[hold_symbold] = {
            "price": price,
            "amount_to_invest": investment_capital * 0.25,
            "num_shares": int((investment_capital * 0.25) / price),
            "support": support,
            "zone": zone,
        }
    for symbol, allocation in investment_allocation.items():
        print(f"Investment for {symbol}:")
        print(f"  Price: {allocation['price']}")
        print(f"  Amount to Invest: {allocation['amount_to_invest']}")
        print(f"  Number of Shares: {allocation['num_shares']}")
        print(f"  Support: {allocation['support']}")
        # print(f"  Zone: {allocation['zone']}")


def main():
    config = load_config()
    print("Loaded configuration")
    start_date = datetime.today() - timedelta(days=365 * 1.1)
    symbols = list(config["momentumrider"]["assets"].keys())
    daily_data_pd = get_data(symbols, start_date, config["momentumrider"]["interval"])
    if config["momentumrider"]["debug"]:
        daily_data_pd.to_csv("momentum_rider_raw.csv")
    returns_pd = get_return(daily_data_pd)
    if config["momentumrider"]["debug"]:
        returns_pd.to_csv("returns.csv")
    top_momentum_df, is_bitcoin_in_top = get_top_assets(
        symbols,
        returns_pd,
        list(config["momentumrider"]["periods"]["months"].keys()),
        config["momentumrider"]["bitcoin_symbol"],
    )
    prep_investment_breakdown(
        top_momentum_df,
        config["momentumrider"]["investment_capital"],
        config["momentumrider"]["bitcoin_symbol"],
        config["momentumrider"]["score_threshold"],
        is_bitcoin_in_top,
    )


if __name__ == "__main__":
    main()
