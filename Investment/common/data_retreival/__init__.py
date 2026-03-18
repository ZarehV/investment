import yfinance as yf
from datetime import datetime, timedelta

def fetch_data_for_prep(symbols, days_to_analyze, granularity):
    """
    Fetch historical market data for the given symbols with specified granularity.
    """
    now = datetime.now()
    start_date_dt = now - timedelta(days=days_to_analyze)
    start_date = start_date_dt.strftime('%Y-%m-%d')
    end_date_dt = now + timedelta(days=1)
    end_date = end_date_dt.strftime('%Y-%m-%d')
    data = yf.download(symbols, start=start_date, end=end_date, interval=granularity)
    target_time = (end_date_dt - timedelta(days=1)).strftime('%Y-%m-%d') + " 09:50:00"
    print(f"Getting data from {start_date_dt.strftime('%Y-%m-%d %H:%M')}:00 to {target_time}")
    data = data.loc[data.index <= target_time]
    return data


def get_stock_data(ticker, days, interval='5m'):
    """

    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    print(f'Getting data from {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}')
    if days == 1:
        return yf.download(ticker, period='1d', interval=interval)
    elif days > 1 and days < 6:
        stock_data = yf.download(ticker, period='5d', interval=interval)
        return stock_data[stock_data.index >= start_date.strftime("%Y-%m-%d")]
    elif days > 5 and days < 30:
        stock_data = yf.download(ticker, period='1mo', interval=interval)
        return stock_data[stock_data.index >= start_date.strftime("%Y-%m-%d")]
    else:
        print(f"Number of days {days} not supported")
        return None


def get_data(ticker, period, interval):
    stock = yf.Ticker(ticker)
    data = stock.history(period=period, interval=interval)
    return data

def get_intraday_data(ticker, interval='5m'):
    stock = yf.Ticker(ticker)
    return get_data(ticker, '1d', interval=interval)

def get_previous_days_data(ticker, days='5d', interval='5m'):
    data_pd = get_data(ticker, period, interval=interval)
    return data_pd

def get_previous_day_data(ticker, perdiod='5d', interval='5m'):
    stock = yf.Ticker(ticker)
    all_data = stock.history(period=perdiod, interval=interval)
    previous_day_data = all_data.iloc[-2]
    return previous_day_data

def split_data_at_time(data, split_time='10:10'):
    data_before_split = data[data.index.time <= pd.to_datetime(split_time).time()]
    return data_before_split, data


