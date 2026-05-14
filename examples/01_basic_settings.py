"""Example 1 — Basic primitives + Field constraints.

The minimum useful schema: str / int / float / bool / Decimal, plus the
constraint kinds the studio surfaces (``ge`` / ``le`` / ``min_length`` /
``pattern`` / ``multiple_of`` / ``max_digits``).

Run with::

    python examples/01_basic_settings.py            # default: tui
    python examples/01_basic_settings.py tui        # Textual terminal UI
    python examples/01_basic_settings.py web        # browser UI
    python examples/01_basic_settings.py show       # print form tree
    python examples/01_basic_settings.py fill       # print YAML stub

If pydantic-studio is not installed in editable mode, prefix with ``uv
run``: ``uv run python examples/01_basic_settings.py tui``.
"""

from __future__ import annotations

from decimal import Decimal

from _runner import run_demo
from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    """Application-wide settings with realistic constraints."""

    name: str = Field(
        description="Service identifier (lowercase letters and hyphens only)",
        min_length=3,
        max_length=32,
        pattern=r"^[a-z][a-z0-9-]*$",
    )
    workers: int = Field(
        default=4,
        description="Worker process count",
        ge=1,
        le=64,
    )
    sample_rate: float = Field(
        default=0.1,
        description="Telemetry sampling probability",
        ge=0.0,
        le=1.0,
    )
    debug: bool = Field(
        default=False,
        description="Verbose logging + assertions",
    )
    price_per_unit: Decimal = Field(
        default=Decimal("9.99"),
        description="Unit price (USD)",
        ge=Decimal("0.00"),
        max_digits=8,
        decimal_places=2,
    )


if __name__ == "__main__":
    run_demo(
        AppSettings,
        existing={
            "name": "my-service",
            "workers": 8,
            "sample_rate": 0.25,
            "debug": True,
            "price_per_unit": Decimal("19.95"),
        },
    )
