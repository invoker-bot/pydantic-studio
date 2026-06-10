"""End-to-end TUI flow tests — Claude Code /config-style journey.

Each test drives the StudioApp through a full user journey (mount,
navigate, edit, save) and asserts both the in-memory FormTree state
and the persisted YAML file. Catches regressions where unit tests
pass but the keystroke-driven path breaks.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field
from textual.widgets import Input, Static

from pydantic_studio import build_form_tree, load_yaml
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.screens import (
    ConfigScreen,
    ErrorsScreen,
)
from pydantic_studio.renderers.textual_.widgets.cells import BoolCell
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

        # Fill the required field the way a user does — through the
        # live Input. (Form mode treats the screen as the truth: a
        # programmatic tree.set_value would leave the stale on-screen
        # text to be flushed right back on Ctrl+S.)
        rows = list(app.screen.query(FieldRow))
        name_row = next(r for r in rows if r.node.name == "name")
        name_input = name_row.query_one(Input)
        name_input.value = "production"
        cell = name_row.query_one(".field-row--cell")
        result = cell.commit_pending()
        assert result is not None
        assert result.ok

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
async def test_required_text_field_can_be_edited_with_keyboard() -> None:
    """Form mode: the field is live on focus — just type, Enter commits."""
    tree = build_form_tree(_AppConfig)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow

        row = app.screen.query_one(FieldRow)

        await pilot.press("p", "r", "o", "d")
        await pilot.press("enter")
        await pilot.pause()

        assert tree.root.find("name").value == "prod"
        assert str(row.query_one(".field-row--label", Static).render()) == "name"


@pytest.mark.asyncio
async def test_text_input_is_visible_while_typing() -> None:
    """Editing must show typed text before Enter commits it."""
    tree = build_form_tree(_AppConfig)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()

        input_widget = app.screen.query_one(Input)
        assert input_widget.content_size.height >= 1

        await pilot.press("p", "r", "o", "d")
        await pilot.pause()
        assert input_widget.value == "prod"
        assert input_widget.content_size.height >= 1


@pytest.mark.asyncio
async def test_bool_field_toggles_with_space_and_arrows() -> None:
    """Form mode: Space (and Left/Right) edit bools; Tab moves on."""
    tree = build_form_tree(_AppConfig)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()

        await pilot.press("down")
        await pilot.pause()
        cell = app.screen.query_one(BoolCell)
        assert cell.value_text == "[ off ]"

        await pilot.press("space")
        await pilot.pause()
        assert tree.root.find("debug").value is True
        assert cell.value_text == "[ on  ]"
        assert "on" in str(cell.query_one(Static).render())


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
