"""Shared utilities for all investment strategies.

Provides data retrieval, momentum scoring, support-level detection, and
allocation helpers used across momentum_driver, sector_momentum and
individual_stocks strategies.
"""

import importlib.resources as pkg_resources
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import yaml
import yfinance as yf
from scipy.signal import argrelextrema

from investment.logging import get_logger

logger = get_logger(__name__)


def get_symbol_current_data(symbol: str) -> yf.Ticker:
    """Return a :class:`yfinance.Ticker` object for *symbol*.

    Args:
        symbol: Ticker symbol (e.g. ``"AAPL"``).

    Returns:
        A ``yfinance.Ticker`` instance ready for further queries.
    """
    return yf.Ticker(symbol)


def load_config(file_path: str | None = None) -> dict[str, Any]:
    """Load and return the YAML configuration file.

    Falls back to the bundled ``investment/config/config.yaml`` when
    *file_path* is ``None``.

    Args:
        file_path: Optional path to a YAML configuration file.

    Returns:
        Parsed configuration as a nested dictionary.
    """
    if file_path is None:
        with pkg_resources.files("investment.config").joinpath("config.yaml").open("r") as f:
            return yaml.safe_load(f)  # type: ignore[return-value]
    with open(file_path) as file:
        return yaml.safe_load(file)  # type: ignore[return-value]


def get_closing_data(
    symbols: list[str],
    start_date: datetime,
    interval: str,
    end_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Download historical closing prices for a list of symbols.

    Args:
        symbols: Ticker symbols to download.
        start_date: Inclusive start of the history window.
        interval: yfinance interval string (e.g. ``"1mo"``, ``"1d"``).
        end_date: Exclusive end of the history window; defaults to today.

    Returns:
        DataFrame indexed by date with one column per symbol.
    """
    if end_date is None:
        end_date = pd.Timestamp.today()
    data: pd.DataFrame = yf.download(
        symbols,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date,
        interval=interval,
    )["Close"]
    return data


def get_all_data(symbol: str, start_date: datetime, interval: str) -> pd.DataFrame:
    """Download full OHLCV history for a single symbol.

    Args:
        symbol: Ticker symbol.
        start_date: Inclusive start of the history window.
        interval: yfinance interval string (e.g. ``"1d"``).

    Returns:
        DataFrame with columns ``Open``, ``High``, ``Low``, ``Close``,
        ``Volume``, indexed by date.
    """
    stock = yf.Ticker(symbol)
    return stock.history(start=start_date, interval=interval)  # type: ignore[return-value]


def get_return(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate the return of each symbol relative to its current market price.

    The return for each historical date is computed as
    ``(current_price - historical_price) / historical_price``.

    Args:
        data: Closing-price DataFrame as returned by :func:`get_closing_data`.

    Returns:
        DataFrame of the same shape as *data* containing return values.
    """
    symbols = data.columns
    return_pd = pd.DataFrame(index=data.index, columns=symbols)
    for symbol in symbols:
        stock = get_symbol_current_data(symbol)
        current_price: float | None = stock.info.get("regularMarketPrice")
        if current_price is None:
            logger.warning("Current price unavailable", extra={"symbol": symbol})
            continue
        return_pd[symbol] = (current_price - data[symbol]) / data[symbol]
    return return_pd


def get_assets_by_momentum(
    symbols: list[str],
    returns_pd: pd.DataFrame,
    periods: list[int],
    total_periods: int = 12,
) -> pd.DataFrame:
    """Score each symbol by its average return-to-current across look-back periods.

    ``returns_pd`` is produced by :func:`get_return`, which stores for every
    historical bar the cumulative return from that bar to the *current* market
    price, i.e.:

    .. code-block:: none

        returns_pd[symbol].iloc[-n]  ==  (current_price - price_n_bars_ago)
                                         / price_n_bars_ago

    The momentum score for a symbol is therefore the simple average of these
    already-cumulative returns at each look-back horizon::

        score = mean( returns_pd[s].iloc[-p]  for p in periods )

    Example with ``periods = [3, 6, 9, 12]`` monthly bars:

        score = (3-mo return + 6-mo return + 9-mo return + 12-mo return) / 4

    This matches the dual-momentum convention used in
    :func:`~investment.strategies.momentum_rider.momentum_rider_flow`.

    Args:
        symbols: Ticker symbols to score.
        returns_pd: Return DataFrame as produced by :func:`get_return`.
        periods: Look-back lengths in bars (e.g. ``[3, 6, 9, 12]`` for
            monthly data).  Each value selects the bar that many positions
            from the end of the series.
        total_periods: Minimum number of observations required to score a
            symbol; symbols with fewer observations are skipped.

    Returns:
        DataFrame with columns ``symbol`` and ``momentum_score``, sorted
        descending by score.
    """
    logger.info("Calculating momentum scores")
    momentum_scores: dict[str, float] = {}
    for symbol in symbols:
        last_n = returns_pd[symbol].dropna()[-total_periods:]
        if len(last_n) < total_periods:
            continue
        # Each entry in last_n is the cumulative return from that bar to today.
        # The n-period return is directly at iloc[-n]; no compounding needed.
        total = sum(float(last_n.iloc[-period]) for period in periods)
        momentum_scores[symbol] = total / len(periods)

    momentum_df = pd.DataFrame.from_dict(
        momentum_scores,
        orient="index",
        columns=["momentum_score"],
    )
    return (
        momentum_df.sort_values(by="momentum_score", ascending=False)
        .reset_index()
        .rename(columns={"index": "symbol"})
    )


def check_investment_percentage(
    symbol: str,
    bitcoin_symbol: str,
    is_bitcoin_in_top: bool,
) -> float:
    """Return the portfolio allocation fraction for *symbol*.

    Bitcoin receives a fixed 4 % allocation.  When Bitcoin is already in the
    top-N basket, every other asset is capped at 24 % so the total stays at
    100 %.  Otherwise each asset gets a full 25 % share.

    Args:
        symbol: Asset being allocated.
        bitcoin_symbol: Ticker symbol representing Bitcoin.
        is_bitcoin_in_top: Whether Bitcoin appears in the selected basket.

    Returns:
        Allocation as a decimal fraction (e.g. ``0.25``).
    """
    if symbol == bitcoin_symbol:
        return 0.04
    if is_bitcoin_in_top:
        return 0.24
    return 0.25


def get_top_assets(
    momentum_df: pd.DataFrame,
    bitcoin_symbol: str,
    top_n: int = 4,
) -> tuple[pd.DataFrame, bool]:
    """Select the top-ranked assets from a momentum-scored DataFrame.

    When Bitcoin is not in the top-*top_n* assets the function returns only
    *top_n - 1* assets, reserving one slot for a potential Bitcoin allocation
    managed separately.

    Args:
        momentum_df: Scored DataFrame as produced by :func:`get_assets_by_momentum`.
        bitcoin_symbol: Ticker symbol representing Bitcoin.
        top_n: Maximum number of assets to select.

    Returns:
        A tuple of (filtered DataFrame, is_bitcoin_in_top flag).
    """
    ranked = momentum_df.sort_values(by="momentum_score", ascending=False)
    top_symbols = ranked.head(top_n)["symbol"].unique()
    is_bitcoin_in_top = bitcoin_symbol in top_symbols

    if is_bitcoin_in_top:
        logger.info("Bitcoin is in the top assets", extra={"top_n": top_n})
        return ranked.head(top_n), True

    return ranked.head(top_n - 1), False


def pivot_points(
    df: pd.DataFrame,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Calculate classic pivot point and three support levels using prior-bar OHLC.

    Args:
        df: OHLCV DataFrame with columns ``High``, ``Low``, ``Close``.

    Returns:
        Tuple of Series ``(pivot_point, s1, s2, s3)``.
    """
    pp = (df["High"].shift(1) + df["Low"].shift(1) + df["Close"].shift(1)) / 3
    s1 = (2 * pp) - df["High"].shift(1)
    s2 = pp - (df["High"].shift(1) - df["Low"].shift(1))
    s3 = df["Low"].shift(1) - 2 * (df["High"].shift(1) - pp)
    return pp, s1, s2, s3


def swing_lows(df: pd.DataFrame, window: int = 5) -> pd.Series:
    """Identify local price minima (swing lows) within a rolling window.

    Uses :func:`scipy.signal.argrelextrema` to find indices where the low
    price is less than or equal to all neighbours within *window* bars.

    Args:
        df: OHLCV DataFrame containing a ``Low`` column.
        window: Number of bars on each side to compare against.

    Returns:
        Series of low prices at swing-low indices; all other positions are
        dropped (sparse series).
    """
    lows = df["Low"]
    pivots = argrelextrema(lows.values, np.less_equal, order=window)[0]
    out = pd.Series(index=df.index, data=np.nan)
    out.iloc[pivots] = lows.iloc[pivots]
    return out.dropna()


def clustered_lows(
    df: pd.DataFrame,
    bins: int = 50,
    threshold: int = 3,
) -> pd.DataFrame:
    """Group low prices into price-level support zones using a histogram.

    Bins the full history of ``Low`` values into *bins* equal-width buckets
    and merges adjacent buckets that each have at least *threshold* touches
    into a single support zone.

    Args:
        df: OHLCV DataFrame containing a ``Low`` column.
        bins: Number of histogram buckets.
        threshold: Minimum number of touches for a bucket to qualify as support.

    Returns:
        DataFrame with columns ``zone_low``, ``zone_high``, and ``touches``.
        Empty if no qualifying zones are found.
    """
    lows = df["Low"].dropna()
    if lows.empty:
        return pd.DataFrame(columns=["zone_low", "zone_high", "touches"])
    hist, edges = np.histogram(lows, bins=bins)
    zones: list[tuple[float, float, int]] = []
    run: list[Any] | None = None

    for i, hits in enumerate(hist):
        if hits >= threshold:
            if run is None:
                run = [edges[i], hits]
            else:
                run[1] += hits
        elif run:
            zones.append((run[0], edges[i], run[1]))
            run = None

    if run:  # trailing run reaching the last edge
        zones.append((run[0], edges[-1], run[1]))

    return pd.DataFrame(zones, columns=["zone_low", "zone_high", "touches"])
