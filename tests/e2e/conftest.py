"""Shared fixtures for the Playwright e2e tests: spin up uvicorn on a
fixed port with a known schema so the SPA has something to render +
mutate.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import closing
from typing import TYPE_CHECKING

import pytest
import uvicorn
from pydantic import BaseModel, Field

from pydantic_studio import StudioServer, build_form_tree

if TYPE_CHECKING:
    from collections.abc import Iterator


class _DemoSchema(BaseModel):
    """Schema the e2e tests drive. Edit cautiously - test assertions
    pin specific field names and values."""

    name: str = Field(default="demo-service", description="Service identifier")
    workers: int = Field(default=4, ge=1, le=64, description="Worker count")
    debug: bool = Field(default=False, description="Verbose logging")


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def fastapi_url() -> Iterator[str]:
    """Spin up uvicorn on a free port in a background thread.

    Each test gets the same server (session-scoped) - tests that mutate
    state are responsible for either resetting it or using values that
    don't collide.
    """
    port = _find_free_port()
    tree = build_form_tree(_DemoSchema)
    # Seed each field with its declared default. ``build_form_tree`` leaves
    # ``value`` as ``None`` (default-seeding was removed in Phase 6 house-
    # keeping); we set the values here so the rendered form mirrors what a
    # user sees after opening a config file with all defaults.
    tree.set_value("name", "demo-service")
    tree.set_value("workers", 4)
    tree.set_value("debug", False)
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
