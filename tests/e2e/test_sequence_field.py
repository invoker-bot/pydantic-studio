"""E2E: add an item to a sequence field, edit the new item's value,
assert both server tree and preview update.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_add_remove_and_edit_sequence_item(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
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
