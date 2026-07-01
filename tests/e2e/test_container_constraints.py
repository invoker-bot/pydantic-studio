"""E2E: container min/max constraints disable structural controls."""

from __future__ import annotations

import socket
import threading
import time as _time
from contextlib import closing, contextmanager
from typing import TYPE_CHECKING

import uvicorn
from playwright.sync_api import Page, expect
from pydantic import BaseModel, Field

from pydantic_studio import StudioServer, build_form_tree

if TYPE_CHECKING:
    from collections.abc import Iterator


class _ContainerLimitSchema(BaseModel):
    tags: list[str] = Field(
        default_factory=lambda: ["alpha", "beta"],
        min_length=1,
        max_length=2,
    )
    env: dict[str, int] = Field(
        default_factory=lambda: {"one": 1},
        min_length=1,
        max_length=2,
    )


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _serve_tree() -> Iterator[str]:
    port = _find_free_port()
    tree = build_form_tree(_ContainerLimitSchema)
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

    deadline = _time.time() + 5.0
    while _time.time() < deadline:
        try:
            with closing(socket.create_connection(("127.0.0.1", port), timeout=0.2)):
                break
        except OSError:
            _time.sleep(0.05)
    else:
        raise RuntimeError(f"uvicorn never bound to :{port}")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        uvi.should_exit = True
        thread.join(timeout=2.0)


def test_container_constraint_controls_disable_at_boundaries(page: Page) -> None:
    with _serve_tree() as base_url:
        page.goto(f"{base_url}/")
        expect(page.get_by_role("heading", name="_ContainerLimitSchema")).to_be_visible(
            timeout=5000
        )

        expect(page.get_by_text("min 1")).to_have_count(2)
        expect(page.get_by_text("max 2")).to_have_count(2)

        tag_add = page.get_by_role("button", name="+ Add str")
        expect(tag_add).to_be_disabled()
        expect(page.get_by_role("button", name="remove tags[1]")).to_be_enabled()

        page.get_by_role("button", name="remove tags[1]").click()

        expect(page.get_by_text("1 item")).to_be_visible(timeout=5000)
        expect(tag_add).to_be_enabled()
        expect(page.get_by_role("button", name="remove tags[0]")).to_be_disabled()

        env_add = page.get_by_role("button", name="add env entry")
        expect(env_add).to_be_enabled()
        expect(page.get_by_role("button", name="remove entry one")).to_be_disabled()

        env_add.click()

        expect(page.get_by_text("2 entries")).to_be_visible(timeout=5000)
        expect(env_add).to_be_disabled()
        expect(page.get_by_role("button", name="remove entry one")).to_be_enabled()
