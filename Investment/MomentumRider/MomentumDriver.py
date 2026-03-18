import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

symbols = ['VTI', 'VEA', 'VWO', 'VGIT', 'SPTI', 'BCI', 'SGOL', 'HODL', 'BND']
start_date = datetime.today() - timedelta(days=365 * 1.1)

# Get historical data
data = yf.download(symbols, start=start_date.strftime('%Y-%m-%d'), progress=False)['Close']
monthly_returns = data.pct_change().resample('ME').last()

# Calculate momentum scores
momentum_scores = {}
for symbol in symbols:
    last_12 = monthly_returns[symbol].dropna()[-12:]
    if len(last_12) < 12:
        continue
    avg_return = (
        last_12[-3:].mean() +
        last_12[-6:].mean() +
        last_12[-9:].mean() +
        last_12[-12:].mean()
    ) / 4
    momentum_scores[symbol] = avg_return

# Create DataFrame
momentum_df = pd.DataFrame.from_dict(momentum_scores, orient='index', columns=['momentum_score'])
momentum_df = momentum_df.sort_values(by='momentum_score', ascending=False).reset_index().rename(columns={'index': 'symbol'}).head(4)



def get_investment(momentum_df):
    investment = 100000
    if len(momentum_df[momentum_df['symbol'] == 'HOLD'].index()) > 0:
        momentum_df['investment'] = momentum_df.apply(
            lambda x: investment * 0.04 if x['symbol'] == 'HOLD' else investment * 0.23, axis=1)









print("Momentum Rankings:\n")
print(momentum_df)
