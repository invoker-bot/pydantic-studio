"""E2E coverage for clearing optional nested model groups."""

from __future__ import annotations

import socket
import threading
import time as _time
from contextlib import closing, contextmanager
from typing import TYPE_CHECKING

import uvicorn
from playwright.sync_api import Page, expect
from pydantic import BaseModel

from pydantic_studio import StudioServer, build_form_tree

if TYPE_CHECKING:
    from collections.abc import Iterator


class _OptionalGroupInner(BaseModel):
    host: str | None = None
    port: int = 5432


class _OptionalGroupSchema(BaseModel):
    primary: _OptionalGroupInner | None = None


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _serve_optional_group_tree() -> Iterator[str]:
    port = _find_free_port()
    tree = build_form_tree(
        _OptionalGroupSchema,
        existing={"primary": {"host": "db.internal", "port": 15432}},
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


def test_clear_optional_group_removes_existing_nested_model(page: Page) -> None:
    with _serve_optional_group_tree() as base_url:
        page.goto(f"{base_url}/")
        expect(page.get_by_role("heading", name="_OptionalGroupSchema")).to_be_visible(
            timeout=5000
        )
        preview = page.get_by_test_id("tree-preview")
        expect(preview).to_contain_text("db.internal", timeout=5000)

        clear = page.get_by_role("button", name="Clear primary")
        expect(clear).to_be_visible(timeout=5000)
        expect(clear).to_be_enabled()
        clear.click()

        expect(preview).not_to_contain_text("db.internal", timeout=5000)
        expect(page.get_by_text("not set — expand to configure")).to_be_visible(
            timeout=5000
        )
        expect(clear).to_be_disabled()

        response = page.context.request.get(f"{base_url}/api/tree")
        assert response.status == 200
        body = response.json()
        primary = next(f for f in body["root"]["fields"] if f["name"] == "primary")
        assert primary["omitted"] is True
        host = next(f for f in primary["fields"] if f["name"] == "host")
        port = next(f for f in primary["fields"] if f["name"] == "port")
        assert host["value"] is None
        assert port["value"] == 5432
