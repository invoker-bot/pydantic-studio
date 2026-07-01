"""Accessibility regressions for the React-backed web form."""

from __future__ import annotations

import asyncio
import socket
import threading
import time as _time
from contextlib import closing, contextmanager
from typing import TYPE_CHECKING

import uvicorn
from playwright.sync_api import Page, expect
from pydantic import BaseModel
from starlette.responses import JSONResponse

from pydantic_studio import StudioServer, build_form_tree

if TYPE_CHECKING:
    from collections.abc import Iterator


class _BrokenLoadSchema(BaseModel):
    name: str = "demo-service"


class _DelayedLoadSchema(BaseModel):
    name: str = "demo-service"


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _serve_server(server: StudioServer) -> Iterator[str]:
    port = _find_free_port()
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


@contextmanager
def _serve_broken_tree_load() -> Iterator[str]:
    tree = build_form_tree(_BrokenLoadSchema)
    server = StudioServer(tree=tree, save_path=None)

    @server.app.middleware("http")
    async def fail_tree_load(request, call_next):
        if request.url.path == "/api/tree":
            return JSONResponse(
                status_code=500,
                content={"detail": "tree unavailable"},
            )
        return await call_next(request)

    with _serve_server(server) as base_url:
        yield base_url


@contextmanager
def _serve_delayed_tree_load(delay_seconds: float = 3.0) -> Iterator[str]:
    tree = build_form_tree(_DelayedLoadSchema)
    server = StudioServer(tree=tree, save_path=None)

    @server.app.middleware("http")
    async def delay_tree_load(request, call_next):
        if request.url.path == "/api/tree":
            await asyncio.sleep(delay_seconds)
        return await call_next(request)

    with _serve_server(server) as base_url:
        yield base_url


def test_labels_reference_labelable_controls(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_role("heading", name="_DemoSchema")).to_be_visible(timeout=5000)

    broken = page.evaluate(
        """() => {
            const labelableTags = new Set([
                "BUTTON",
                "INPUT",
                "METER",
                "OUTPUT",
                "PROGRESS",
                "SELECT",
                "TEXTAREA",
            ]);
            return Array.from(document.querySelectorAll("label[for]"))
                .map((label) => {
                    const targetId = label.getAttribute("for");
                    const target = targetId ? document.getElementById(targetId) : null;
                    return {
                        label: label.textContent?.trim() ?? "",
                        targetId,
                        tagName: target?.tagName ?? null,
                    };
                })
                .filter((entry) => !entry.tagName || !labelableTags.has(entry.tagName));
        }"""
    )

    assert broken == []


def test_editor_and_preview_sections_are_named_regions(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_role("heading", name="_DemoSchema")).to_be_visible(timeout=5000)

    expect(page.get_by_role("region", name="_DemoSchema")).to_be_visible()
    expect(page.get_by_role("region", name="Live YAML preview")).to_be_visible()


def test_tree_loading_state_is_announced(page: Page) -> None:
    with _serve_delayed_tree_load() as base_url:
        page.goto(f"{base_url}/")

        expect(page.get_by_text("Loading tree...")).to_be_visible(timeout=1000)
        status = page.get_by_role("status")
        expect(status).to_contain_text("Loading tree...", timeout=1000)
        expect(status).to_have_attribute("aria-busy", "true")


def test_tree_load_failure_is_announced(page: Page) -> None:
    with _serve_broken_tree_load() as base_url:
        page.goto(f"{base_url}/")

        expect(page.get_by_text("Failed to load tree")).to_be_visible(timeout=12000)
        alert = page.get_by_role("alert")
        expect(alert).to_contain_text("Failed to load tree", timeout=5000)
        expect(alert).to_contain_text("GET /api/tree failed: HTTP 500")
        expect(alert).to_have_attribute("aria-atomic", "true")


def test_field_validation_errors_are_announced_as_alerts(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_role("heading", name="_DemoSchema")).to_be_visible(timeout=5000)

    workers = page.get_by_label("workers", exact=True)
    workers.fill("0")
    workers.blur()

    alert = page.get_by_role("alert")
    expect(alert).to_contain_text("must be >= 1", timeout=5000)
    expect(workers).to_have_attribute("aria-invalid", "true")

    describedby = workers.get_attribute("aria-describedby")
    assert describedby is not None
    describedby_target = page.locator(f'[id="{describedby}"]')
    expect(describedby_target).to_have_attribute("role", "alert")
    expect(describedby_target).to_contain_text("must be >= 1")

    workers.fill("2")

    expect(page.get_by_role("alert")).to_have_count(0)
    expect(workers).not_to_have_attribute("aria-invalid", "true")
    assert workers.get_attribute("aria-describedby") is None
