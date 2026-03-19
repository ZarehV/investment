"""General-purpose utility helpers.

Provides deterministic hashing for investment records used as idempotency
keys in the journal.
"""

import base64
import hashlib
from typing import Any


def compute_hash(new_investment: dict[str, Any]) -> str:
    """Derive a stable, URL-safe identifier for an investment record.

    Concatenates the symbol, account, date, investment type, purchase price,
    and position size into a single string, then returns its Base64-encoded
    SHA-256 digest.  The same combination of inputs always produces the same
    key, making it safe to use as a deduplication token.

    Args:
        new_investment: Dictionary containing at least the keys
            ``symbol``, ``investment_account``, ``purchase_date``,
            ``investment_type``, ``purchase_price``, and ``position_size``.

    Returns:
        Base64-encoded SHA-256 hash string.
    """
    raw = (
        new_investment["symbol"]
        + new_investment["investment_account"]
        + new_investment["purchase_date"]
        + new_investment["investment_type"]
        + str(new_investment["purchase_price"])
        + str(new_investment["position_size"])
    )
    digest = hashlib.sha256(raw.encode()).digest()
    return base64.b64encode(digest).decode()
