"""Position-preparation routine for intraday trades.

Fetches market data, computes technical indicators (ATR, EMA, pivot points),
determines stop-loss and take-profit levels, and optionally renders a
price chart with all key levels overlaid.
"""

import warnings
from datetime import datetime

from investment.common.calculations import (
    calculate_atr,
    calculate_ema,
    calculate_pivot_points,
    calculate_risk_reward_ratio,
    determine_stop_loss,
    determine_take_profit,
    get_entry_price,
)
from investment.common.data_retrieval import get_stock_data
from investment.common.plotting import plot_data_with_indicators
from investment.logging import get_logger

logger = get_logger(__name__)


def prep_position(
    ticker: str,
    days: int = 5,
    interval: str = "5m",
    investment_type: str = "morning",
    testing: bool = False,
    atr_window: int = 14,
    ema_period: int = 20,
    print_metrics: bool = False,
    risk_level: str = "low",
    position_type: str = "long",
    stop_loss_type: str = "pivot",
    take_profit_type: str = "pivot",
    plot: bool = True,
    debug: bool = False,
) -> tuple[float, float, float, float]:
    """Prepare a trade position by computing key price levels and risk metrics.

    Downloads recent price data for *ticker*, computes ATR and EMA, derives
    pivot-point support/resistance levels, and returns a fully specified trade
    setup (entry, stop-loss, take-profit, risk/reward ratio).

    Args:
        ticker: Ticker symbol to analyse.
        days: Number of calendar days of history to use.
        interval: Bar size for the downloaded data (default ``"5m"``).
        investment_type: ``"morning"`` caps data at 10:00 AM; ``"afternoon"``
            caps at 15:00 PM (only applies when *testing* is ``True``).
        testing: When ``True`` the dataset is trimmed to simulate a live
            intraday decision point.
        atr_window: Look-back period for ATR (default ``14``).
        ema_period: Span for the EMA calculation (default ``20``).
        print_metrics: When ``True`` log pivot-point and indicator values.
        risk_level: ``"low"`` uses first-level support/resistance;
            ``"medium"`` uses second-level.
        position_type: ``"long"`` or ``"short"`` — passed to stop-loss and
            take-profit helpers.
        stop_loss_type: ``"pivot"`` anchors the stop at the nearest support;
            ``"ema"`` anchors it at the EMA.
        take_profit_type: ``"pivot"``, ``"ema"``, or ``"resistance"``.
        plot: When ``True`` render an interactive Plotly chart.
        debug: When ``True`` log the tail of the data used for calculations.

    Returns:
        Tuple of ``(entry_price, stop_loss, take_profit, risk_reward_ratio)``
        all rounded to two decimal places.

    Raises:
        ValueError: If *ticker* returns no data.
    """
    data = get_stock_data(ticker, days, interval)
    if data is None or data.empty:
        raise ValueError(f"No data found for ticker '{ticker}'.")

    with warnings.catch_warnings():
        data = data.drop(columns=["Close"]).copy()
        data = data.rename(columns={"Adj Close": "Close"}).copy()

    if testing:
        today = datetime.now()
        cutoff = (
            today.strftime("%Y-%m-%d 10:00:00")
            if investment_type == "morning"
            else today.strftime("%Y-%m-%d 15:00:00")
        )
        data_to_calc = data[data.index <= cutoff].copy()
    else:
        data_to_calc = data.copy()

    data_to_calc["ATR"] = calculate_atr(data_to_calc, atr_window)
    data_to_calc["EMA"] = calculate_ema(data_to_calc["Close"], ema_period)
    pivot_point, support_1, support_2, resistance_1, resistance_2 = calculate_pivot_points(
        data_to_calc,
    )

    if debug:
        logger.debug("Data tail", extra={"tail": data_to_calc.tail().to_dict()})

    support = support_1 if risk_level == "low" else support_2
    resistance = resistance_1 if risk_level == "low" else resistance_2

    if print_metrics:
        logger.debug(
            "Pivot metrics",
            extra={
                "pivot_point": round(pivot_point, 2),
                "support_1": round(support_1, 2),
                "support_2": round(support_2, 2),
                "resistance_1": round(resistance_1, 2),
                "resistance_2": round(resistance_2, 2),
                "atr": round(float(data_to_calc["ATR"].iloc[-1]), 2),
                "ema": round(float(data_to_calc["EMA"].iloc[-1]), 2),
            },
        )

    atr_value = float(data_to_calc["ATR"].iloc[-1])

    if stop_loss_type == "pivot":
        stop_loss = determine_stop_loss(
            reference=support,
            atr=atr_value,
            position_type=position_type,
        )
    else:  # "ema"
        stop_loss = determine_stop_loss(
            reference=float(data_to_calc["EMA"].iloc[-1]),
            atr=atr_value,
            position_type=position_type,
        )

    if take_profit_type == "pivot":
        take_profit = determine_take_profit(
            reference=pivot_point,
            atr=atr_value,
            position_type=position_type,
        )
    elif take_profit_type == "ema":
        take_profit = determine_take_profit(
            reference=float(data_to_calc["EMA"].iloc[-1]),
            atr=atr_value,
            position_type=position_type,
        )
    elif take_profit_type == "resistance":
        take_profit = resistance
    else:
        take_profit = determine_take_profit(
            reference=pivot_point,
            atr=atr_value,
            position_type=position_type,
        )

    entry_price = get_entry_price(data_to_calc)
    risk_reward_ratio = calculate_risk_reward_ratio(entry_price, stop_loss, take_profit)

    if plot:
        plot_data_with_indicators(
            data,
            pivot_point,
            support_1,
            support_2,
            resistance_1,
            resistance_2,
            stop_loss,
            take_profit,
            f"{ticker} {investment_type} Trade",
        )

    return (
        round(entry_price, 2),
        round(stop_loss, 2),
        round(take_profit, 2),
        round(risk_reward_ratio, 2),
    )
