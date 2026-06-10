"""Form-mode paradigm pins: the focused field IS the editable field.

Replaces the modal-cell model (Enter to edit, Enter to commit, Esc to
leave) with the universal form habit:

- text-backed rows host a persistent Input — focus it and type
- Tab / Shift+Tab / Up / Down commit the pending value, then move
- Enter commits and advances to the next row
- Esc reverts the focused field to its value-on-focus
- Space toggles bools; Left/Right cycle bools, choices, union variants
- a commit that fails parsing/validation blocks the move and surfaces
  the error on the row
"""

from __future__ import annotations

from enum import StrEnum

import pytest
from pydantic import BaseModel
from textual.widgets import Input

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow


class _Level(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 5
    enabled: bool = False
    level: _Level = _Level.INFO


def _value(tree, path):
    return tree._resolve_path(path).value


@pytest.mark.asyncio
async def test_text_rows_host_persistent_inputs() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        first_row = app.screen.query(FieldRow).first()
        assert first_row.query(Input), (
            "text rows must render a persistent Input — no modal edit state"
        )


@pytest.mark.asyncio
async def test_typing_then_down_commits_without_enter() -> None:
    """Focus selects the text (web-form Tab habit); typing replaces it;
    moving away commits — no Enter required anywhere."""
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        for ch in "edited":
            await pilot.press(ch)
        await pilot.press("down")
        await pilot.pause()
        assert _value(tree, "name") == "edited"


@pytest.mark.asyncio
async def test_tab_commits_and_moves_to_next_row() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        for ch in "X":
            await pilot.press(ch)
        await pilot.press("tab")
        await pilot.pause()
        view = app.screen.query_one(FieldListView)
        assert _value(tree, "name") == "X"
        assert view._row_specs()[view.cursor].path == "count"


@pytest.mark.asyncio
async def test_enter_commits_and_advances() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        for ch in "renamed":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        view = app.screen.query_one(FieldListView)
        assert _value(tree, "name") == "renamed"
        assert view._row_specs()[view.cursor].path == "count"


@pytest.mark.asyncio
async def test_escape_reverts_pending_text() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        for ch in "zzz":
            await pilot.press(ch)
        await pilot.press("escape")
        await pilot.pause()
        assert app.is_running, "Esc with pending text must only revert the field"
        assert _value(tree, "name") == "alpha"
        row = app.screen.query(FieldRow).first()
        assert row.query_one(Input).value == "alpha"


@pytest.mark.asyncio
async def test_invalid_value_blocks_move_and_shows_error() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")  # -> count (int)
        await pilot.pause()
        for ch in "abc":
            await pilot.press(ch)
        await pilot.press("down")
        await pilot.pause()
        view = app.screen.query_one(FieldListView)
        assert view._row_specs()[view.cursor].path == "count", (
            "an unparsable value must keep the cursor on the field"
        )
        assert _value(tree, "count") == 5
        rows = list(app.screen.query(FieldRow))
        assert rows[view.cursor].helper_text, "the row must show why the move was blocked"


@pytest.mark.asyncio
async def test_space_toggles_bool_row() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down", "down")  # -> enabled
        await pilot.press("space")
        await pilot.pause()
        assert _value(tree, "enabled") is True


@pytest.mark.asyncio
async def test_left_right_cycle_choice_row() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down", "down", "down")  # -> level
        await pilot.press("right")
        await pilot.pause()
        assert _value(tree, "level") == _Level.WARN
        await pilot.press("left")
        await pilot.pause()
        assert _value(tree, "level") == _Level.INFO


@pytest.mark.asyncio
async def test_enter_on_bool_and_choice_advances() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down", "down")  # -> enabled (bool)
        await pilot.press("enter")
        await pilot.pause()
        view = app.screen.query_one(FieldListView)
        assert view._row_specs()[view.cursor].path == "level"
        assert _value(tree, "enabled") is False, "Enter advances; Space is the toggle"


@pytest.mark.asyncio
async def test_click_on_row_moves_cursor_and_focuses_input() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        rows = list(app.screen.query(FieldRow))
        target = rows[1].query_one(Input)
        target.focus()  # what a mouse click on the input does
        await pilot.pause()
        view = app.screen.query_one(FieldListView)
        assert view._row_specs()[view.cursor].path == "count"


@pytest.mark.asyncio
async def test_boundary_move_still_commits() -> None:
    """Moving 'off the edge' is still a blur — the pending value commits
    even when there is no row to move to (caught live: the boundary
    check used to short-circuit before the commit gate)."""
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        for ch in "boundary":
            await pilot.press(ch)
        await pilot.press("up")  # cursor already at row 0 — boundary move
        await pilot.pause()
        assert _value(tree, "name") == "boundary"


@pytest.mark.asyncio
async def test_ctrl_s_flushes_pending_text_before_submit(tmp_path) -> None:
    """Ctrl+S right after typing must save what the user sees on
    screen, not the last committed value."""
    import yaml as pyyaml

    save = tmp_path / "c.yaml"
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=save)
    async with app.run_test() as pilot:
        await pilot.pause()
        for ch in "fresh":
            await pilot.press(ch)
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert app.outcome.submitted is True
    assert pyyaml.safe_load(save.read_text())["name"] == "fresh"


@pytest.mark.asyncio
async def test_ctrl_s_with_invalid_pending_text_blocks_submit() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")  # -> count (int)
        await pilot.pause()
        for ch in "junk":
            await pilot.press(ch)
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.is_running, "invalid pending text must block the submit"
        assert _value(tree, "count") == 5
