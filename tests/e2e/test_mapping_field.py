"""E2E: add an entry to a mapping field, rename its key, assert both
server tree and preview update.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


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

    # Rename the key to "TZ"
    key_input.fill("TZ")
    key_input.blur()

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
