"""Example 5 - console-first editing.

This example is intentionally small so the default console flow is easy
to inspect. Each field is asked once, pressing Enter keeps the displayed
default/current value, and completion writes ``ConsoleSettings.yaml``.

Run with::

    python examples/05_console_prompts.py
    python examples/05_console_prompts.py console
    python examples/05_console_prompts.py tui
    python examples/05_console_prompts.py web
    python examples/05_console_prompts.py fill
"""

from __future__ import annotations

from typing import Literal

from _runner import run_demo
from pydantic import BaseModel, Field


class ConsoleSettings(BaseModel):
    service: str = Field(default="worker", description="Service name")
    port: int = Field(default=8080, ge=1, le=65535, description="Listen port")
    debug: bool = Field(default=False, description="Enable debug logging")
    level: Literal["debug", "info", "warn"] = Field(
        default="info",
        description="Log level",
    )


if __name__ == "__main__":
    run_demo(ConsoleSettings)
