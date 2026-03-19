import warnings
from datetime import datetime, timedelta
from investment.common.data_retrieval import get_stock_data
from investment.common.calculations import (
    calculate_atr,
    calculate_pivot_points,
    determine_take_profit,
    calculate_risk_reward_ratio,
    get_entry_price,
    calculate_ema,
    determine_stop_loss,
)
from investment.common.plotting import plot_data_with_indicators


def prep_position(
    ticker,
    days=5,
    interval="5m",
    investment_type="morning",
    testing=False,
    atr_window=14,
    ema_period=20,
    print_metrics=False,
    risk_level="low",
    position_type="long",
    stop_loss_type="pivot",
    take_profit_type="pivot",
    plot=True,
    debug=False,
):
    data = get_stock_data(ticker, days, interval)
    if data.empty:
        raise ValueError("No data found for the given ticker")
    with warnings.catch_warnings():
        data = data.drop(columns=["Close"]).copy()
        data = data.rename(columns={"Adj Close": "Close"}).copy()
        # data['Revenue'] = calculate_revenue(data['Close'])

    if testing:
        today = datetime.now()
        if investment_type == "morning":
            data_to_calc = data[data.index <= today.strftime("%Y-%m-%d 10:00:00")].copy()
        elif investment_type == "afternoon":
            data_to_calc = data[data.index <= today.strftime("%Y-%m-%d 15:00:00")].copy()
    else:
        data_to_calc = data.copy()

    data_to_calc["ATR"] = calculate_atr(data_to_calc, atr_window)
    data_to_calc["EMA"] = calculate_ema(data_to_calc["Close"], ema_period)
    pivot_point, support_1, support_2, resistance_1, resistance_2 = calculate_pivot_points(
        data_to_calc
    )

    if debug:
        print(data_to_calc.tail())

    if risk_level == "low":
        resistance = resistance_1
        support = support_1
    elif risk_level == "medium":
        resistance = resistance_2
        support = support_2

    if print_metrics:
        print(f"Pivot Point: {pivot_point:.2f}")
        print(f"Support 1: {support_1:.2f}")
        print(f"Support 2: {support_2:.2f}")
        print(f"Resistance 1: {resistance_1:.2f}")
        print(f"Resistance 2: {resistance_2:.2f}")

    if print_metrics:
        print(f"ATR: {data_to_calc['ATR'].iloc[-1]:.2f}")
        print(f"EMA: {data_to_calc['EMA'].iloc[-1]:.2f}")

    if stop_loss_type == "pivot":
        stop_loss = determine_stop_loss(
            reference=support, atr=data_to_calc["ATR"].iloc[-1], position_type=position_type
        )
    elif stop_loss_type == "ema":
        stop_loss = determine_stop_loss(
            reference=data_to_calc["EMA"].iloc[-1],
            atr=data_to_calc["ATR"].iloc[-1],
            position_type=position_type,
        )

    if take_profit_type == "pivot":
        take_profit = determine_take_profit(
            reference=pivot_point, atr=data_to_calc["ATR"].iloc[-1], position_type=position_type
        )
    elif take_profit_type == "ema":
        take_profit = determine_take_profit(
            reference=data_to_calc["EMA"].iloc[-1],
            atr=data_to_calc["ATR"].iloc[-1],
            position_type=position_type,
        )
    elif take_profit_type == "closing":
        take_profit = determine_take_profit(
            reference=data_to_calc["data_to_calc"].iloc[-1],
            atr=data_to_calc["ATR"].iloc[-1],
            position_type=position_type,
        )
    elif take_profit_type == "resistance":
        take_profit = resistance

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
