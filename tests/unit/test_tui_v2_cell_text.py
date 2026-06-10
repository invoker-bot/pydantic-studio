"""Unit tests for TextCell — covers 16 leaf node kinds via parse_for_kind.

Form mode: the cell hosts a persistent Input (focus = edit). Commit
happens via Enter (Input.Submitted) or ``commit_pending()`` (the
move-away path driven by FieldListView).
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App
from textual.widgets import Input

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.cells.text_cell import TextCell


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 5


class _Host(App):
    def __init__(self, cell: TextCell) -> None:
        super().__init__()
        self._cell = cell

    def compose(self):
        yield self._cell


def _make_cell(field: str, value):
    tree = build_form_tree(_Schema)
    tree.set_value(field, value)
    node = tree.root.find(field)
    assert node is not None
    return tree, node, TextCell(node=node, path=field, form_tree=tree)


@pytest.mark.asyncio
async def test_text_cell_hosts_persistent_input_with_value() -> None:
    _, _, cell = _make_cell("name", "beta")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "beta"
        assert cell.query_one(Input).value == "beta", (
            "form mode: the Input is always mounted and pre-filled"
        )
        assert cell.editing is False, "no modal edit state exists"


@pytest.mark.asyncio
async def test_text_cell_idle_renders_int_value() -> None:
    _, _, cell = _make_cell("count", 42)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "42"


@pytest.mark.asyncio
async def test_text_cell_commit_on_enter_in_input() -> None:
    tree, _, cell = _make_cell("name", "beta")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        input_widget = cell.query_one(Input)
        input_widget.value = "gamma"
        await input_widget.action_submit()
        await pilot.pause()
        assert tree.root.find("name").value == "gamma"
        assert cell.value_text == "gamma"


@pytest.mark.asyncio
async def test_text_cell_commit_pending_on_move_away() -> None:
    """The form-flow path: FieldListView calls commit_pending before
    every cursor move; no Enter involved."""
    tree, _, cell = _make_cell("name", "beta")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.query_one(Input).value = "delta"
        result = cell.commit_pending()
        await pilot.pause()
        assert result is not None
        assert result.ok
        assert tree.root.find("name").value == "delta"


@pytest.mark.asyncio
async def test_text_cell_commit_pending_noop_when_clean() -> None:
    _, _, cell = _make_cell("name", "beta")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.commit_pending() is None, "unchanged text commits nothing"


@pytest.mark.asyncio
async def test_text_cell_revert_restores_committed_value() -> None:
    tree, _, cell = _make_cell("name", "beta")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        input_widget = cell.query_one(Input)
        input_widget.value = "zzz"
        assert cell.is_dirty()
        cell.revert()
        await pilot.pause()
        assert tree.root.find("name").value == "beta"  # unchanged
        assert input_widget.value == "beta"
        assert not cell.is_dirty()


@pytest.mark.asyncio
async def test_text_cell_unparseable_int_sets_last_error() -> None:
    tree, _, cell = _make_cell("count", 5)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.query_one(Input).value = "not-an-int"
        result = cell.commit_pending()
        await pilot.pause()
        assert result is not None
        assert not result.ok
        assert tree.root.find("count").value == 5  # tree NOT mutated
        assert cell.last_error is not None
        assert "parse" in cell.last_error.lower() or "int" in cell.last_error.lower()


@pytest.mark.asyncio
async def test_text_cell_validate_failure_sets_last_error() -> None:
    """A string that parses fine (parse_for_kind always returns the raw
    str for ip_address) but flunks the node's validate_value surfaces
    via the FormTree's validate-first contract."""
    from ipaddress import IPv4Address

    class _IpSchema(BaseModel):
        host: IPv4Address = IPv4Address("127.0.0.1")

    tree = build_form_tree(_IpSchema)
    tree.set_value("host", "127.0.0.1")
    node = tree.root.find("host")
    cell = TextCell(node=node, path="host", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.query_one(Input).value = "not-an-ip"
        result = cell.commit_pending()
        await pilot.pause()
        assert result is not None
        assert not result.ok
        assert tree.root.find("host").value == "127.0.0.1"  # unchanged
        assert cell.last_error is not None


@pytest.mark.asyncio
async def test_text_cell_bytes_renders_hex_and_parses_hex() -> None:
    class _BSchema(BaseModel):
        salt: bytes = b""

    tree = build_form_tree(_BSchema)
    tree.set_value("salt", b"\xde\xad")
    node = tree.root.find("salt")
    cell = TextCell(node=node, path="salt", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "dead"  # hex of b"\xde\xad"
        input_widget = cell.query_one(Input)
        assert input_widget.value == "dead"
        input_widget.value = "beef"
        await input_widget.action_submit()
        await pilot.pause()
        assert tree.root.find("salt").value == b"\xbe\xef"
