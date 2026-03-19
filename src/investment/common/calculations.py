"""Financial calculation utilities.

Provides price-level calculations (pivot points, ATR, EMA), risk-management
helpers (stop-loss, take-profit, risk/reward ratio), return statistics, and
P&L computation used across strategies and the position-preparation routine.
"""

import numpy as np
import pandas as pd
import ta
import yfinance as yf

from investment.common.journal import input_int_with_default
from investment.logging import get_logger

logger = get_logger(__name__)


def get_entry_price(data: pd.DataFrame, entry_type: str = "simple") -> float:
    """Return the entry price derived from *data*.

    Args:
        data: OHLCV DataFrame.
        entry_type: Method to use.  Currently only ``"simple"`` is supported,
            which returns the last closing price.

    Returns:
        Entry price as a float.

    Raises:
        NotImplementedError: If *entry_type* is not ``"simple"``.
    """
    if entry_type == "simple":
        return float(data["Close"].iloc[-1])
    raise NotImplementedError(f"Entry type '{entry_type}' is not implemented.")


def calculate_pivot_points(
    data: pd.DataFrame,
) -> tuple[float, float, float, float, float]:
    """Calculate the classic pivot point and two support/resistance levels.

    Uses the second-to-last bar (``iloc[-2]``) so that the values are based
    on the most recently *completed* session.

    Args:
        data: OHLCV DataFrame with ``High``, ``Low``, and ``Close`` columns.

    Returns:
        Tuple of ``(pivot_point, support_1, support_2, resistance_1, resistance_2)``.
    """
    high = float(data["High"].iloc[-2])
    low = float(data["Low"].iloc[-2])
    close = float(data["Close"].iloc[-2])
    pivot_point = (high + low + close) / 3
    support_1 = (2 * pivot_point) - high
    support_2 = pivot_point - (high - low)
    resistance_1 = (2 * pivot_point) - low
    resistance_2 = pivot_point + (high - low)
    return pivot_point, support_1, support_2, resistance_1, resistance_2


def calculate_revenue(close: pd.Series) -> pd.Series:
    """Calculate the daily return series using the *ta* library.

    Args:
        close: Series of closing prices.

    Returns:
        Series of daily returns.
    """
    return ta.others.daily_return(close)  # type: ignore[return-value]


def calculate_risk_reward_ratio(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
) -> float:
    """Compute the risk/reward ratio for a long position.

    Args:
        entry_price: Price at which the position is opened.
        stop_loss: Price level at which the position is closed at a loss.
        take_profit: Price level at which the position is closed at a profit.

    Returns:
        Ratio of potential profit to potential loss.  Returns ``inf`` when the
        potential loss is zero.
    """
    potential_loss = entry_price - stop_loss
    potential_profit = take_profit - entry_price
    if potential_profit == 0:
        return float("inf")
    return potential_profit / potential_loss


def determine_stop_loss(
    reference: float,
    atr: float,
    atr_multiplier: float = 3.0,
    position_type: str = "long",
) -> float:
    """Calculate a stop-loss price based on ATR distance from a reference level.

    Args:
        reference: Price level used as the anchor (e.g. pivot support).
        atr: Average True Range value.
        atr_multiplier: Number of ATR units below/above the reference.
        position_type: ``"long"`` subtracts from *reference*; ``"short"`` adds.

    Returns:
        Stop-loss price.

    Raises:
        ValueError: If *position_type* is not ``"long"`` or ``"short"``.
    """
    if position_type == "long":
        return reference - (atr_multiplier * atr)
    if position_type == "short":
        return reference + (atr_multiplier * atr)
    raise ValueError("position_type must be either 'long' or 'short'.")


def determine_take_profit(
    reference: float,
    atr: float,
    atr_multiplier: float = 1.5,
    position_type: str = "long",
) -> float:
    """Calculate a take-profit price based on ATR distance from a reference level.

    Args:
        reference: Price level used as the anchor (e.g. pivot point or EMA).
        atr: Average True Range value.
        atr_multiplier: Number of ATR units above/below the reference.
        position_type: ``"long"`` subtracts from *reference*; ``"short"`` adds.

    Returns:
        Take-profit price.

    Raises:
        ValueError: If *position_type* is not ``"long"`` or ``"short"``.
    """
    if position_type == "long":
        return reference - (atr_multiplier * atr)
    if position_type == "short":
        return reference + (atr_multiplier * atr)
    raise ValueError("position_type must be either 'long' or 'short'.")


def determine_take_profit_pivot(
    pivot_point: float,
    atr: float,
    resistance: float,
    multiplier: float = 2.0,
) -> float:
    """Return the more aggressive of an ATR-based and a resistance-based take-profit.

    Args:
        pivot_point: Classic pivot point price.
        atr: Average True Range value.
        resistance: Nearest resistance level.
        multiplier: ATR multiplier applied to the pivot.

    Returns:
        The higher of the two candidate take-profit prices.
    """
    take_profit_atr = pivot_point + (atr * multiplier)
    return max(take_profit_atr, resistance)


def calculate_ema(data: pd.Series, span: int) -> pd.Series:
    """Calculate the Exponential Moving Average for *data*.

    Args:
        data: Price series (typically closing prices).
        span: EMA span (number of periods).

    Returns:
        EMA series aligned with *data*.
    """
    return data.ewm(span=span, adjust=False).mean()  # type: ignore[return-value]


def calculate_atr(data: pd.DataFrame, window: int = 14) -> pd.Series:
    """Calculate the Average True Range using the *ta* library.

    Args:
        data: OHLCV DataFrame with ``High``, ``Low``, and ``Close`` columns.
        window: Look-back period for the ATR calculation.

    Returns:
        ATR series aligned with *data*.
    """
    return ta.volatility.AverageTrueRange(  # type: ignore[return-value]
        high=data["High"],
        low=data["Low"],
        close=data["Close"],
        window=window,
    ).average_true_range()


def get_last_closing_price(symbol: str) -> float:
    """Fetch the most recent closing price for *symbol* via yfinance.

    Args:
        symbol: Ticker symbol.

    Returns:
        Last closing price rounded to two decimal places.
    """
    stock = yf.Ticker(symbol)
    hist = stock.history(period="1d")
    return round(float(hist["Close"].iloc[0]), 2)


def get_recommended_take_profit(
    symbol: str,
    purchase_price: float,
    last_closing_price: float,
) -> float:
    """Return a take-profit 1 % above the last closing price.

    Args:
        symbol: Ticker symbol (unused; kept for API consistency).
        purchase_price: Original purchase price (unused; kept for API consistency).
        last_closing_price: Most recent closing price.

    Returns:
        Recommended take-profit rounded to two decimal places.
    """
    return round((last_closing_price * 0.01) + last_closing_price, 2)


def calculate_recommended_take_profit(
    symbol: str,
    purchase_price: float,
    stop_loss: float,
    risk_reward_ratio: float = 2.0,
) -> float:
    """Determine a take-profit using either a fixed R/R ratio or the last close.

    When *purchase_price* is above *stop_loss* the take-profit is set so that
    the trade achieves *risk_reward_ratio*.  Otherwise the user is prompted to
    confirm or override a 1 %-above-close recommendation.

    Args:
        symbol: Ticker symbol used to fetch the last closing price when needed.
        purchase_price: Position entry price.
        stop_loss: Stop-loss price.
        risk_reward_ratio: Target reward-to-risk multiple.

    Returns:
        Calculated or user-confirmed take-profit price.
    """
    if purchase_price > stop_loss:
        logger.debug(
            "Calculating take profit from stop loss",
            extra={"symbol": symbol, "risk_reward_ratio": risk_reward_ratio},
        )
        loss = purchase_price - stop_loss
        return purchase_price + loss * risk_reward_ratio

    last_closing_price = get_last_closing_price(symbol)
    logger.debug(
        "Purchase price below stop loss; prompting for take profit",
        extra={
            "symbol": symbol,
            "purchase_price": purchase_price,
            "stop_loss": stop_loss,
            "last_closing_price": last_closing_price,
        },
    )
    recommended = get_recommended_take_profit(symbol, purchase_price, last_closing_price)
    return float(input_int_with_default("Provide take profit or  ", recommended))


def calculate_profit_loss(
    purchase_price: float,
    exit_price: float,
    position_size: float,
) -> tuple[float, float]:
    """Calculate the absolute and percentage P&L for a closed position.

    Args:
        purchase_price: Price at which the position was opened.
        exit_price: Price at which the position was closed.
        position_size: Number of shares or units.

    Returns:
        Tuple of ``(profit_loss_dollars, profit_loss_pct)``.
    """
    initial_position = position_size * purchase_price
    final_position = position_size * exit_price
    pnl = final_position - initial_position
    return pnl, pnl / initial_position


def calculate_log_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Calculate log returns from a price series or DataFrame.

    Args:
        prices: Closing prices; may be a single Series or a multi-column DataFrame.

    Returns:
        Log-return Series or DataFrame with the first row dropped (NaN).
    """
    log_returns = np.log(prices / prices.shift(1))
    return log_returns.dropna()


def calculate_statistics(
    log_returns: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Compute correlation, volatility, and average return from log returns.

    Args:
        log_returns: Log-return DataFrame as produced by :func:`calculate_log_returns`.

    Returns:
        Tuple of ``(correlation_matrix, volatility, avg_return)`` where
        *avg_return* is expressed as a simple (non-log) return.
    """
    correlation = log_returns.corr()
    volatility = log_returns.std()
    avg_log_return = log_returns.mean()
    avg_return = np.exp(avg_log_return) - 1
    return correlation, volatility, avg_return


def get_avg_daily_return(avg_return: float, granularity: str) -> float:
    """Scale an intraday average return to a full trading day.

    Assumes 6.5 trading hours per day.

    Args:
        avg_return: Average return per bar at the given *granularity*.
        granularity: Bar length string (``"1m"``, ``"2m"``, ``"3m"``,
            ``"5m"``, ``"15m"``, ``"1h"``, or ``"1d"``).

    Returns:
        Estimated average daily return, or ``0`` for unsupported granularities.
    """
    scale: dict[str, float] = {
        "1m": 60 * 6.5,
        "2m": 30 * 6.5,
        "3m": 20 * 6.5,
        "5m": 12 * 6.5,
        "15m": 4 * 6.5,
        "1h": 6.5,
        "1d": 1.0,
    }
    if granularity not in scale:
        logger.warning("Unsupported granularity", extra={"granularity": granularity})
        return 0.0
    return avg_return * scale[granularity]


def calculate_daily_average_volume(data: pd.DataFrame) -> float:
    """Calculate the mean daily traded volume.

    Args:
        data: Intraday OHLCV DataFrame with a ``Volume`` column and a
            datetime index.

    Returns:
        Average daily volume across all complete trading days in *data*.
    """
    volume_daily = data["Volume"].resample("D").sum().dropna()
    return float(volume_daily.mean())


def calculate_daily_atr(data: pd.DataFrame, period_factor: float = 0.1) -> float:
    """Calculate the mean daily ATR for intraday price data.

    Resamples *data* to daily bars and uses a dynamic window proportional to
    the number of available days (minimum 1).

    Args:
        data: Intraday OHLCV DataFrame with ``High``, ``Low``, and
            ``Adj Close`` columns and a datetime index.
        period_factor: Fraction of available daily bars used as the ATR window.

    Returns:
        Mean ATR value across the resampled daily series.
    """
    data_daily = data.resample("D").agg({"High": "max", "Low": "min", "Adj Close": "last"}).dropna()
    period = max(1, int(len(data_daily) * period_factor))
    atr = ta.volatility.AverageTrueRange(
        high=data_daily["High"],
        low=data_daily["Low"],
        close=data_daily["Adj Close"],
        window=period,
    ).average_true_range()
    return float(atr.mean())
