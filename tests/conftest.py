"""Shared pytest fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pydantic_studio.tree.builder import reset_default_registry

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Reset the global default builder registry around every test.

    Without this fixture, a test that registers a custom builder leaves it
    in place for every subsequent test, leading to order-dependent failures.
    The reset runs both before and after each test so a crashing test cannot
    poison the next one even if the post-test reset would otherwise be skipped.
    """
    reset_default_registry()
    yield
    reset_default_registry()
