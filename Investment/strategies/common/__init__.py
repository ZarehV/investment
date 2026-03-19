import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
import yaml
import yfinance as yf


def get_symbol_current_data(symbol):
    stock = yf.Ticker(symbol)
    return stock


def load_config(file_path="config.yaml"):
    with open(file_path, "r") as file:
        config = yaml.safe_load(file)
    return config


def get_closing_data(symbols, start_date, interval, end_date=None):
    if end_date is None:
        end_date = pd.Timestamp.today()
    data = yf.download(
        symbols, start=start_date.strftime("%Y-%m-%d"), end=end_date, interval=interval
    )["Close"]
    return data


def get_all_data(symbol, start_date, interval):
    stock = yf.Ticker(symbol)
    return stock.history(start=start_date, interval=interval)


def get_return(data):
    symbols = data.columns
    return_pd = pd.DataFrame(index=data.index, columns=symbols)
    for symbol in symbols:
        stock = get_symbol_current_data(symbol)
        current_price = stock.info.get("regularMarketPrice", None)
        if current_price is None:
            print(f"Warning: Current price for {symbol} is not available.")
            continue
        return_pd[symbol] = (current_price - data[symbol]) / current_price
    return return_pd


def get_assets_by_momentum(symbols, returns_pd, periods, total_periods=12):
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
    return (
        momentum_df.sort_values(by="momentum_score", ascending=False)
        .reset_index()
        .rename(columns={"index": "symbol"})
    )


def check_investment_percentage(symbol, bitcoin_symbol, is_bitcoin_in_top):
    if symbol == bitcoin_symbol:
        return 0.04
    elif symbol != bitcoin_symbol and is_bitcoin_in_top:
        return 0.24
    else:
        return 0.25


def get_top_assets(momentum_df, bitcoin_symbol, top_n=4):
    is_bitcoin_in_top = False
    symbols = (
        momentum_df.sort_values(by="momentum_score", ascending=False).head(top_n)["symbol"].unique()
    )
    for top_symbol in symbols:
        if bitcoin_symbol == top_symbol:
            is_bitcoin_in_top = True

    if is_bitcoin_in_top:
        print("Bitcoin is in the top 4...")
        return momentum_df.sort_values(by="momentum_score", ascending=False).head(
            top_n
        ), is_bitcoin_in_top

    return momentum_df.sort_values(by="momentum_score", ascending=False).head(
        top_n - 1
    ), is_bitcoin_in_top


def pivot_points(df):
    pp = (df["High"].shift(1) + df["Low"].shift(1) + df["Close"].shift(1)) / 3
    s1 = (2 * pp) - df["High"].shift(1)
    s2 = pp - (df["High"].shift(1) - df["Low"].shift(1))
    s3 = df["Low"].shift(1) - 2 * (df["High"].shift(1) - pp)
    return pp, s1, s2, s3


def swing_lows(df, window=5):
    lows = df["Low"]
    pivots = argrelextrema(lows.values, np.less_equal, order=window)[0]
    out = pd.Series(index=df.index, data=np.nan)
    out.iloc[pivots] = lows.iloc[pivots]
    return out.dropna()


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
