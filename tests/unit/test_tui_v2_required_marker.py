"""FieldRow required-field marker tests.

A leaf node that is ``required=True`` and currently has ``value is
None`` must render a visible marker so the user knows the field
blocks save. Group / Sequence / Mapping / Union containers don't get
a marker (drilling into them surfaces their own required children).
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow


class _Required(BaseModel):
    api_key: str = Field(...)
    timeout: int = 30
    debug: bool = False


class _AllOptional(BaseModel):
    note: str = "hi"
    count: int = 7


class _WithGroup(BaseModel):
    nested: _Required


def _row_named(app: StudioApp, name: str) -> FieldRow:
    rows = list(app.screen.query(FieldRow))
    for r in rows:
        if r.node.name == name:
            return r
    raise AssertionError(
        f"No row named {name!r}; available: {[r.node.name for r in rows]}"
    )


@pytest.mark.asyncio
async def test_required_unset_leaf_shows_marker():
    """``api_key`` is required and unset → label gets a ``*`` marker."""
    tree = build_form_tree(_Required)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        row = _row_named(app, "api_key")
        assert row.label_text.startswith("*"), (
            f"required+unset row should be marked; got label={row.label_text!r}"
        )


@pytest.mark.asyncio
async def test_required_set_leaf_has_no_marker():
    """Once the required field has a value, the marker drops."""
    tree = build_form_tree(_Required)
    tree.set_value("api_key", "secret")
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        row = _row_named(app, "api_key")
        assert not row.label_text.startswith("*"), (
            f"required+set row must not show marker; got label={row.label_text!r}"
        )


@pytest.mark.asyncio
async def test_optional_unset_leaf_has_no_marker():
    """Optional fields never show the missing-marker, even when unset."""
    tree = build_form_tree(_AllOptional)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        # _AllOptional fields have defaults, so neither is "missing".
        for row in app.screen.query(FieldRow):
            assert not row.label_text.startswith("*"), (
                f"optional-with-default row must not show marker; got {row.label_text!r}"
            )


@pytest.mark.asyncio
async def test_group_node_never_shows_required_marker():
    """A nested Group container itself never shows the marker — drilling
    into it surfaces the group's own required leaves."""
    tree = build_form_tree(_WithGroup)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        row = _row_named(app, "nested")
        assert not row.label_text.startswith("*"), (
            f"group rows must not show missing-marker on the container "
            f"itself; got {row.label_text!r}"
        )
