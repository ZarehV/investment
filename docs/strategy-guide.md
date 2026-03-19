# Investment Strategy Guide

This document is the authoritative reference for the investment platform's algorithms,
strategies, and architecture. It is intended for anyone who needs to understand how
momentum scores, support levels, and capital allocations are calculated.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Configuration](#configuration)
3. [Core Algorithms](#core-algorithms)
   - [Momentum Score](#momentum-score)
   - [Support Level 1 — Long-Term (90-Day, Clustered Lows)](#support-level-1--long-term-90-day-clustered-lows)
   - [Support Level 2 — Short-Term (15-Day, Swing Lows)](#support-level-2--short-term-15-day-swing-lows)
   - [Swing Lows](#swing-lows)
   - [Clustered Lows](#clustered-lows)
   - [Pivot Points](#pivot-points)
   - [ATR, Stop-Loss, and Take-Profit](#atr-stop-loss-and-take-profit)
4. [Strategies](#strategies)
   - [Momentum Driver](#momentum-driver)
   - [Sector Momentum](#sector-momentum)
   - [Individual Stocks](#individual-stocks)
5. [Intraday Scalping (ScalpingVWAPRSI)](#intraday-scalping-scalpingvwaprsi)
6. [Logging](#logging)
7. [Environment Variables](#environment-variables)
8. [Running the Project](#running-the-project)

---

## Architecture Overview

The project follows a **src-layout**:

```
src/investment/          # Importable package
├── common/              # Shared financial calculations and data access
│   ├── base_strategies.py   # CommonLogic and ScalpingVWAPRSI classes
│   ├── calculations.py      # ATR, EMA, pivot points, stop-loss, P&L
│   ├── data_retrieval.py    # yfinance wrappers
│   ├── journal.py           # Trade journal helpers
│   ├── recommendations.py   # Trade candidate filtering
│   ├── routines.py
│   ├── plotting.py
│   └── utils.py             # Hashing and position-sizing utilities
├── config/
│   └── config.yaml          # Strategy parameters
├── strategies/
│   ├── common.py            # Momentum scoring, support detection, allocation helpers
│   ├── momentum_driver.py   # Multi-asset momentum strategy
│   ├── sector_momentum.py   # Sector-rotation strategy
│   ├── individual_stocks.py # Individual-equity strategy
│   ├── momentum_rider.py    # Legacy prototype
│   └── execute_strategy.py
└── logging.py               # ECS-formatted structured logger

tests/
├── unit/
└── integration/
```

**Data source**: All market data is retrieved from Yahoo Finance via the `yfinance` library.

---

## Configuration

All strategy parameters live in `src/investment/config/config.yaml`. The file has
one top-level key per strategy (`momentumrider`, `sector_momentum`, `individual_stocks`).

| Parameter | Type | Description |
|---|---|---|
| `interval` | string | yfinance bar granularity used for momentum data (e.g. `1mo`) |
| `debug` | bool | When `true`, intermediate DataFrames are written to CSV |
| `score_threshold` | float | Minimum momentum score required to invest in an asset |
| `investment_capital` | float | Total capital to deploy per run (dollars) |
| `bitcoin_symbol` | string | Ticker that receives the fixed 4 % Bitcoin sleeve (Momentum Driver only) |
| `hold_symbol` | string | Ticker to accumulate when assets are below threshold (default `BSV`) |
| `top_n` | int | Maximum number of assets to select after ranking |
| `periods.months` | dict | Look-back horizons in months used for momentum (keys only; values are `null`) |
| `assets` | dict | Universe of ticker symbols (keys only; values are `null`) |

The configuration is loaded at runtime by `load_config()` in `src/investment/strategies/common.py`.
An alternative path may be supplied via the `CONFIG_PATH` environment variable.

---

## Core Algorithms

### Momentum Score

**Source**: `src/investment/strategies/common.py` — `get_return()` and `get_assets_by_momentum()`

The momentum score measures how strongly an asset has trended toward its current price
across several look-back windows. A higher score means the asset has appreciated more
consistently across all time horizons.

#### Step 1 — Build the return matrix (`get_return`)

For every historical closing price bar, compute the **cumulative return from that
bar to the current market price**:

```
return[t] = (current_price − price[t]) / price[t]
```

This produces a DataFrame where each cell answers the question: *"If I had bought
at time `t`, what would my return be today?"*

Note that this is **not** a period-to-period return. Every cell is anchored to the
current live price obtained from `yf.Ticker(symbol).info["regularMarketPrice"]`.

#### Step 2 — Score each symbol (`get_assets_by_momentum`)

Given a list of look-back periods `P = [p₁, p₂, …, pₙ]` (in bars), the momentum
score for symbol `s` is the **arithmetic mean** of the cumulative returns at each
look-back horizon:

```
score(s) = ( return[−p₁] + return[−p₂] + … + return[−pₙ] ) / n
```

where `return[−p]` is the return stored at the bar `p` positions from the end of
the series — i.e. the return earned since `p` bars ago.

With the default configuration `P = [3, 6, 9, 12]` monthly bars:

```
score(s) = (R₃ᵐᵒ + R₆ᵐᵒ + R₉ᵐᵒ + R₁₂ᵐᵒ) / 4
```

where:

- `R₃ᵐᵒ` = return from 3 months ago to today
- `R₆ᵐᵒ` = return from 6 months ago to today
- `R₉ᵐᵒ` = return from 9 months ago to today
- `R₁₂ᵐᵒ` = return from 12 months ago to today

A symbol requires at least `total_periods` (default 12) non-null observations to
be scored; symbols with fewer observations are skipped.

#### Step 3 — Rank and filter

The resulting scores are sorted descending. Each strategy then:

1. Selects the top-N symbols.
2. Discards any symbol whose score is below `score_threshold` (those symbols'
   capital is redirected to `hold_symbol`).

---

### Support Level 1 — Long-Term (90-Day, Clustered Lows)

**Source**: `src/investment/strategies/momentum_driver.py` (and the equivalent
function in `sector_momentum.py` and `individual_stocks.py`), using helpers from
`src/investment/strategies/common.py`.

**Purpose**: Used for **bi-weekly rebalancing decisions** — i.e. determining whether
a position should be rebalanced or exited at the next scheduled review.

#### Calculation

1. Fetch 90 calendar days of daily OHLCV data for the symbol.
2. Identify all swing lows in that window using [`swing_lows()`](#swing-lows).
3. Cluster all daily Low prices into zones using [`clustered_lows()`](#clustered-lows).
4. **If qualifying zones exist**:
   - Select the zone with the highest touch count (most price revisits).
   - Support price = midpoint of that zone's boundaries:
     ```
     support_long = (zone_low + zone_high) / 2
     ```
   - The reference date is the last date a swing low fell inside that zone.
5. **If no qualifying zones exist** (price history is too sparse or volatile):
   - Fall back to the global minimum swing low over the 90-day window.
   - Support price = that minimum swing low price.
   - The reference date is the date of that minimum.

The logic is identical across all three strategies.

---

### Support Level 2 — Short-Term (15-Day, Swing Lows)

**Source**: Same strategy files as above.

**Purpose**: Used for **weekly stop-loss adjustments** — a tighter, more responsive
floor for the current week's risk management.

#### Calculation

1. Fetch 15 calendar days of daily OHLCV data for the symbol.
2. Identify all swing lows in that window using [`swing_lows()`](#swing-lows).
3. Support price = the **minimum** of all swing low prices found:
   ```
   support_short = min(swing_lows)
   ```
4. The reference date is the date on which that minimum swing low occurred.

Because the 15-day window is narrow, the histogram-based clustering used for the
long-term support would rarely find enough touches to form a zone; the raw swing low
minimum is therefore used directly.

---

### Swing Lows

**Source**: `src/investment/strategies/common.py` — `swing_lows(df, window=5)`

Identifies local price minima in the `Low` column of an OHLCV DataFrame.

#### Algorithm

Uses `scipy.signal.argrelextrema` with `np.less_equal` as the comparator:

```
A bar at index i is a swing low if:
  Low[i] <= Low[j]  for all j in [i − window, i + window]
```

In other words, the bar's low must be the lowest (or tied for lowest) among all
bars within `window` bars on either side. The default `window=5` means each candidate
bar is compared against its 5 immediate predecessors and 5 immediate successors —
a total neighbourhood of 11 bars.

The function returns a sparse Series containing only the confirmed swing low prices;
all other positions are dropped.

---

### Clustered Lows

**Source**: `src/investment/strategies/common.py` — `clustered_lows(df, bins=50, threshold=3)`

Groups historical Low prices into support zones by detecting price ranges that the
market has visited repeatedly.

#### Algorithm

1. Collect all `Low` prices from the DataFrame.
2. Build a **histogram** with `bins` equal-width buckets spanning the full price range.
3. A bucket qualifies as support if it has at least `threshold` touches (bars whose
   Low falls in that bucket).
4. **Merge adjacent qualifying buckets** into a single zone. This prevents two
   neighbouring price buckets from being reported as separate supports when they are
   really one continuous area.
5. Return a DataFrame with columns `zone_low`, `zone_high`, and `touches` for each
   merged zone.

#### Example

Suppose the Low prices over 90 days produce this histogram (simplified):

```
Price range    Touches
$98–$100          1      ← below threshold, ignored
$100–$102         4      ← qualifies
$102–$104         5      ← qualifies, adjacent → merged into one zone [$100–$104, 9 touches]
$104–$106         1      ← below threshold, ignored
$118–$120         3      ← qualifies, isolated → zone [$118–$120, 3 touches]
```

With `threshold=3`, the result is two support zones:

| zone_low | zone_high | touches |
|----------|-----------|---------|
| 100.00   | 104.00    | 9       |
| 118.00   | 120.00    | 3       |

When selecting the long-term support, the zone with `touches=9` wins, and the support
price becomes `(100 + 104) / 2 = 102.00`.

---

### Pivot Points

Two implementations are used in the codebase for different purposes.

#### Series-based (rolling) — `pivot_points()` in `strategies/common.py`

Produces a time series of pivot points and supports using each bar's **prior bar**
OHLC (shifted by 1):

```
PP  = (High[-1] + Low[-1] + Close[-1]) / 3
S1  = (2 × PP) − High[-1]
S2  = PP − (High[-1] − Low[-1])
S3  = Low[-1] − 2 × (High[-1] − PP)
```

Returns a tuple of four Series `(PP, S1, S2, S3)`.

#### Scalar (single session) — `calculate_pivot_points()` in `common/calculations.py`

Uses the second-to-last bar (`iloc[-2]`) — the most recently **completed** session —
and returns scalar values along with resistance levels:

```
PP  = (High + Low + Close) / 3        (prior completed session)
S1  = (2 × PP) − High
S2  = PP − (High − Low)
R1  = (2 × PP) − Low
R2  = PP + (High − Low)
```

Returns `(PP, S1, S2, R1, R2)`.

---

### ATR, Stop-Loss, and Take-Profit

**Source**: `src/investment/common/calculations.py`

#### Average True Range (ATR)

Standard 14-period ATR computed via the `ta` library:

```python
calculate_atr(data, window=14)
```

For intraday data, `calculate_daily_atr()` resamples to daily bars first and uses a
window proportional to the number of available days (`period = max(1, len(days) × 0.1)`).

#### Stop-Loss

```
Long:   stop_loss = reference − (atr_multiplier × ATR)   [default multiplier: 3.0]
Short:  stop_loss = reference + (atr_multiplier × ATR)
```

`reference` is typically a support level or the entry price.

#### Take-Profit

```
Long:   take_profit = reference − (atr_multiplier × ATR)  [default multiplier: 1.5]
Short:  take_profit = reference + (atr_multiplier × ATR)
```

A pivot-aware variant picks the more aggressive of two candidates:

```
take_profit = max(PP + ATR × multiplier,  nearest resistance)
```

#### Risk/Reward Ratio

```
R/R = (take_profit − entry) / (entry − stop_loss)
```

---

## Strategies

All three strategies share the same two-phase structure:

1. **Momentum phase** — Score all symbols, select top-N, filter by threshold.
2. **Allocation phase** — For each selected symbol, fetch current price, compute both
   support levels, determine share count, and persist the allocation.

Capital for skipped symbols (below `score_threshold`) is consolidated and directed to
`hold_symbol` (BSV by default).

---

### Momentum Driver

**File**: `src/investment/strategies/momentum_driver.py`
**Entry point**: `momentum_driver_flow()`
**History file**: `momentum_driver_execution_history.csv`

#### Universe

| Ticker | Asset class |
|--------|-------------|
| VTI    | US total-market equities |
| VEA    | International developed equities |
| VWO    | Emerging-market equities |
| VGIT   | Intermediate-term US government bonds |
| SPTI   | Intermediate-term US Treasuries |
| BCI    | Broad commodity ETF |
| SGOL   | Physical gold |
| HODL   | Bitcoin ETF |
| BND    | Total US bond market |

#### Parameters (from `config.yaml`)

| Parameter | Value |
|---|---|
| `interval` | `1mo` |
| `score_threshold` | `0.04` |
| `investment_capital` | `$120,000` |
| `top_n` | `5` |
| `hold_symbol` | `BSV` |
| `bitcoin_symbol` | `HODL` |
| `periods` | `[3, 6, 9, 12]` months |
| Look-back window | 1.1 years of monthly data |

#### Allocation Logic

Bitcoin (HODL) always receives a **fixed 4 % sleeve** regardless of rank. The
remaining capital is split equally across the other selected assets:

| Scenario | Bitcoin allocation | Each other asset |
|---|---|---|
| Bitcoin is in the top-5 | 4 % | 24 % × 4 assets = 96 % |
| Bitcoin is not in top-5 | 4 % (still allocated) | 25 % × 4 assets = 100 % |

When Bitcoin is not ranked in the top 5, only 4 other assets are selected (top-4
from the rest of the universe), and each receives 25 % of capital. Bitcoin's 4 %
is taken as an additional allocation on top.

#### Per-asset output fields

| Field | Description |
|---|---|
| `price` | Current market price |
| `momentum_score` | Computed score |
| `amount_to_invest` | `capital × allocation_pct` |
| `num_shares` | `floor(amount_to_invest / price)` |
| `investment_pct` | Allocation fraction (0.04, 0.24, or 0.25) |
| `support_long` | Long-term support price (90-day clustered lows) |
| `support_long_date` | Date of the last swing low inside the best zone |
| `support_short` | Short-term support price (15-day swing low minimum) |
| `support_short_date` | Date of that minimum swing low |

---

### Sector Momentum

**File**: `src/investment/strategies/sector_momentum.py`
**Entry point**: `sector_momentum_flow()`
**History file**: `sector_momentum_execution_history.csv`

#### Universe — 11 SPDR Sector ETFs

| Ticker | Sector |
|--------|--------|
| XLK    | Technology |
| XLV    | Healthcare |
| XLF    | Financials |
| XLY    | Consumer Discretionary |
| XLP    | Consumer Staples |
| XLE    | Energy |
| XLI    | Industrials |
| XLB    | Materials |
| XLU    | Utilities |
| XLRE   | Real Estate |
| XLC    | Communication Services |

#### Parameters (from `config.yaml`)

| Parameter | Value |
|---|---|
| `interval` | `1mo` |
| `score_threshold` | `0.04` |
| `investment_capital` | `$100,000` |
| `top_n` | `4` (3 investing + 1 bitcoin placeholder — see note) |
| `hold_symbol` | `BSV` |
| `periods` | `[3, 6, 9, 12]` months |

#### Look-ahead bias prevention

Unlike the other strategies, the Sector Momentum strategy computes momentum using
closing data **through the last day of the previous calendar month** — not today:

```
end_date   = last day of previous month
start_date = end_date − 365 days
```

This ensures the signal cannot be contaminated by partial-month data and mirrors how
a practitioner would implement a monthly rebalancing rule.

#### Allocation

Each of the top-3 qualifying sectors receives a **fixed 33 % of capital**. If a
sector's score is below `score_threshold`, its 33 % slot is redirected to
`hold_symbol`.

---

### Individual Stocks

**File**: `src/investment/strategies/individual_stocks.py`
**Entry point**: `individual_stocks_flow()`
**History file**: `individual_stocks_execution_history.csv`

#### Universe (from `config.yaml`)

| Ticker |
|--------|
| SHLD   |
| XOP    |
| JEPI   |
| QQA    |

#### Parameters (from `config.yaml`)

| Parameter | Value |
|---|---|
| `interval` | `1mo` |
| `score_threshold` | `0.03` |
| `investment_capital` | `$100,000` |
| `hold_symbol` | `BSV` |
| `periods` | `[3, 6, 9, 12]` months |
| Look-back window | 1.1 years |

#### Allocation

Capital is split **equally across all configured symbols** regardless of rank:

```
allocation_pct = 100 / N    (where N = number of symbols)
```

There is no top-N filtering — all configured symbols are included. The momentum
ranking is printed for informational purposes but does not affect how many symbols
are invested.

---

## Intraday Scalping (ScalpingVWAPRSI)

**Source**: `src/investment/common/base_strategies.py`

The `ScalpingVWAPRSI` class generates entry/exit signals for intraday trading using
three indicators combined in sequence.

### Indicators

| Indicator | Parameters | Purpose |
|---|---|---|
| VWAP | — | Intraday trend direction |
| RSI | 16-period | Overbought / oversold filter |
| Bollinger Bands | Default `ta` settings | Breakout confirmation |

### VWAP trend classification (`_get_vwap_signal`)

| Signal value | Condition | Interpretation |
|---|---|---|
| `2` (uptrend) | Open and Close both above VWAP | Buyers in control |
| `1` (downtrend) | Open and Close both below VWAP | Sellers in control |
| `3` (indecision) | Both of the above are true simultaneously | Overlapping range |
| `0` (neutral) | Neither condition met | No clear bias |

### Combined signal (`_get_total_signals`)

| Signal | Condition |
|---|---|
| `2` (buy) | VWAP uptrend AND (Close ≤ lower Bollinger Band OR RSI < 45) |
| `1` (sell) | VWAP downtrend AND (Close ≥ upper Bollinger Band OR RSI > 55) |
| `0` (hold) | All other cases |

### Backtesting

`CommonLogic.backtest()` implements a simple long-only simulation: buy when
`Signal = 2`, sell when `Signal = 1`. P&L is accumulated on the position size.

---

## Logging

**Source**: `src/investment/logging.py`

All application code must use the project logger — never call `logging.getLogger()`
directly:

```python
from investment.logging import get_logger

logger = get_logger(__name__)
logger.info("Processing symbol", extra={"symbol": "VTI", "score": 0.12})
```

The logger produces **ECS (Elastic Common Schema)** compliant JSON output suitable
for ingestion into Elasticsearch / Kibana. Key fields:

| Field | Source |
|---|---|
| `@timestamp` | Current UTC time with timezone |
| `log.level` | Python log level |
| `log.logger` | Logger name (typically `__name__`) |
| `message` | Log message string |
| `service.name` | `ELASTIC_APM_SERVICE_NAME` env var, default `"investment"` |
| Any `extra` key | Passed through as top-level ECS fields |

Log level is controlled by the `LOG_LEVEL` environment variable (default `INFO`).

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_ENV` | No | `development` | Runtime environment tag |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `CONFIG_PATH` | No | Bundled `config.yaml` | Path to an alternative strategy config |
| `ELASTIC_APM_SERVICE_NAME` | No | `investment` | APM service identifier |
| `ELASTIC_APM_SECRET_TOKEN` | No | — | APM authentication token |
| `ELASTIC_APM_SERVER_URL` | No | — | APM server endpoint |
| `ELASTIC_APM_ENVIRONMENT` | No | — | APM environment tag |

---

## Running the Project

### Install dependencies

```bash
uv sync --all-groups
```

### Run a strategy

```bash
# Momentum Driver
uv run python -c "from investment.strategies.momentum_driver import momentum_driver_flow; momentum_driver_flow()"

# Sector Momentum
uv run python -c "from investment.strategies.sector_momentum import sector_momentum_flow; sector_momentum_flow()"

# Individual Stocks
uv run python -c "from investment.strategies.individual_stocks import individual_stocks_flow; individual_stocks_flow()"
```

### Run tests

```bash
uv run pytest
```

### Run with coverage

```bash
uv run pytest --cov=src/investment --cov-report=html
```

### Lint and format

```bash
uv run ruff format .
uv run ruff check --fix .
uv run mypy src/
```

### Security audit

```bash
uv run pip-audit
```

### Debug mode

Set `debug: true` in `config.yaml` for any strategy to dump intermediate DataFrames
to CSV files in the working directory:

- `momentum_rider_raw.csv` — raw closing prices
- `returns.csv` — return matrix
- `momentum_df.csv` — momentum scores (sector_momentum only)
