"""Container drill-down tests for the TUI v2 ConfigScreen.

Pressing Enter on a row whose node is a Group / Sequence / Mapping /
Union container must push a new ConfigScreen scoped to that child.
Pressing Esc (with no edit in progress) pops back. The Breadcrumb on
the pushed screen reflects the full path from the root.

For M3 the drill-down lights up GroupNode. Sequence / Mapping / Union
are deferred to a later milestone; today their Enter still falls
through to the TextCell stub.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.screens import ConfigScreen
from pydantic_studio.renderers.textual_.widgets.breadcrumb import Breadcrumb
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView


class _Nested(BaseModel):
    api_key: str = "default-key"
    timeout: int = 30


class _Deep(BaseModel):
    label: str = "deep"


class _Mid(BaseModel):
    deep: _Deep = _Deep()
    flag: bool = False


class _Outer(BaseModel):
    name: str = "outer"
    nested: _Nested = _Nested()
    mid: _Mid = _Mid()


def _focus_row(field_list: FieldListView, index: int) -> None:
    """Move the FieldListView cursor to ``index`` by simulating arrow-down."""
    while field_list.cursor < index:
        field_list.action_cursor_down()


def _config_screen_depth(app: StudioApp) -> int:
    """Count ConfigScreen instances on the stack (ignores Textual's
    default Screen at index 0). Root mounted = 1; one drill = 2; etc.
    """
    return sum(1 for s in app.screen_stack if isinstance(s, ConfigScreen))


@pytest.mark.asyncio
async def test_enter_on_group_row_pushes_child_screen():
    """Cursor on a Group row + Enter → a new ConfigScreen is pushed."""
    tree = build_form_tree(_Outer)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        root_screen = app.screen
        assert _config_screen_depth(app) == 1
        field_list = app.screen.query_one(FieldListView)
        # _Outer fields: [name (str), nested (group), mid (group)] — index 1.
        _focus_row(field_list, 1)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        assert _config_screen_depth(app) == 2, (
            f"Enter on 'nested' should push a child ConfigScreen; "
            f"stack = {[type(s).__name__ for s in app.screen_stack]}"
        )
        assert app.screen is not root_screen
        bc = app.screen.query_one(Breadcrumb)
        assert "nested" in bc.label_text, (
            f"Child breadcrumb should include 'nested'; got {bc.label_text!r}"
        )


@pytest.mark.asyncio
async def test_esc_on_child_screen_pops():
    """Esc on a drilled-in screen (no edit in progress) pops back."""
    tree = build_form_tree(_Outer)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        root_screen = app.screen
        field_list = app.screen.query_one(FieldListView)
        _focus_row(field_list, 1)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        assert _config_screen_depth(app) == 2
        await pilot.press("escape")
        await pilot.pause()
        await pilot.pause()
        assert _config_screen_depth(app) == 1, (
            f"Esc on child should pop; stack = "
            f"{[type(s).__name__ for s in app.screen_stack]}"
        )
        assert app.screen is root_screen


@pytest.mark.asyncio
async def test_two_level_drill_down_breadcrumb():
    """Drill into mid.deep: breadcrumb shows full path."""
    tree = build_form_tree(_Outer)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        field_list = app.screen.query_one(FieldListView)
        # _Outer fields: [name, nested, mid] — index 2 is 'mid'.
        _focus_row(field_list, 2)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        # Now in 'mid' — fields are [deep, flag] — cursor starts at 0 = 'deep'.
        mid_list = app.screen.query_one(FieldListView)
        assert mid_list.cursor == 0
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        assert _config_screen_depth(app) == 3, (
            f"Two-level drill should push twice; stack = "
            f"{[type(s).__name__ for s in app.screen_stack]}"
        )
        deep_bc = app.screen.query_one(Breadcrumb)
        assert "deep" in deep_bc.label_text


@pytest.mark.asyncio
async def test_esc_on_root_screen_does_not_pop():
    """Esc on the root ConfigScreen has no ConfigScreen to pop to — the
    root ConfigScreen must remain mounted (Textual's default Screen at
    index 0 of the stack is internal and irrelevant)."""
    tree = build_form_tree(_Outer)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert _config_screen_depth(app) == 1
        await pilot.press("escape")
        await pilot.pause()
        assert _config_screen_depth(app) == 1, (
            "Esc on root must not pop the only ConfigScreen"
        )


@pytest.mark.asyncio
async def test_enter_on_leaf_row_does_not_drill():
    """Enter on a leaf (str) row should enter edit mode, not push a screen."""
    tree = build_form_tree(_Outer)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        # cursor starts at 0 → 'name' (a string leaf).
        await pilot.press("enter")
        await pilot.pause()
        assert _config_screen_depth(app) == 1, (
            "Enter on a leaf row should not push a new screen"
        )
