"""Unit tests for get_short_term_momentum_score().

All tests use synthetic DataFrames — no network calls are made.
"""

import pandas as pd
import pytest

from investment.strategies.common import get_short_term_momentum_score


def _make_closes(prices: dict[str, list[float]], n_days: int = 40) -> pd.DataFrame:
    """Build a closing-price DataFrame from per-symbol price lists.

    Args:
        prices: Mapping of symbol → list of closing prices (length == n_days).
        n_days: Number of trading-day rows.

    Returns:
        DataFrame with a DatetimeIndex and one column per symbol.
    """
    index = pd.bdate_range(end="2026-03-19", periods=n_days)
    return pd.DataFrame(prices, index=index, dtype=float)


def test_get_short_term_momentum_score_returns_correct_columns() -> None:
    """Output must contain exactly 'symbol' and 'momentum_score' columns."""
    closes = _make_closes({"AAA": list(range(1, 41)), "BBB": list(range(40, 0, -1))})
    result = get_short_term_momentum_score(["AAA", "BBB"], closes)
    assert list(result.columns) == ["symbol", "momentum_score"]


def test_get_short_term_momentum_score_sorted_descending() -> None:
    """Scores must be in non-ascending order."""
    closes = _make_closes(
        {
            "UP": list(range(1, 41)),
            "DOWN": list(range(40, 0, -1)),
            "FLAT": [20.0] * 40,
        }
    )
    result = get_short_term_momentum_score(["UP", "DOWN", "FLAT"], closes)
    scores = result["momentum_score"].tolist()
    assert scores == sorted(scores, reverse=True)


def test_get_short_term_momentum_score_ranks_higher_for_stronger_uptrend() -> None:
    """A strongly rising symbol must outrank a flat one."""
    closes = _make_closes(
        {
            "STRONG": [float(i) for i in range(10, 50)],
            "FLAT": [25.0] * 40,
        }
    )
    result = get_short_term_momentum_score(["STRONG", "FLAT"], closes)
    strong_score = float(result.loc[result["symbol"] == "STRONG", "momentum_score"].iloc[0])
    flat_score = float(result.loc[result["symbol"] == "FLAT", "momentum_score"].iloc[0])
    assert strong_score > flat_score


def test_get_short_term_momentum_score_skips_symbol_with_insufficient_data() -> None:
    """Symbols with fewer bars than max(roc_periods) + rsi_period are omitted."""
    # Only 10 bars — less than the 34 required by defaults (20 + 14)
    short_index = pd.bdate_range(end="2026-03-19", periods=10)
    closes = pd.DataFrame({"SHORT": [float(i) for i in range(1, 11)]}, index=short_index)
    result = get_short_term_momentum_score(["SHORT"], closes)
    assert result.empty


def test_get_short_term_momentum_score_handles_single_symbol() -> None:
    """A single-symbol universe must return one row without raising."""
    closes = _make_closes({"ONLY": list(range(1, 41))})
    result = get_short_term_momentum_score(["ONLY"], closes)
    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "ONLY"
    # With one symbol z-score is 0 for both components → composite score is 0
    assert result.iloc[0]["momentum_score"] == pytest.approx(0.0)


def test_get_short_term_momentum_score_custom_roc_periods() -> None:
    """Custom roc_periods are respected and do not raise."""
    closes = _make_closes({"AAA": list(range(1, 41)), "BBB": list(range(40, 0, -1))})
    result = get_short_term_momentum_score(["AAA", "BBB"], closes, roc_periods=[3, 7])
    assert set(result["symbol"]) == {"AAA", "BBB"}


def test_get_short_term_momentum_score_missing_symbol_in_closes() -> None:
    """Symbols absent from closes are silently skipped."""
    closes = _make_closes({"AAA": list(range(1, 41))})
    # Request both AAA and MISSING; only AAA is in closes
    result = get_short_term_momentum_score(["AAA", "MISSING"], closes)
    assert set(result["symbol"]) == {"AAA"}
