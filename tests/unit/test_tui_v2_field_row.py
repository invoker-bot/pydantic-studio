"""Unit tests for FieldRow shell + kind-based cell dispatch."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 5
    tags: list[str] = []


def _tree_and_node(field_name: str):
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
    return tree, n


class _Host(App):
    def __init__(self, row: FieldRow) -> None:
        super().__init__()
        self._row = row

    def compose(self):
        yield self._row


@pytest.mark.asyncio
async def test_field_row_renders_label_and_value() -> None:
    tree, node = _tree_and_node("name")
    row = FieldRow(node=node, path="name", form_tree=tree, focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        # Label is accessible via row API for tests.
        assert row.label_text == "name"


@pytest.mark.asyncio
async def test_field_row_focused_shows_marker() -> None:
    tree, node = _tree_and_node("name")
    row = FieldRow(node=node, path="name", form_tree=tree, focused=True)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.marker_text == "▎"  # U+25B8 focus indicator


@pytest.mark.asyncio
async def test_field_row_unfocused_marker_is_blank() -> None:
    tree, node = _tree_and_node("name")
    row = FieldRow(node=node, path="name", form_tree=tree, focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.marker_text == " "


@pytest.mark.asyncio
async def test_field_row_container_kind_renders_drill_marker() -> None:
    # tags is a SequenceNode -> drillable -> drill marker visible.
    tree, node = _tree_and_node("tags")
    row = FieldRow(node=node, path="tags", form_tree=tree, focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.drill_marker_text == "›"  # noqa: RUF001


@pytest.mark.asyncio
async def test_field_row_leaf_kind_hides_drill_marker() -> None:
    # name is a StringNode -> not drillable -> blank drill marker.
    tree, node = _tree_and_node("name")
    row = FieldRow(node=node, path="name", form_tree=tree, focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.drill_marker_text == ""


@pytest.mark.asyncio
async def test_field_row_error_helper_hidden_by_default() -> None:
    tree, node = _tree_and_node("name")
    row = FieldRow(node=node, path="name", form_tree=tree, focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.helper_text == ""


@pytest.mark.asyncio
async def test_field_row_set_error_shows_helper() -> None:
    tree, node = _tree_and_node("name")
    row = FieldRow(node=node, path="name", form_tree=tree, focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        row.set_error("pattern requires ^[a-z]+$")
        await pilot.pause()
        assert row.helper_text == "↳ pattern requires ^[a-z]+$"


@pytest.mark.asyncio
async def test_field_row_clear_error_hides_helper() -> None:
    tree, node = _tree_and_node("name")
    row = FieldRow(node=node, path="name", form_tree=tree, focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        row.set_error("oops")
        await pilot.pause()
        row.set_error(None)
        await pilot.pause()
        assert row.helper_text == ""


@pytest.mark.asyncio
async def test_field_row_dispatches_string_to_text_cell() -> None:
    from pydantic_studio.renderers.textual_.widgets.cells import TextCell

    tree = build_form_tree(_Schema)
    tree.set_value("name", "alpha")
    node = tree.root.find("name")
    row = FieldRow(node=node, path="name", form_tree=tree, focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert isinstance(row.query_one(TextCell), TextCell)


@pytest.mark.asyncio
async def test_field_row_dispatches_bool_to_bool_cell() -> None:
    from pydantic_studio.renderers.textual_.widgets.cells import BoolCell

    class _BS(BaseModel):
        debug: bool = False

    tree = build_form_tree(_BS)
    tree.set_value("debug", True)
    node = tree.root.find("debug")
    row = FieldRow(node=node, path="debug", form_tree=tree, focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert isinstance(row.query_one(BoolCell), BoolCell)
