"""Unit tests for Cell base lifecycle + Messages."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App
from textual.widgets import Static

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.cells.base import (
    Cell,
    EditModeEntered,
    EditModeExited,
)


class _Schema(BaseModel):
    name: str = "alpha"


class _StubCell(Cell):
    """Minimal concrete subclass: renders a Static."""

    def compose(self):
        yield Static(self.value_text, classes="field-row--value")

    @property
    def value_text(self) -> str:
        v = getattr(self._node, "value", None)
        return "" if v is None else str(v)


class _Host(App):
    def __init__(self, cell: _StubCell) -> None:
        super().__init__()
        self._cell = cell
        self.entered_events: list[EditModeEntered] = []
        self.exited_events: list[EditModeExited] = []

    def compose(self):
        yield self._cell

    def on_edit_mode_entered(self, event: EditModeEntered) -> None:
        self.entered_events.append(event)

    def on_edit_mode_exited(self, event: EditModeExited) -> None:
        self.exited_events.append(event)


def _build_tree_and_node():
    tree = build_form_tree(_Schema)
    node = tree.root.find("name")
    assert node is not None
    return tree, node


@pytest.mark.asyncio
async def test_cell_idle_value_text_reads_node_value() -> None:
    tree, node = _build_tree_and_node()
    tree.set_value("name", "beta")
    cell = _StubCell(node=node, path="name", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "beta"


@pytest.mark.asyncio
async def test_cell_enter_edit_posts_event() -> None:
    tree, node = _build_tree_and_node()
    cell = _StubCell(node=node, path="name", form_tree=tree)
    host = _Host(cell)
    async with host.run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        assert len(host.entered_events) == 1
        assert host.entered_events[0].path == "name"


@pytest.mark.asyncio
async def test_cell_exit_edit_posts_event() -> None:
    tree, node = _build_tree_and_node()
    cell = _StubCell(node=node, path="name", form_tree=tree)
    host = _Host(cell)
    async with host.run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        cell.exit_edit()
        await pilot.pause()
        assert len(host.exited_events) == 1
        assert host.exited_events[0].path == "name"


@pytest.mark.asyncio
async def test_cell_commit_success_returns_ok_and_mutates_tree() -> None:
    tree, node = _build_tree_and_node()
    cell = _StubCell(node=node, path="name", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        result = cell.commit("new-name")
        assert result.ok is True
        assert tree.root.find("name").value == "new-name"


@pytest.mark.asyncio
async def test_cell_commit_failure_returns_errors_and_leaves_tree() -> None:
    """A failed commit returns ok=False with errors; the tree is not
    mutated (validate-first contract)."""

    class _ConstrainedSchema(BaseModel):
        port: int = 8080

    tree = build_form_tree(_ConstrainedSchema)
    tree.set_value("port", 8080)
    node = tree.root.find("port")
    cell = _StubCell(node=node, path="port", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # int is fine; pass a string that set_value can't coerce -> failure.
        result = cell.commit("not-an-int")
        assert result.ok is False
        assert len(result.errors) > 0
        assert tree.root.find("port").value == 8080  # unchanged


@pytest.mark.asyncio
async def test_cell_tracks_editing_flag() -> None:
    tree, node = _build_tree_and_node()
    cell = _StubCell(node=node, path="name", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.editing is False
        cell.enter_edit()
        assert cell.editing is True
        cell.exit_edit()
        assert cell.editing is False
