"""Basic smoke tests for the investment package."""

import investment


def test_version_is_defined() -> None:
    """Package exposes a version string."""
    assert isinstance(investment.__version__, str)
    assert len(investment.__version__) > 0
