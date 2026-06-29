"""End-to-end test: load the SPA, edit a string field, assert both
the server-side tree AND the in-page preview update.

Per spec section 8 Phase 3 acceptance: 'Playwright test: load schema,
edit one field, see preview update.'
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_edit_string_field_updates_tree_and_preview(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")

    # Wait for React to mount the form. The 'name' input is the first
    # primitive field in _DemoSchema (see conftest.py).
    name_input = page.get_by_label("name", exact=True)
    expect(name_input).to_be_visible(timeout=5000)
    expect(name_input).to_have_value("demo-service")

    # Edit the field. fill() replaces the entire value, blur() commits
    # via the on-blur mutation in StringField.
    name_input.fill("edited-via-playwright")
    name_input.blur()

    # The preview pane should reflect the new value once the mutation
    # round-trips. Wait for it to update.
    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text("edited-via-playwright", timeout=5000)

    # And the server-side tree, fetched directly (bypassing the SPA),
    # should also show the new value.
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    assert response.status == 200
    body = response.json()
    name_field = next(
        f for f in body["root"]["fields"] if f["name"] == "name"
    )
    assert name_field["value"] == "edited-via-playwright"


def test_live_preview_renders_yaml_not_formtree_dump(
    page: Page, fastapi_url: str
) -> None:
    """The preview pane must show the effective config values as YAML
    (``key: value`` lines), NOT a JSON dump of the FormTree's internal
    metadata (kind/required/error/fields/value/default). Regression for
    a Phase-5 gap where App.tsx was JSON.stringify(data) of the raw
    FormTree response.
    """
    page.goto(f"{fastapi_url}/")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)
    preview = page.get_by_test_id("tree-preview")
    text = preview.inner_text()
    assert "name: demo-service" in text
    assert "workers: 4" in text
    assert '"kind"' not in text
    assert '"required"' not in text
    assert '"fields"' not in text
