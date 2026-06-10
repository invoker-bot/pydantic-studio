"""Regression tests for the phantom-edit-mode family of bugs.

Pre-fix, Enter on a small ChoiceCell fell through to the *base*
``Cell.enter_edit()`` — a phantom edit mode with no edit UI where Enter
did nothing and Esc crashed the app (``AttributeError:
'ChoiceCell' object has no attribute 'cancel_edit'``), and the footer
stayed stuck on editing hints. These tests pin the fixed contract:

- Enter on a small choice cycles the value (same as Tab); no edit mode.
- Esc never raises, whatever cell is focused.
- ``Cell.cancel_edit`` exists on the base class as a safe no-op exit.
- The footer returns to idle hints after the interaction.
"""

from __future__ import annotations

from enum import StrEnum

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.widgets.cells.base import Cell
from pydantic_studio.renderers.textual_.widgets.cells.choice_cell import ChoiceCell
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.footer_hints import FooterHints


class _Level(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"


class _Schema(BaseModel):
    level: _Level = _Level.INFO
    name: str = "alpha"


@pytest.mark.asyncio
async def test_enter_on_small_choice_cycles_instead_of_phantom_edit() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        cell = app.screen.query_one(ChoiceCell)
        assert cell.editing is False, "small choice must never enter edit mode"
        assert tree._resolve_path("level").value == _Level.WARN, (
            "Enter on a small choice cycles to the next value"
        )


@pytest.mark.asyncio
async def test_escape_after_enter_on_small_choice_does_not_crash() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")  # pre-fix: AttributeError crash
        await pilot.pause()
        assert app.is_running


@pytest.mark.asyncio
async def test_footer_returns_to_idle_after_choice_interaction() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.press("escape")
        await pilot.pause()
        footer = app.screen.query_one(FooterHints)
        assert footer._mode == "idle"


def test_cell_base_has_safe_cancel_edit() -> None:
    assert hasattr(Cell, "cancel_edit"), (
        "Cell base class must provide a default cancel_edit so Esc can "
        "never crash on cells without a custom edit UI"
    )


@pytest.mark.asyncio
async def test_escape_with_focused_cell_guarded_via_getattr() -> None:
    """Even a cell whose subclass deletes cancel_edit must not crash Esc."""
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        view = app.screen.query_one(FieldListView)
        cell = view._focused_cell()
        assert cell is not None
        cell._editing = True  # simulate a stuck edit flag
        await pilot.press("escape")
        await pilot.pause()
        assert app.is_running
        assert cell.editing is False
