import os
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
from investment.strategies.common import load_config, get_closing_data, get_return, \
    get_assets_by_momentum, get_top_assets, get_all_data, swing_lows, get_symbol_current_data


EXECUTION_HISTORY = 'individual_stocks_execution_history.csv'

def check_investment_percentage(total_list):
    return 100 / total_list


def prep_investment_breakdown(symbols_list, investment_capital, hold_symbol, score_threshold):
    investment_pct = check_investment_percentage(len(symbols_list))
    investment_allocation = {}

    for symbol in symbols_list:

        stock = get_symbol_current_data(symbol)
        price = stock.info['regularMarketPrice']

        start_date = datetime.today() - timedelta(days=15)
        data_df = get_all_data(symbol, start_date, '1d')
        swing_lows_df = swing_lows(data_df)


        investment_allocation[symbol] = {
            'price': price,
            'amount_to_invest': investment_capital * investment_pct,
            'num_shares': int((investment_capital * investment_pct) / price),
            'investment_pct': investment_pct,
            'support': swing_lows_df.min(),
            'support_date': swing_lows_df.idxmin(),

        }




    for symbol, allocation in investment_allocation.items():
        print(f"Investment for {symbol}:")
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

def individual_stocks_flow():
    config = load_config(os.getenv('CONFIG_PATH'))
    print("Loaded configuration")
    start_date = datetime.today() - timedelta(days=365 * 1.1)
    symbols = list(config['individual_stocks']['assets'].keys())

    prep_investment_breakdown(
        symbols,
        config['individual_stocks']['investment_capital'],
        config['individual_stocks']['hold_symbol'],
        config['individual_stocks']['score_threshold'],
    )
