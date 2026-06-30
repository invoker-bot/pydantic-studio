"""Shared fixtures for the Playwright e2e tests: spin up uvicorn on a
fixed port with a known schema so the SPA has something to render +
mutate.
"""

from __future__ import annotations

import re
import socket
import threading
import time as _time
from contextlib import closing
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path as FsPath
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import UUID

import pytest
import uvicorn
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    HttpUrl,
    SecretBytes,
    SecretStr,
)

from pydantic_studio import StudioServer, build_form_tree

if TYPE_CHECKING:
    from collections.abc import Iterator


class _LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"


class _EmailNotifier(BaseModel):
    kind: Literal["email"] = "email"
    address: str = ""


class _SlackNotifier(BaseModel):
    kind: Literal["slack"] = "slack"
    channel: str = ""


_Notifier = Annotated[
    _EmailNotifier | _SlackNotifier, Field(discriminator="kind")
]


class _DemoSchema(BaseModel):
    """Schema the e2e tests drive. Edit cautiously - test assertions
    pin specific field names and values."""

    # Phase 3/4 fields
    name: str = Field(default="demo-service", description="Service identifier")
    workers: int = Field(default=4, ge=1, le=64, description="Worker count")
    debug: bool = Field(default=False, description="Verbose logging")
    level: _LogLevel = Field(default=_LogLevel.INFO, description="Log level")
    tags: list[str] = Field(default_factory=list, description="Free labels")
    env: dict[str, str] = Field(default_factory=dict, description="Env vars")
    notifier: _Notifier = Field(
        default_factory=_EmailNotifier, description="Where to alert"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata"
    )

    # Phase 5 fields - one per remaining primitive kind, in plan order
    ratio: float = Field(default=1.0, description="Phase 5 float field")
    price: Decimal = Field(default=Decimal("0.00"), description="Phase 5 decimal field")
    log_dir: FsPath = Field(default=FsPath("/tmp"), description="Phase 5 path field")
    homepage: HttpUrl = Field(
        default="https://example.com", description="Phase 5 url field"
    )
    contact: EmailStr = Field(
        default="ops@example.com", description="Phase 5 email field"
    )
    starts_on: date = Field(
        default=date(2025, 1, 1), description="Phase 5 date field"
    )
    cron_at: time = Field(
        default=time(2, 30, 0), description="Phase 5 time field"
    )
    last_run: datetime = Field(
        default=datetime(2025, 1, 1, 12, 0, 0),
        description="Phase 5 datetime field",
    )
    ttl: timedelta = Field(
        default=timedelta(hours=1), description="Phase 5 timedelta field"
    )
    bind_ip: IPv4Address = Field(
        default=IPv4Address("127.0.0.1"), description="Phase 5 ip_address field"
    )
    subnet: IPv4Network = Field(
        default=IPv4Network("10.0.0.0/24"), description="Phase 5 ip_network field"
    )
    request_id: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000000"),
        description="Phase 5 uuid field",
    )
    api_key: SecretStr = Field(
        default=SecretStr("placeholder"), description="Phase 5 secret str field"
    )
    api_key_bytes: SecretBytes = Field(
        default=SecretBytes(b"placeholder"), description="Phase 5 secret bytes field"
    )
    pattern_field: re.Pattern[str] = Field(
        default=re.compile(r"^[a-z]+$", re.IGNORECASE),
        description="Phase 5 pattern field",
    )
    salt: bytes = Field(default=b"\xde\xad\xbe\xef", description="Phase 5 bytes field")


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def fastapi_url() -> Iterator[str]:
    """Spin up uvicorn on a free port in a background thread, one per
    test function.

    Function-scoped (NOT session-scoped) so each test gets a fresh
    FormTree with the schema's defaults. Phase 4 added e2e tests that
    mutate state (add_item / add_entry / select_variant) — session-
    scoping caused order-dependent flakes (e.g., test_any_field leaving
    a metadata entry behind that test_mapping_field's `.first` selector
    then picked up by mistake). Adds ~50 ms of uvicorn-startup overhead
    per test; cheap insurance for test isolation.
    """
    port = _find_free_port()
    tree = build_form_tree(
        _DemoSchema,
        existing={
            "name": "demo-service",
            "workers": 4,
            "debug": False,
            "level": _LogLevel.INFO,
            "ratio": 1.0,
            "price": Decimal("0.00"),
            "log_dir": FsPath("/tmp"),
            "homepage": "https://example.com",
            "contact": "ops@example.com",
            "starts_on": date(2025, 1, 1),
            "cron_at": time(2, 30, 0),
            "last_run": datetime(2025, 1, 1, 12, 0, 0),
            "ttl": timedelta(hours=1),
            "bind_ip": IPv4Address("127.0.0.1"),
            "subnet": IPv4Network("10.0.0.0/24"),
            "request_id": UUID("00000000-0000-0000-0000-000000000000"),
            "api_key": "placeholder",
            "api_key_bytes": b"placeholder",
            "pattern_field": re.compile(r"^[a-z]+$", re.IGNORECASE),
            "salt": b"\xde\xad\xbe\xef",
        },
    )
    server = StudioServer(tree=tree, save_path=None)
    config = uvicorn.Config(
        server.app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        ws="none",
    )
    uvi = uvicorn.Server(config)
    thread = threading.Thread(target=uvi.run, daemon=True)
    thread.start()

    # Wait for the server to bind. Cap at ~5s.
    deadline = _time.time() + 5.0
    while _time.time() < deadline:
        try:
            with closing(socket.create_connection(("127.0.0.1", port), timeout=0.2)):
                break
        except OSError:
            _time.sleep(0.05)
    else:
        raise RuntimeError(f"uvicorn never bound to :{port}")

    yield f"http://127.0.0.1:{port}"

    uvi.should_exit = True
    thread.join(timeout=2.0)
