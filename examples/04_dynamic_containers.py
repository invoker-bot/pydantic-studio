"""Example 4 — Containers, unions, discriminated unions, and ``Any``.

The dynamic side of the form tree:

* **list[T]** / **set[T]** / **tuple[T, ...]** / **dict[str, T]** —
  ``+ Add`` controls per-item and per-entry editing.
* **Optional[T]** (``T | None``) — collapses to ``T`` with
  ``required=False`` when the only "other" variant is ``None``.
* **Union[A, B]** — the renderer offers a variant picker and rebuilds
  the inner editor each time you switch.
* **Discriminated union** via ``Annotated[..., Field(discriminator=...)]``
  — same UX, with the discriminator field driving validation.
* **Any** — a single editor that infers the value's "mode" (str / int /
  list / dict / …) from what you type or paste.

Run with::

    python examples/04_dynamic_containers.py           # default: console prompts
    python examples/04_dynamic_containers.py console
    python examples/04_dynamic_containers.py tui       # Textual terminal UI
    python examples/04_dynamic_containers.py web       # browser UI
    python examples/04_dynamic_containers.py show
    python examples/04_dynamic_containers.py fill
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from _runner import run_demo
from pydantic import BaseModel, Field


class EmailNotifier(BaseModel):
    """Email-channel notification target."""

    kind: Literal["email"] = "email"
    address: str = Field(description="Recipient email")


class SlackNotifier(BaseModel):
    """Slack-channel notification target."""

    kind: Literal["slack"] = "slack"
    channel: str = Field(description="#channel-name", pattern=r"^#")
    webhook: str = Field(description="Slack incoming webhook URL")


# Discriminated union: Pydantic uses the `kind` literal to dispatch.
Notifier = Annotated[EmailNotifier | SlackNotifier, Field(discriminator="kind")]


class Job(BaseModel):
    """A scheduled job — exercises every dynamic container kind."""

    job_id: str = Field(description="Stable job identifier")

    # Sequence types
    tags: list[str] = Field(default_factory=list, description="Free-form labels")
    allowed_users: set[str] = Field(
        default_factory=set, description="User IDs allowed to trigger"
    )
    schedule: tuple[int, int, int] = Field(
        description="Cron-ish triple: (hour, minute, day_of_week)"
    )

    # Mapping
    env: dict[str, str] = Field(
        default_factory=dict, description="Extra environment variables"
    )

    # Optional (sugar for `Union[T, None]`)
    retry_count: int | None = Field(
        default=None, description="Override retry count (None means use system default)"
    )

    # Plain union — primitive variants
    timeout: int | float = Field(default=30, description="Timeout in seconds")

    # Discriminated union — repeated as a list.
    notifiers: list[Notifier] = Field(
        default_factory=list, description="Where to send completion alerts"
    )

    # Any — escape hatch for heterogeneous payloads
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata for downstream consumers"
    )


if __name__ == "__main__":
    run_demo(
        Job,
        existing={
            "job_id": "nightly-rollup",
            "tags": ["billing", "nightly"],
            "allowed_users": {"alice", "bob"},
            "schedule": (2, 30, 0),  # 02:30 on Sunday
            "env": {"TZ": "UTC", "LOG_LEVEL": "info"},
            "retry_count": 3,
            "timeout": 60.0,
            "notifiers": [
                {"kind": "email", "address": "ops@example.com"},
                {
                    "kind": "slack",
                    "channel": "#ops",
                    "webhook": "https://hooks.slack.com/...",
                },
            ],
            "metadata": {"owner": "platform", "priority": 5, "experimental": True},
        },
    )
