"""E2E for the SPA's Save / Cancel action bar.

Phases 1-5 shipped all field components but never wired a top-level
action bar to call ``POST /api/submit`` / ``POST /api/cancel``. Without
these, the SPA is a read-only editor: edits propagate to the FormTree
but the user has no way to commit them. These tests pin the action bar
shape and the success-state UX so the gap can't silently reopen.
"""

from __future__ import annotations

import socket
import threading
import time as _time
from contextlib import closing, contextmanager
from typing import TYPE_CHECKING, Literal

import uvicorn
from playwright.sync_api import Page, expect
from pydantic import BaseModel

from pydantic_studio import StudioServer, build_form_tree

if TYPE_CHECKING:
    from collections.abc import Iterator


class _BrokenSubmitSchema(BaseModel):
    name: str = "demo-service"


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _serve_broken_action_tree(action: Literal["submit", "cancel"]) -> Iterator[str]:
    port = _find_free_port()
    tree = build_form_tree(_BrokenSubmitSchema)
    server = StudioServer(tree=tree, save_path=None)

    def fail_action():
        raise RuntimeError(f"{action} backend unavailable")

    if action == "submit":
        server.session.submit = fail_action
    else:
        server.session.cancel = fail_action
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


def test_save_and_cancel_buttons_visible(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)
    expect(page.get_by_role("button", name="Save")).to_be_visible()
    expect(page.get_by_role("button", name="Cancel")).to_be_visible()


def test_save_click_marks_submitted_and_shows_success(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    page.get_by_role("button", name="Save").click()

    expect(page.get_by_text("Saved", exact=False)).to_be_visible(timeout=5000)
    status = page.get_by_role("status")
    expect(status).to_contain_text("Saved")
    expect(status).to_have_attribute("aria-atomic", "true")
    expect(page.get_by_role("button", name="Save")).to_have_count(0)


def test_cancel_click_shows_cancelled_state(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    page.get_by_role("button", name="Cancel").click()

    expect(page.get_by_text("Cancelled", exact=False)).to_be_visible(timeout=5000)
    status = page.get_by_role("status")
    expect(status).to_contain_text("Cancelled")
    expect(status).to_have_attribute("aria-atomic", "true")
    expect(page.get_by_role("button", name="Save")).to_have_count(0)


def test_save_transport_failure_is_announced(page: Page) -> None:
    with _serve_broken_action_tree("submit") as base_url:
        page.goto(f"{base_url}/")
        expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

        page.get_by_role("button", name="Save").click()

        alert = page.get_by_role("alert")
        expect(alert).to_contain_text("Save failed", timeout=5000)
        expect(alert).to_contain_text("HTTP 500")
        expect(page.get_by_role("button", name="Save")).to_be_enabled()


def test_cancel_transport_failure_is_announced(page: Page) -> None:
    with _serve_broken_action_tree("cancel") as base_url:
        page.goto(f"{base_url}/")
        expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

        page.get_by_role("button", name="Cancel").click()

        alert = page.get_by_role("alert")
        expect(alert).to_contain_text("Cancel failed", timeout=5000)
        expect(alert).to_contain_text("HTTP 500")
        expect(page.get_by_role("button", name="Cancel")).to_be_enabled()
