"""Standalone momentum-rider prototype (legacy reference implementation).

This module is a self-contained, simplified version of the momentum-driver
strategy.  It is kept for historical reference; the production strategy is
:mod:`investment.strategies.momentum_driver`.

The universe is hard-coded to the nine MomentumRider assets.  Momentum is
scored as the average of the 3-, 6-, 9-, and 12-month cumulative returns,
and the top-four assets are printed to stdout.
"""

from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from investment.logging import get_logger

logger = get_logger(__name__)

_SYMBOLS: list[str] = ["VTI", "VEA", "VWO", "VGIT", "SPTI", "BCI", "SGOL", "HODL", "BND"]
_LOOK_BACK_YEARS: float = 1.1
_TOP_N: int = 4
_INVESTMENT_CAPITAL: float = 100_000.0


def momentum_rider_flow() -> None:
    """Download monthly data, score momentum, and print the top-4 allocation."""
    start_date = datetime.today() - timedelta(days=365 * _LOOK_BACK_YEARS)

    logger.info(
        "Downloading monthly data",
        extra={"symbols": _SYMBOLS, "start_date": start_date.strftime("%Y-%m-%d")},
    )
    data = yf.download(
        _SYMBOLS,
        start=start_date.strftime("%Y-%m-%d"),
        progress=False,
    )["Close"]
    monthly_returns = data.pct_change().resample("ME").last()

    momentum_scores: dict[str, float] = {}
    for symbol in _SYMBOLS:
        last_12 = monthly_returns[symbol].dropna()[-12:]
        if len(last_12) < 12:
            continue
        avg_return = (
            (1 + last_12[-3:]).prod()
            - 1
            + (1 + last_12[-6:]).prod()
            - 1
            + (1 + last_12[-9:]).prod()
            - 1
            + (1 + last_12[-12:]).prod()
            - 1
        ) / 4
        momentum_scores[symbol] = avg_return

    momentum_df = (
        pd.DataFrame.from_dict(momentum_scores, orient="index", columns=["momentum_score"])
        .sort_values(by="momentum_score", ascending=False)
        .reset_index()
        .rename(columns={"index": "symbol"})
        .head(_TOP_N)
    )

    print("Momentum Rankings:\n")
    print(momentum_df)


def _get_investment(momentum_df: pd.DataFrame) -> pd.DataFrame:
    """Attach an investment-dollar column to *momentum_df*.

    Bitcoin (``HODL``) receives a 4 % allocation; all other assets share the
    remaining capital equally at 23 % each.

    Args:
        momentum_df: Top-ranked assets with a ``symbol`` column.

    Returns:
        The same DataFrame with an added ``investment`` column.
    """
    investment = _INVESTMENT_CAPITAL
    if len(momentum_df[momentum_df["symbol"] == "HODL"].index) > 0:
        momentum_df["investment"] = momentum_df.apply(
            lambda x: investment * 0.04 if x["symbol"] == "HODL" else investment * 0.23,
            axis=1,
        )
    return momentum_df


if __name__ == "__main__":
    momentum_rider_flow()
