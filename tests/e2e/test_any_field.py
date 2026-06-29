"""E2E: AnyField - dict[str, Any] entries support the AnyField editor.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_any_field_parses_json_value(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    # metadata starts empty. Add an entry via the metadata's +Add button.
    # There are TWO +Add Entry buttons (env and metadata); use .all()
    # and pick the second.
    add_buttons = page.get_by_role("button", name="+ Add Entry").all()
    assert len(add_buttons) >= 2, (
        f"expected >=2 +Add Entry buttons, found {len(add_buttons)}"
    )
    add_buttons[1].click()   # the metadata one

    # The new entry's value field is an AnyField - takes raw text or JSON.
    # Locate the "any value (JSON or raw string)" placeholder input.
    any_input = page.get_by_placeholder(
        "any value (JSON or raw string)"
    ).first
    expect(any_input).to_be_visible(timeout=5000)

    # Type a JSON number, blur
    any_input.fill("42")
    any_input.blur()

    # Server tree should show the value as a number (not a string).
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    metadata_field = next(
        f for f in body["root"]["fields"] if f["name"] == "metadata"
    )
    assert len(metadata_field["entries"]) == 1
    _key_node, value_node = metadata_field["entries"][0]
    assert value_node["kind"] == "any"
    assert value_node["value"] == 42      # parsed as int, not string
    assert value_node["mode"] == "int"
