"""Shared pytest fixtures and configuration."""

import pytest


@pytest.fixture
def app_env() -> str:
    """Return a consistent test environment name."""
    return "test"
