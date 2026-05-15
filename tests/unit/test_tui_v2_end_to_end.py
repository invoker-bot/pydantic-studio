"""End-to-end TUI flow tests — Claude Code /config-style journey.

Each test drives the StudioApp through a full user journey (mount,
navigate, edit, save) and asserts both the in-memory FormTree state
and the persisted YAML file. Catches regressions where unit tests
pass but the keystroke-driven path breaks.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree, load_yaml
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.screens import (
    ConfigScreen,
    ErrorsScreen,
)
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView


class _Database(BaseModel):
    host: str = "localhost"
    port: int = 5432


class _AppConfig(BaseModel):
    name: str = Field(...)
    debug: bool = False
    db: _Database = _Database()


@pytest.mark.asyncio
async def test_required_field_visible_then_edit_then_save(tmp_path):
    """Full journey: missing-marker → edit required field → save → reload.

    Mirrors the Claude Code /config experience: the user sees the
    required field marked with an asterisk, types a value, saves,
    and the YAML on disk reflects the change.
    """
    save = tmp_path / "config.yaml"
    tree = build_form_tree(_AppConfig)
    app = StudioApp(tree=tree, save_path=save)
    async with app.run_test() as pilot:
        await pilot.pause()
        from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow

        rows = list(app.screen.query(FieldRow))
        # Order is [name (required), debug, db (group)] — verify marker.
        name_row = next(r for r in rows if r.node.name == "name")
        assert name_row.label_text.startswith("*"), (
            f"required+unset 'name' should show marker; got {name_row.label_text!r}"
        )

        # First save attempt: tree is invalid (name unset) → ErrorsScreen.
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, ErrorsScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen)
        assert not save.exists(), "Invalid save must not write a file"

        # Set the required field directly on the tree (the cell-edit path
        # is covered by test_tui_v2_cell_text.py; here we focus on
        # save + reload semantics).
        tree.set_value("name", "production")

        # Re-render so the marker drops. Force a recompose by re-querying.
        # The label_text property reflects current node state on each read.
        rows = list(app.screen.query(FieldRow))
        name_row = next(r for r in rows if r.node.name == "name")
        assert not name_row.label_text.startswith("*"), (
            "marker should drop after required field is set"
        )

        # Second save: tree is now valid → write succeeds.
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen), (
            "successful save should keep us on ConfigScreen"
        )
        assert save.exists(), "valid save must write the file"

    # Reload from disk and assert the value persisted.
    reloaded = load_yaml(save, _AppConfig)
    instance = reloaded.to_instance()
    assert instance.name == "production"
    assert instance.db.host == "localhost"
    assert instance.db.port == 5432


@pytest.mark.asyncio
async def test_drill_into_nested_group_edit_save():
    """Drill into nested group, mutate via tree API, return to root, save."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        save = Path(tmp) / "out.yaml"
        tree = build_form_tree(_AppConfig)
        tree.set_value("name", "alpha")
        app = StudioApp(tree=tree, save_path=save)
        async with app.run_test() as pilot:
            await pilot.pause()
            # _AppConfig fields: [name, debug, db] — drill into db (index 2).
            field_list = app.screen.query_one(FieldListView)
            field_list.action_cursor_down()
            field_list.action_cursor_down()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ConfigScreen)
            # We're now scoped to _Database fields. Verify breadcrumb.
            from pydantic_studio.renderers.textual_.widgets.breadcrumb import (
                Breadcrumb,
            )

            bc = app.screen.query_one(Breadcrumb)
            assert "db" in bc.label_text

            # Mutate while drilled-in.
            tree.set_value("db.host", "db.prod.internal")

            # Esc back to root.
            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()
            # Save from root.
            await pilot.press("ctrl+s")
            await pilot.pause()
            await pilot.pause()
            assert save.exists()

        reloaded = load_yaml(save, _AppConfig)
        instance = reloaded.to_instance()
        assert instance.db.host == "db.prod.internal"
