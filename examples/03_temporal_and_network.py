"""Example 3 — Temporal, network, and identifier types.

Less common but fully supported: datetime / date / time / timedelta,
UUID, IPv4Address / IPv4Network, pathlib.Path, EmailStr. All round-trip
through YAML/TOML/JSON via Pydantic's ISO 8601 / canonical string forms.

Run with::

    python examples/03_temporal_and_network.py        # default: console prompts
    python examples/03_temporal_and_network.py console
    python examples/03_temporal_and_network.py tui    # Textual terminal UI
    python examples/03_temporal_and_network.py web    # browser UI
    python examples/03_temporal_and_network.py show
    python examples/03_temporal_and_network.py fill
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from uuid import UUID

from _runner import run_demo
from pydantic import BaseModel, EmailStr, Field


class Maintenance(BaseModel):
    """A scheduled maintenance window for a service."""

    window_id: UUID = Field(description="Stable identifier for this window")
    starts_at: datetime = Field(description="Window start (ISO 8601 datetime)")
    on_date: date = Field(description="Calendar day")
    daily_cutoff: time = Field(description="Daily downtime start (local clock)")
    duration: timedelta = Field(
        description="Expected outage length (ISO 8601 duration, e.g. PT1H30M)"
    )
    operator_email: EmailStr = Field(description="On-call engineer email")
    bastion_ip: IPv4Address = Field(description="Bastion host address")
    allow_cidr: IPv4Network = Field(description="Allowed network range")
    runbook_path: Path = Field(description="Path to runbook on the operator's box")


if __name__ == "__main__":
    run_demo(
        Maintenance,
        existing={
            "window_id": UUID("12345678-1234-5678-1234-567812345678"),
            "starts_at": datetime(2026, 5, 14, 2, 0),
            "on_date": date(2026, 5, 14),
            "daily_cutoff": time(2, 0),
            "duration": timedelta(hours=1, minutes=30),
            "operator_email": "oncall@example.com",
            "bastion_ip": IPv4Address("10.0.0.1"),
            "allow_cidr": IPv4Network("10.0.0.0/8"),
            "runbook_path": Path("/opt/runbooks/db-maintenance.md"),
        },
    )
