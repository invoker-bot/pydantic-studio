"""Unit tests for BoolCell — Space/Enter toggles the value immediately."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.cells.bool_cell import BoolCell


class _Schema(BaseModel):
    debug: bool = False


class _Host(App):
    def __init__(self, cell: BoolCell) -> None:
        super().__init__()
        self._cell = cell

    def compose(self):
        yield self._cell


def _make_cell(initial: bool):
    tree = build_form_tree(_Schema)
    tree.set_value("debug", initial)
    node = tree.root.find("debug")
    assert node is not None
    return tree, BoolCell(node=node, path="debug", form_tree=tree)


@pytest.mark.asyncio
async def test_bool_cell_idle_false_renders_off_chip() -> None:
    _, cell = _make_cell(False)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "○ off"


@pytest.mark.asyncio
async def test_bool_cell_idle_true_renders_on_chip() -> None:
    _, cell = _make_cell(True)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "● on "


@pytest.mark.asyncio
async def test_bool_cell_toggle_flips_false_to_true() -> None:
    tree, cell = _make_cell(False)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.toggle()
        await pilot.pause()
        assert tree.root.find("debug").value is True
        assert cell.value_text == "● on "


@pytest.mark.asyncio
async def test_bool_cell_toggle_flips_true_to_false() -> None:
    tree, cell = _make_cell(True)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.toggle()
        await pilot.pause()
        assert tree.root.find("debug").value is False
        assert cell.value_text == "○ off"


@pytest.mark.asyncio
async def test_bool_cell_toggle_from_none_treats_as_false() -> None:
    """If value is None (never set), toggle commits True."""
    tree = build_form_tree(_Schema)
    node = tree.root.find("debug")
    cell = BoolCell(node=node, path="debug", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.toggle()
        await pilot.pause()
        assert tree.root.find("debug").value is True


@pytest.mark.asyncio
async def test_bool_cell_does_not_enter_edit_mode() -> None:
    """BoolCell has no inline-input edit cycle."""
    _, cell = _make_cell(False)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # toggle should NOT trigger the edit lifecycle.
        cell.toggle()
        await pilot.pause()
        assert cell.editing is False
