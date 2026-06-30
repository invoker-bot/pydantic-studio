"""E2E: add an item to a sequence field, edit the new item's value,
assert both server tree and preview update.
"""

from __future__ import annotations

import re
import socket
import threading
import time as _time
from contextlib import closing, contextmanager
from typing import TYPE_CHECKING

import uvicorn
from playwright.sync_api import Page, expect
from pydantic import BaseModel, Field

from pydantic_studio import StudioServer, build_form_tree
from pydantic_studio.session import SubmitResult

if TYPE_CHECKING:
    from collections.abc import Iterator


class _SequenceSubmitItem(BaseModel):
    network: str = ""
    address: str = ""


class _SequenceSubmitSchema(BaseModel):
    items: list[_SequenceSubmitItem] = Field(default_factory=list)


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _serve_bracket_submit_error_tree() -> Iterator[str]:
    port = _find_free_port()
    tree = build_form_tree(
        _SequenceSubmitSchema,
        existing={"items": [{"network": "", "address": ""}]},
    )
    server = StudioServer(tree=tree, save_path=None)
    server.session.submit = lambda: SubmitResult(
        ok=False,
        errors=("network is required",),
        paths=("items[0].network",),
    )
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


def test_add_remove_and_edit_sequence_item(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")
    # Wait for the SPA to render the form
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    # Sanity: tags starts empty. The "+ Add" button should be present
    # under the tags field.
    add_button = page.get_by_role("button", name="+ Add str")
    expect(add_button).to_be_visible()

    # Click +Add. A new card appears at index 0 with a string input.
    add_button.click()

    # The new item is the only StringNode-shaped child of tags. Locate
    # the [0] header that SequenceField renders.
    item_header = page.get_by_text("[0]").first
    expect(item_header).to_be_visible(timeout=5000)

    # Fill the new item with a recognisable value so we can pin the
    # YAML preview's output deterministically (empty None items render
    # as just "- " which is fragile to assert on).
    new_tag_input = page.locator('input[id="field-tags.0"]')
    new_tag_input.fill("alpha-tag")
    new_tag_input.blur()

    # After the mutation round-trips, the YAML preview should show the
    # filled value as a list item under `tags:`.
    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text("- alpha-tag", timeout=5000)

    # Independent check: fetch /api/tree and confirm tags has 1 item
    # with the filled value.
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    tags_field = next(
        f for f in body["root"]["fields"] if f["name"] == "tags"
    )
    assert len(tags_field["items"]) == 1
    assert tags_field["items"][0]["value"] == "alpha-tag"


def test_readonly_sequence_descendant_disables_structural_controls(
    page: Page, readonly_tags_item_url: str
) -> None:
    page.goto(f"{readonly_tags_item_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    locked_input = page.locator('input[id="field-tags.0"]')
    expect(locked_input).to_have_value("locked-tag", timeout=5000)
    expect(locked_input).to_be_disabled()

    expect(page.get_by_role("button", name="move tags[0] down")).to_be_disabled()
    expect(page.get_by_role("button", name="remove tags[0]")).to_be_disabled()
    expect(page.get_by_role("button", name="+ Add str")).to_be_disabled()


def test_readonly_sequence_bracket_path_disables_structural_controls(
    page: Page, readonly_tags_bracket_item_url: str
) -> None:
    page.goto(f"{readonly_tags_bracket_item_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    locked_input = page.locator('input[id="field-tags.0"]')
    expect(locked_input).to_have_value("locked-tag", timeout=5000)
    expect(locked_input).to_be_disabled()

    expect(page.get_by_role("button", name="move tags[0] down")).to_be_disabled()
    expect(page.get_by_role("button", name="remove tags[0]")).to_be_disabled()
    expect(page.get_by_role("button", name="+ Add str")).to_be_disabled()


def test_bracket_submit_error_expands_and_highlights_sequence_item(
    page: Page,
) -> None:
    with _serve_bracket_submit_error_tree() as base_url:
        page.goto(f"{base_url}/")
        expect(page.get_by_role("heading", name="_SequenceSubmitSchema")).to_be_visible(
            timeout=5000
        )
        expect(page.get_by_label("network", exact=True)).to_have_count(0)

        page.get_by_role("button", name="Save").click()

        expect(page.get_by_test_id("submit-errors")).to_contain_text(
            "items[0].network",
            timeout=5000,
        )
        network_input = page.get_by_label("network", exact=True)
        expect(network_input).to_be_visible(timeout=5000)
        field = page.locator('[data-field-path="items.0.network"]')
        expect(field).to_have_class(re.compile("ring-red-400"))
