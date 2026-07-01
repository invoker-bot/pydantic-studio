"""E2E: add an entry to a mapping field, rename its key, assert both
server tree and preview update.
"""

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


class _IntMappingSchema(BaseModel):
    ports: dict[int, str] = Field(default_factory=dict)


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


def test_add_entry_rename_key(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    # env starts empty - click + Add Entry under the env field
    add_button = page.get_by_role("button", name="+ Add Entry").first
    expect(add_button).to_be_visible()
    add_button.click()

    # MappingField generates a default key "key0" for the new entry.
    # The key input has aria-label="entry key".
    key_input = page.get_by_label("entry key").first
    expect(key_input).to_have_value("key0", timeout=5000)
    expect(page.get_by_role("button", name="remove entry key0")).to_be_visible()

    # Rename the key to "TZ"
    key_input.fill("TZ")
    key_input.blur()
    expect(page.get_by_role("button", name="remove entry TZ")).to_be_visible(
        timeout=5000
    )

    # Server should reflect the new key after the rename_key round-trip.
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    env_field = next(
        f for f in body["root"]["fields"] if f["name"] == "env"
    )
    # entries is a list of (k_node, v_node) tuples; the first key node's
    # value should be "TZ" after rename.
    assert len(env_field["entries"]) == 1
    k_node, _v_node = env_field["entries"][0]
    assert k_node["value"] == "TZ"

    # Preview is YAML; the new key surfaces as "  TZ:" under env.
    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text("TZ:", timeout=5000)


def test_add_entry_uses_typed_default_key_for_int_mapping(page: Page) -> None:
    tree = build_form_tree(_IntMappingSchema)

    with _serve_tree(tree) as base_url:
        page.goto(f"{base_url}/")
        expect(page.get_by_role("heading", name="_IntMappingSchema")).to_be_visible(
            timeout=5000
        )

        add_button = page.get_by_role("button", name="+ Add Entry").first
        add_button.click()

        key_input = page.get_by_label("entry key").first
        expect(key_input).to_have_value("0", timeout=5000)

        response = page.context.request.get(f"{base_url}/api/tree")
        body = response.json()
        ports_field = next(f for f in body["root"]["fields"] if f["name"] == "ports")
        assert len(ports_field["entries"]) == 1
        key_node, _value_node = ports_field["entries"][0]
        assert key_node["kind"] == "int"
        assert key_node["value"] == 0

        key_input.fill("443")
        key_input.blur()

        response = page.context.request.get(f"{base_url}/api/tree")
        body = response.json()
        ports_field = next(f for f in body["root"]["fields"] if f["name"] == "ports")
        key_node, _value_node = ports_field["entries"][0]
        assert key_node["value"] == 443

        preview = page.get_by_test_id("tree-preview")
        expect(preview).to_contain_text("443:", timeout=5000)


def test_readonly_mapping_descendant_disables_structural_controls(
    page: Page, readonly_env_entry_url: str
) -> None:
    page.goto(f"{readonly_env_entry_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    key_input = page.get_by_label("entry key").first
    expect(key_input).to_have_value("LOCKED", timeout=5000)
    expect(key_input).to_be_disabled()

    expect(page.get_by_role("button", name="remove entry LOCKED")).to_be_disabled()
    expect(page.get_by_role("button", name="+ Add Entry").first).to_be_disabled()
