"""Market data retrieval utilities.

Wraps yfinance downloads with convenience helpers for intraday and
multi-day data, with a configurable time-of-day cutoff for pre-market
filtering.
"""

from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from investment.logging import get_logger

logger = get_logger(__name__)


def fetch_data_for_prep(
    symbols: list[str],
    days_to_analyze: int,
    granularity: str,
) -> pd.DataFrame:
    """Download historical data and trim it to a 09:50 AM intraday cutoff.

    Useful for morning-session analysis: all bars after 09:50 on the final
    day are excluded so that calculations remain reproducible regardless of
    the exact time the function is called.

    Args:
        symbols: Ticker symbols to download.
        days_to_analyze: Number of calendar days of history to fetch.
        granularity: yfinance interval string (e.g. ``"5m"``).

    Returns:
        OHLCV DataFrame truncated to bars on or before 09:50 AM of the last day.
    """
    now = datetime.now()
    start_date_dt = now - timedelta(days=days_to_analyze)
    end_date_dt = now + timedelta(days=1)
    start_date = start_date_dt.strftime("%Y-%m-%d")
    end_date = end_date_dt.strftime("%Y-%m-%d")

    logger.info(
        "Fetching data for prep",
        extra={
            "symbols": symbols,
            "start_date": start_date_dt.strftime("%Y-%m-%d %H:%M"),
            "granularity": granularity,
        },
    )

    data: pd.DataFrame = yf.download(symbols, start=start_date, end=end_date, interval=granularity)
    target_time = (end_date_dt - timedelta(days=1)).strftime("%Y-%m-%d") + " 09:50:00"
    return data.loc[data.index <= target_time]


def get_stock_data(ticker: str, days: int, interval: str = "5m") -> pd.DataFrame | None:
    """Download stock data for up to 29 calendar days of history.

    Selects the yfinance period string automatically:

    * ``days == 1``  →  ``period="1d"``
    * ``2 ≤ days ≤ 5``  →  ``period="5d"``
    * ``6 ≤ days ≤ 29``  →  ``period="1mo"``

    Args:
        ticker: Ticker symbol.
        days: Number of calendar days to look back.
        interval: yfinance interval string (default ``"5m"``).

    Returns:
        OHLCV DataFrame, or ``None`` if *days* > 29.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    logger.debug(
        "Fetching stock data",
        extra={
            "ticker": ticker,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        },
    )

    if days == 1:
        return yf.download(ticker, period="1d", interval=interval)  # type: ignore[return-value]
    if 1 < days < 6:
        stock_data: pd.DataFrame = yf.download(ticker, period="5d", interval=interval)
        return stock_data[stock_data.index >= start_date.strftime("%Y-%m-%d")]
    if 5 < days < 30:
        stock_data = yf.download(ticker, period="1mo", interval=interval)
        return stock_data[stock_data.index >= start_date.strftime("%Y-%m-%d")]

    logger.warning("Unsupported number of days", extra={"ticker": ticker, "days": days})
    return None


def get_data(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Fetch OHLCV history using yfinance's period/interval API.

    Args:
        ticker: Ticker symbol.
        period: yfinance period string (e.g. ``"1d"``, ``"5d"``, ``"1mo"``).
        interval: yfinance interval string (e.g. ``"5m"``, ``"1d"``).

    Returns:
        OHLCV DataFrame.
    """
    stock = yf.Ticker(ticker)
    return stock.history(period=period, interval=interval)  # type: ignore[return-value]


def get_intraday_data(ticker: str, interval: str = "5m") -> pd.DataFrame:
    """Fetch today's intraday OHLCV data for *ticker*.

    Args:
        ticker: Ticker symbol.
        interval: Bar size (default ``"5m"``).

    Returns:
        Intraday OHLCV DataFrame for the current trading session.
    """
    return get_data(ticker, "1d", interval=interval)


def get_previous_days_data(ticker: str, days: str = "5d", interval: str = "5m") -> pd.DataFrame:
    """Fetch recent multi-day intraday data for *ticker*.

    Args:
        ticker: Ticker symbol.
        days: yfinance period string (default ``"5d"``).
        interval: Bar size (default ``"5m"``).

    Returns:
        OHLCV DataFrame covering *days* of history.
    """
    return get_data(ticker, days, interval=interval)


def get_previous_day_data(
    ticker: str,
    period: str = "5d",
    interval: str = "5m",
) -> pd.Series:
    """Return the second-to-last bar of *ticker*'s recent history.

    Useful for accessing the previous session's final bar.

    Args:
        ticker: Ticker symbol.
        period: yfinance period string (default ``"5d"``).
        interval: Bar size (default ``"5m"``).

    Returns:
        A single-row Series corresponding to the penultimate bar.
    """
    stock = yf.Ticker(ticker)
    all_data = stock.history(period=period, interval=interval)
    return all_data.iloc[-2]  # type: ignore[return-value]


def split_data_at_time(
    data: pd.DataFrame,
    split_time: str = "10:10",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split *data* into a pre-cutoff slice and the full dataset.

    Args:
        data: Intraday OHLCV DataFrame with a timezone-aware datetime index.
        split_time: Wall-clock cutoff in ``"HH:MM"`` format (default ``"10:10"``).

    Returns:
        Tuple of ``(data_before_split, data)`` where *data_before_split*
        contains only bars whose time component is at or before *split_time*.
    """
    cutoff = pd.to_datetime(split_time).time()
    data_before_split = data[data.index.time <= cutoff]
    return data_before_split, data
