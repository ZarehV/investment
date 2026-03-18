import numpy as np
import yfinance as yf
import ta
from investment.common.journal import input_int_with_default

def get_entry_price(data, type='simple'):
    if type == 'simple':
        return data['Close'].iloc[-1]
    else:
        raise NotImplemented

def calculate_pivot_points(data):
    high = data['High'].max()
    low = data['Low'].min()
    close = data['Close'].iloc[-1]
    pivot_point = (high + low + close) / 3
    support_1 = (2 * pivot_point) - high
    support_2 = pivot_point - (high - low)
    resistance_1 = (2 * pivot_point) - low
    resistance_2 = pivot_point + (high - low)

    return pivot_point, support_1, support_2, resistance_1, resistance_2

def calculate_revenue(close):
    return ta.others.daily_return(close)

def calculate_risk_reward_ratio(entry_price, stop_loss, take_profit):
    potential_loss = entry_price - stop_loss
    potential_profit = take_profit - entry_price
    if potential_profit == 0:  # Avoid division by zero
        return float('inf')
    risk_reward_ratio = potential_profit / potential_loss
    return risk_reward_ratio

def determine_stop_loss(reference, atr, atr_multiplier=3, position_type='long'):
    if position_type == 'long':
        return reference - (atr_multiplier * atr)
    elif position_type == 'short':
        return reference + (atr_multiplier * atr)
    else:
        raise ValueError("Position type must be either 'long' or 'short'")

def determine_take_profit(reference, atr, atr_multiplier=1.5, position_type='long'):
    if position_type == 'long':
        return reference - (atr_multiplier * atr)
    elif position_type == 'short':
        return reference + (atr_multiplier * atr)
    else:
        raise ValueError("Position type must be either 'long' or 'short'")

def determine_take_profit_pivot(pivot_point, atr, resistance, multiplier=2):
    take_profit_atr = pivot_point + (atr * multiplier)
    take_profit_resistance = resistance  # Can also consider other resistance levels
    return max(take_profit_atr, take_profit_resistance)

def calculate_ema(data, span):
    return data.ewm(span=span, adjust=False).mean()

def calculate_atr(data, window=14):
    return ta.volatility.AverageTrueRange(high=data['High'], low=data['Low'], close=data['Close'], window=window).average_true_range()

def get_last_closing_price(symbol):
    # Fetch the stock data
    stock = yf.Ticker(symbol)

    # Get historical market data
    hist = stock.history(period="1d")

    # Get the last closing price
    last_closing_price = hist['Close'].iloc[0]
    return round(last_closing_price, 2)

def get_recommended_take_profit(symbol, purchase_price, last_closing_price):
    return round((last_closing_price * 0.01) + last_closing_price,2)

def calculate_recommended_take_profit(symbol, purchase_price, stop_loss, risk_reward_ratio=2):
    if purchase_price > stop_loss:
        print(f"Calculating take profit based on stop loss")
        loss = purchase_price - stop_loss
        win = loss * risk_reward_ratio
        return purchase_price + win
    elif purchase_price < stop_loss:
        print(f"Calculating take profit based on recommended or selected profit")
        last_closing_price = get_last_closing_price(symbol)
        print(f"Purchase price is of {purchase_price} lower that stop lost of {stop_loss}, last closing price for {symbol} was {last_closing_price}")
        recommended_take_profit = get_recommended_take_profit(symbol, purchase_price, last_closing_price)
        take_profit = input_int_with_default("Provide take profit or  ", recommended_take_profit)
        return take_profit

def calculate_porfit_loss(purchase_price, exit_price, position_size):
    initial_postion_dollars = position_size * purchase_price
    final_position_dollars = position_size * exit_price
    return final_position_dollars - initial_postion_dollars, (final_position_dollars - initial_postion_dollars) / initial_postion_dollars

def calculate_log_returns(prices):
    """
    Calculate log returns for the given price data.
    """
    log_returns = np.log(prices / prices.shift(1))
    return log_returns.dropna()

def calculate_statistics(log_returns):
    """
    Calculate correlation, volatility, and average return for the given log returns data.
    """
    correlation = log_returns.corr()
    volatility = log_returns.std()  # Volatility over the selected time interval
    avg_log_return = log_returns.mean()  # Average log return over the selected time interval
    avg_return = np.exp(avg_log_return) - 1
    return correlation, volatility, avg_return


def get_avg_daily_return(avg_return, granularity):
    if granularity == "1m":
        return avg_return * 60 * 6.5
    elif granularity == "2m":
        return avg_return * 30 * 6.5
    elif granularity == "3m":
        return avg_return * 20 * 6.5
    elif granularity == "5m":
        return avg_return * 12 * 6.5
    elif granularity == "15m":
        return avg_return * 4 * 6.5
    elif granularity == "1h":
        return avg_return * 6.5
    elif granularity == "1d":
        return avg_return
    else:
        print(f"Granularity {granularity} not supported")
        return 0


def calculate_daily_average_volume(data):
    """
    Calculate the daily average volume for the given volume data.
    """
    volume_daily = data['Volume'].resample('D').sum().dropna()
    avg_volume = volume_daily.mean()
    return avg_volume


def calculate_daily_atr(data, period_factor=0.1):
    """
    Calculate the daily Average True Range (ATR) for the given price data using ta library.
    """
    # Resample to daily data
    data_daily = data.resample('D').agg({
        'High': 'max',
        'Low': 'min',
        'Adj Close': 'last'
    }).dropna()

    # Determine the period based on the length of the dataset and the period_factor
    period = max(1, int(len(data_daily) * period_factor))  # Ensure at least a period of 1

    atr = ta.volatility.AverageTrueRange(
        high=data_daily['High'], low=data_daily['Low'], close=data_daily['Adj Close'], window=period
    ).average_true_range()

    return atr.mean()
