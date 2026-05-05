"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from pydantic_studio.tree.builder import reset_default_registry


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    """Reset the global default builder registry before every test.

    Without this fixture, a test that registers a custom builder leaves it
    in place for every subsequent test, leading to order-dependent failures.
    """
    reset_default_registry()
