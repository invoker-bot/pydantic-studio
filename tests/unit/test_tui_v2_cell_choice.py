"""Unit tests for ChoiceCell (enum + literal) and ChooserScreen for
the >7 choices case.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

import pytest
from pydantic import BaseModel
from textual.app import App

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.cells.choice_cell import ChoiceCell


class _Level(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"


class _Small(BaseModel):
    level: _Level = _Level.INFO


class _Literal(BaseModel):
    color: Literal["red", "green", "blue"] = "green"


class _BigEnum(StrEnum):
    A = "a"
    B = "b"
    C = "c"
    D = "d"
    E = "e"
    F = "f"
    G = "g"
    H = "h"


class _Large(BaseModel):
    letter: _BigEnum = _BigEnum.A


class _Host(App):
    def __init__(self, cell: ChoiceCell) -> None:
        super().__init__()
        self._cell = cell

    def compose(self):
        yield self._cell


def _make_cell(schema_class: type[BaseModel], field: str, initial):
    tree = build_form_tree(schema_class)
    tree.set_value(field, initial)
    node = tree.root.find(field)
    assert node is not None
    return tree, ChoiceCell(node=node, path=field, form_tree=tree)


@pytest.mark.asyncio
async def test_choice_cell_small_renders_chevron_chip() -> None:
    _, cell = _make_cell(_Small, "level", _Level.INFO)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # Small (3 choices) renders the inline-cycle chrome.
        assert cell.value_text.startswith("‹")  # noqa: RUF001
        assert cell.value_text.endswith("›")  # noqa: RUF001
        assert "info" in cell.value_text


@pytest.mark.asyncio
async def test_choice_cell_small_cycle_next() -> None:
    tree, cell = _make_cell(_Small, "level", _Level.INFO)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.cycle_next()
        await pilot.pause()
        # info -> warn (third in DEBUG, INFO, WARN order)
        assert tree.root.find("level").value == _Level.WARN


@pytest.mark.asyncio
async def test_choice_cell_small_cycle_prev() -> None:
    tree, cell = _make_cell(_Small, "level", _Level.INFO)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.cycle_prev()
        await pilot.pause()
        # info -> debug
        assert tree.root.find("level").value == _Level.DEBUG


@pytest.mark.asyncio
async def test_choice_cell_small_cycle_wraps() -> None:
    tree, cell = _make_cell(_Small, "level", _Level.WARN)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.cycle_next()
        await pilot.pause()
        # warn -> debug (wraps)
        assert tree.root.find("level").value == _Level.DEBUG


@pytest.mark.asyncio
async def test_choice_cell_literal_works_like_enum() -> None:
    tree, cell = _make_cell(_Literal, "color", "green")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.cycle_next()
        await pilot.pause()
        assert tree.root.find("color").value == "blue"


@pytest.mark.asyncio
async def test_choice_cell_large_renders_drill_chip() -> None:
    _, cell = _make_cell(_Large, "letter", _BigEnum.A)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # >7 choices: no chevron, just the value (drill marker is on FieldRow).
        assert cell.value_text == "a"
        assert cell.large_choice is True


@pytest.mark.asyncio
async def test_choice_cell_large_open_chooser_screen() -> None:
    """When ChoiceCell.open_chooser() is called for a large-choice
    field, a ChooserScreen is pushed onto the app's screen stack."""
    from pydantic_studio.renderers.textual_.screens import ChooserScreen

    _, cell = _make_cell(_Large, "letter", _BigEnum.A)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.open_chooser()
        await pilot.pause()
        assert isinstance(cell.app.screen, ChooserScreen)


@pytest.mark.asyncio
async def test_chooser_screen_lists_all_options_and_commits_on_select() -> None:
    """The ChooserScreen exposes a list of options; calling its
    select(idx) commits the choice and pops the screen."""
    from pydantic_studio.renderers.textual_.screens import ChooserScreen

    tree = build_form_tree(_Large)
    tree.set_value("letter", _BigEnum.A)
    node = tree.root.find("letter")
    screen = ChooserScreen(node=node, path="letter", form_tree=tree)

    class _AppHost(App):
        def on_mount(self) -> None:
            self.push_screen(screen)

    async with _AppHost().run_test() as pilot:
        await pilot.pause()
        # 8 options for _BigEnum.
        assert len(screen.options) == 8
        # Pick the 5th option (E).
        screen.select(4)
        await pilot.pause()
        assert tree.root.find("letter").value == _BigEnum.E
