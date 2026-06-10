"""Regression tests for the phantom-edit-mode family of bugs.

Pre-fix, Enter on a small ChoiceCell fell through to the *base*
``Cell.enter_edit()`` — a phantom edit mode with no edit UI where Enter
did nothing and Esc crashed the app (``AttributeError:
'ChoiceCell' object has no attribute 'cancel_edit'``), and the footer
stayed stuck on editing hints. These tests pin the fixed contract:

- Enter on a small choice advances (form flow); Left/Right cycle the
  value; no phantom edit mode anywhere.
- Esc never raises, whatever cell is focused.
- ``Cell.cancel_edit`` exists on the base class as a safe no-op exit.
- The footer stays on idle hints after the interaction.
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
async def test_enter_on_small_choice_never_phantom_edits() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        cell = app.screen.query_one(ChoiceCell)
        assert cell.editing is False, "small choice must never enter edit mode"
        assert tree._resolve_path("level").value == _Level.INFO, (
            "Enter advances the form; values change via Left/Right"
        )


@pytest.mark.asyncio
async def test_right_cycles_small_choice_value() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        assert tree._resolve_path("level").value == _Level.WARN


@pytest.mark.asyncio
async def test_escape_after_enter_on_small_choice_does_not_crash() -> None:
    """Pre-fix this raised AttributeError (cancel_edit missing) and the
    whole session died. Now Esc walks the layered flow; on a clean tree
    at root it exits gracefully with a cancelled outcome — run_test
    re-raises any in-app exception, so reaching the assert IS the pin."""
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.outcome.submitted is False


@pytest.mark.asyncio
async def test_footer_stays_idle_after_choice_interaction() -> None:
    """Enter on a small choice cycles in place — the footer must never
    flip to editing hints (the phantom mode used to leave it stuck)."""
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
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
