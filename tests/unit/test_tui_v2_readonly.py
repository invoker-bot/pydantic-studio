"""readonly_paths — fields the user may inspect but not edit.

Downstream CLIs own some field values (e.g. the HFT config name, which
the CLI force-overrides on save). Pre-v0.2 the TUI happily let users
edit them and the edit silently did nothing. Now the row is marked,
edits are rejected with a visible message, and the HelpBar says
read-only.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.widgets.cells import Cell
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow
from pydantic_studio.renderers.textual_.widgets.help_bar import HelpBar


class _Schema(BaseModel):
    path: str = "okx/okx"
    debug: bool = False
    name: str = "alpha"


@pytest.mark.asyncio
async def test_enter_on_readonly_row_does_not_edit() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None, readonly_paths={"path"})
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        cell = app.screen.query_one(FieldListView).query(Cell).first()
        assert cell.editing is False


@pytest.mark.asyncio
async def test_readonly_row_shows_marker_and_helper() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None, readonly_paths={"path"})
    async with app.run_test() as pilot:
        await pilot.pause()
        row = app.screen.query(FieldRow).first()
        assert "read-only" in row.label_text
        await pilot.press("enter")
        await pilot.pause()
        assert "read-only" in row.helper_text


@pytest.mark.asyncio
async def test_space_on_readonly_bool_does_not_toggle() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None, readonly_paths={"debug"})
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("space")
        await pilot.pause()
        assert tree._resolve_path("debug").value is False


@pytest.mark.asyncio
async def test_help_bar_mentions_readonly() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None, readonly_paths={"path"})
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.screen.query_one(HelpBar)
        assert "read-only" in bar.text


@pytest.mark.asyncio
async def test_editable_rows_unaffected() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None, readonly_paths={"path"})
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("space")
        await pilot.pause()
        assert tree._resolve_path("debug").value is True
