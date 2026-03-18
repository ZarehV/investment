import os
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
from strategies.common import load_config, get_closing_data, get_return, \
    get_top_assets, get_assets_by_momentum, swing_lows, get_all_data

EXECUTION_HISTORY = 'momentum_driver_execution_history.csv'

def check_investment_percentage(symbol, bitcoin_symbol, is_bitcoin_in_top):
    if symbol == bitcoin_symbol:
        return 0.04
    elif symbol != bitcoin_symbol and is_bitcoin_in_top:
        return 0.24
    else:
        return 0.25

def prep_investment_breakdown(top_momentum_df, investment_capital, bitcoin_symbol, hold_symbol, score_threshold, is_bitcoin_in_top=False):
    investment_allocation = {}
    hold_folds = 0
    for index, row in top_momentum_df.iterrows():
        symbol = row['symbol']
        score = row['momentum_score']
        if score < score_threshold:
            print(f"Skipping {symbol} due to low momentum score: {score}")
            hold_folds += 1
            continue
        stock = yf.Ticker(symbol)
        price = stock.info['regularMarketPrice']

        start_date = datetime.today() - timedelta(days=15)
        data_df = get_all_data(symbol, start_date, '1d')
        swing_lows_df = swing_lows(data_df)

        investment_pct = check_investment_percentage(symbol, bitcoin_symbol, is_bitcoin_in_top)
        investment_allocation[symbol] = {
            'price': price,
            'momentum_score': score,
            'amount_to_invest': investment_capital * investment_pct,
            'num_shares': int((investment_capital * investment_pct) / price),
            'investment_pct': investment_pct,
            'support': swing_lows_df.min(),
            'support_date': swing_lows_df.idxmin(),

        }

    if hold_folds > 0:
        print(f"Investment folds: {hold_folds} for {hold_symbol}")
        stock = yf.Ticker(hold_symbol)
        price = stock.info['regularMarketPrice']
        start_date = datetime.today() - timedelta(days=15)
        data_df = get_all_data(hold_symbol, start_date, '1d')
        swing_lows_df = swing_lows(data_df)
        investment_pct = check_investment_percentage(hold_symbol, bitcoin_symbol, is_bitcoin_in_top)
        investment_pct = investment_pct * hold_folds
        investment_allocation[hold_symbol] = {
            'price': price,
            'momentum_score': 'N/A',
            'amount_to_invest': investment_capital * investment_pct,
            'num_shares': int((investment_capital * investment_pct) / price),
            'investment_pct': investment_pct,
            'support': swing_lows_df.min(),
            'support_date': swing_lows_df.idxmin(),

        }


    for symbol, allocation in investment_allocation.items():
        print(f"Investment for {symbol}:")
        print(f"  Momentum Score: {allocation['momentum_score']}")
        print(f"  Price: {allocation['price']}")
        print(f"  Amount to Invest: {allocation['amount_to_invest']}")
        print(f"  Number of Shares: {allocation['num_shares']}")
        print(f"  Investment Percentage: {allocation['investment_pct']}")
        print(f"  Support: {allocation['support']}")
        print(f"  Support Date: {allocation['support_date']}")

    if os.path.exists(EXECUTION_HISTORY):
        df = pd.DataFrame.from_dict(investment_allocation, orient='index')
        current = pd.read_csv(EXECUTION_HISTORY, index_col=0)
        df = pd.concat([current, df])
        df['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    else:
        df = pd.DataFrame.from_dict(investment_allocation, orient='index')
        df['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    df.to_csv(EXECUTION_HISTORY, index=True)

def momentum_driver_flow():
    config = load_config(os.getenv('CONFIG_PATH'))
    print("Loaded configuration")
    start_date = datetime.today() - timedelta(days=365 * 1.1)
    symbols = list(config['momentumrider']['assets'].keys())
    daily_data_pd = get_closing_data(symbols, start_date, config['momentumrider']['interval'])
    if config['momentumrider']['debug']:
        daily_data_pd.to_csv('momentum_rider_raw.csv')
    returns_pd = get_return(daily_data_pd)
    if config['momentumrider']['debug']:
        returns_pd.to_csv('returns.csv')

    momentum_df = get_assets_by_momentum(
        list(config['momentumrider']['assets'].keys()),
        returns_pd,
        list(config['momentumrider']['periods']['months'].keys()),
    )

    top_momentum_df, is_bitcoin_in_top = get_top_assets(
        momentum_df,
        config['momentumrider']['bitcoin_symbol'],
        config['momentumrider']['top_n']
    )

    prep_investment_breakdown(
        top_momentum_df,
        config['momentumrider']['investment_capital'],
        config['momentumrider']['bitcoin_symbol'],
        config['momentumrider']['hold_symbol'],
        config['momentumrider']['score_threshold'],
        is_bitcoin_in_top
    )
