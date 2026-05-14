"""Shared fixtures for the Playwright e2e tests: spin up uvicorn on a
fixed port with a known schema so the SPA has something to render +
mutate.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import closing
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, Literal

import pytest
import uvicorn
from pydantic import BaseModel, Field

from pydantic_studio import StudioServer, build_form_tree

if TYPE_CHECKING:
    from collections.abc import Iterator


class _LogLevel(str, Enum):
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


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def fastapi_url() -> "Iterator[str]":
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
    tree = build_form_tree(_DemoSchema)
    # Seed defaults so the SPA renders with values (Phase 6 housekeeping
    # removed default-seeding from build_form_tree). tags/env/metadata
    # start at default_factory empties; notifier is preselected by
    # UnionBuilder via isinstance against the EmailNotifier default.
    tree.set_value("name", "demo-service")
    tree.set_value("workers", 4)
    tree.set_value("debug", False)
    tree.set_value("level", _LogLevel.INFO)
    server = StudioServer(tree=tree, save_path=None)
    config = uvicorn.Config(
        server.app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    uvi = uvicorn.Server(config)
    thread = threading.Thread(target=uvi.run, daemon=True)
    thread.start()

    # Wait for the server to bind. Cap at ~5s.
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            with closing(socket.create_connection(("127.0.0.1", port), timeout=0.2)):
                break
        except OSError:
            time.sleep(0.05)
    else:
        raise RuntimeError(f"uvicorn never bound to :{port}")

    yield f"http://127.0.0.1:{port}"

    uvi.should_exit = True
    thread.join(timeout=2.0)
