from __future__ import annotations

import socket
import threading
import time as _time
from contextlib import closing, contextmanager
from typing import TYPE_CHECKING

import uvicorn
from playwright.sync_api import Page, expect
from pydantic import BaseModel

from pydantic_studio import StudioServer
from pydantic_studio.variants import VariantRegistry, VariantSpec, build_variant_form_tree

if TYPE_CHECKING:
    from collections.abc import Iterator


class WebEmail(BaseModel):
    address: str = "ops@example.com"


class WebSlack(BaseModel):
    channel: str = "#ops"


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _serve_tree(tree) -> Iterator[str]:
    port = _find_free_port()
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


def test_web_variant_selector_switches_root_model(page: Page) -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=WebEmail, label="Email"),
                VariantSpec(id="slack", model=WebSlack, label="Slack"),
            ]
        ),
        selected_id="email",
        discriminator="class_name",
        persistence="inline_discriminator",
    )

    with _serve_tree(tree) as base_url:
        page.goto(f"{base_url}/")
        page.get_by_label("Variant").click()
        page.get_by_role("option", name="Slack").click()

        channel_input = page.get_by_role("textbox")
        expect(channel_input).to_be_visible(timeout=5000)
        channel_input.fill("#alerts")
        channel_input.blur()

        preview = page.get_by_test_id("tree-preview")
        expect(preview).to_contain_text("class_name: slack", timeout=5000)
        expect(preview).to_contain_text("channel: '#alerts'", timeout=5000)
