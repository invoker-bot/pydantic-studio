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


def test_undo_and_redo_buttons_restore_browser_edits(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")

    name_input = page.get_by_label("name", exact=True)
    expect(name_input).to_be_visible(timeout=5000)
    expect(name_input).to_have_value("demo-service")

    name_input.fill("edited-via-history")
    name_input.blur()

    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text("edited-via-history", timeout=5000)

    page.get_by_role("button", name="Undo").click()

    expect(preview).to_contain_text("name: demo-service", timeout=5000)
    expect(name_input).to_have_value("demo-service")

    page.get_by_role("button", name="Redo").click()

    expect(preview).to_contain_text("edited-via-history", timeout=5000)
    expect(name_input).to_have_value("edited-via-history")


def test_history_buttons_reflect_available_actions(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/")

    name_input = page.get_by_label("name", exact=True)
    undo = page.get_by_role("button", name="Undo")
    redo = page.get_by_role("button", name="Redo")
    expect(name_input).to_be_visible(timeout=5000)
    expect(undo).to_be_disabled()
    expect(redo).to_be_disabled()

    name_input.fill("history-enabled")
    name_input.blur()

    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text("history-enabled", timeout=5000)
    expect(undo).to_be_enabled()
    expect(redo).to_be_disabled()

    undo.click()

    expect(preview).to_contain_text("name: demo-service", timeout=5000)
    expect(undo).to_be_disabled()
    expect(redo).to_be_enabled()

    redo.click()

    expect(preview).to_contain_text("history-enabled", timeout=5000)
    expect(undo).to_be_enabled()
    expect(redo).to_be_disabled()


def test_rejected_history_action_is_announced(page: Page, fastapi_url: str) -> None:
    # A rejected history action must be surfaced via role="alert". Force the
    # rejection deterministically by letting every mutation through except the
    # undo, which the (intercepted) server rejects. The previous version raced
    # a double-click to produce one success + one rejection, which was
    # timing-dependent — reliable only inside the warmed-up full suite and
    # flaky under React 19's more aggressive commit batching.
    def _reject_undo(route):
        if '"op":"undo"' in (route.request.post_data or ""):
            route.fulfill(
                status=400,
                content_type="application/json",
                json={"detail": "nothing to undo"},
            )
        else:
            route.continue_()

    page.route("**/api/mutations", _reject_undo)
    page.goto(f"{fastapi_url}/")

    name_input = page.get_by_label("name", exact=True)
    undo = page.get_by_role("button", name="Undo")
    redo = page.get_by_role("button", name="Redo")
    expect(name_input).to_be_visible(timeout=5000)

    name_input.fill("history-race")
    name_input.blur()

    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text("history-race", timeout=5000)
    expect(undo).to_be_enabled()

    undo.click()

    alert = page.get_by_role("alert")
    expect(alert).to_contain_text("Undo failed", timeout=5000)
    expect(alert).to_contain_text("nothing to undo")
    # The rejected undo leaves the tree untouched and history intact.
    expect(preview).to_contain_text("history-race")
    expect(undo).to_be_enabled()
    expect(redo).to_be_disabled()
