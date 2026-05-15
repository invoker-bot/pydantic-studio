"""Unit tests for FieldRow shell + PlaceholderCell."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.field_row import (
    FieldRow,
    PlaceholderCell,
)


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 5
    tags: list[str] = []


def _node(field_name: str):
    # Default-seeding was removed in Phase 6 housekeeping (see CLAUDE.md),
    # so build_form_tree leaves node.value=None even when the field has a
    # default. Seed the value here so the helper matches what users see
    # after first navigating to a field (where the row chrome falls back
    # to the field default).
    tree = build_form_tree(_Schema)
    n = tree.root.find(field_name)
    assert n is not None
    if getattr(n, "default", None) is not None and getattr(n, "value", None) is None:
        tree.set_value(field_name, n.default)
    return n


class _Host(App):
    def __init__(self, row: FieldRow) -> None:
        super().__init__()
        self._row = row

    def compose(self):
        yield self._row


@pytest.mark.asyncio
async def test_field_row_renders_label_and_value() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        # Label and value are accessible via row API for tests.
        assert row.label_text == "name"
        # PlaceholderCell renders str(node.value); name was seeded "alpha".
        assert row.value_text == "alpha"


@pytest.mark.asyncio
async def test_field_row_focused_shows_marker() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=True)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.marker_text == "▸"  # U+25B8 focus indicator


@pytest.mark.asyncio
async def test_field_row_unfocused_marker_is_blank() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.marker_text == " "


@pytest.mark.asyncio
async def test_field_row_container_kind_renders_drill_marker() -> None:
    # tags is a SequenceNode -> drillable -> drill marker visible.
    row = FieldRow(node=_node("tags"), path="tags", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.drill_marker_text == ">"


@pytest.mark.asyncio
async def test_field_row_leaf_kind_hides_drill_marker() -> None:
    # name is a StringNode -> not drillable -> blank drill marker.
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.drill_marker_text == ""


@pytest.mark.asyncio
async def test_field_row_error_helper_hidden_by_default() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.helper_text == ""


@pytest.mark.asyncio
async def test_field_row_set_error_shows_helper() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        row.set_error("pattern requires ^[a-z]+$")
        await pilot.pause()
        assert row.helper_text == "[!] pattern requires ^[a-z]+$"


@pytest.mark.asyncio
async def test_field_row_clear_error_hides_helper() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        row.set_error("oops")
        await pilot.pause()
        row.set_error(None)
        await pilot.pause()
        assert row.helper_text == ""


@pytest.mark.asyncio
async def test_placeholder_cell_renders_str_value() -> None:
    cell = PlaceholderCell(node=_node("count"))
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # count is seeded 5 -> stringified.
        assert cell.value_text == "5"


@pytest.mark.asyncio
async def test_placeholder_cell_renders_empty_when_value_none() -> None:
    # Build a tree without seeding -> value is None.
    tree = build_form_tree(_Schema)
    # Don't set anything; default-seeding was removed in Phase 6
    # housekeeping, so freshly built nodes have value=None.
    node = tree.root.find("name")
    assert node is not None
    cell = PlaceholderCell(node=node)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # None renders as the empty string, not "None".
        assert cell.value_text == ""
