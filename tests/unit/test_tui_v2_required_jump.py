"""`n` — jump to the next missing-required field.

The dominant editing task is "make this config valid with the least
effort"; required fields can sit anywhere in declaration order (in the
motivating downstream schema: dead last, behind 20 pre-filled optional
fields). `n` cycles the cursor through rows whose subtree still misses
required values.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView


class _Inner(BaseModel):
    network: str
    address: str


class _Schema(BaseModel):
    timeout: int = 30
    api_key: str = Field(...)
    retries: int = 3
    api_secret: str = Field(...)
    items: list[_Inner] = Field(default_factory=list)


def _cursor_path(app: StudioApp) -> str:
    view = app.screen.query_one(FieldListView)
    return view._row_specs()[view.cursor].path


@pytest.mark.asyncio
async def test_n_jumps_to_first_missing_required() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert _cursor_path(app) == "api_key"


@pytest.mark.asyncio
async def test_n_cycles_through_missing_required() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.press("n")
        await pilot.pause()
        assert _cursor_path(app) == "api_secret"
        await pilot.press("n")  # wraps around
        await pilot.pause()
        assert _cursor_path(app) == "api_key"


@pytest.mark.asyncio
async def test_n_targets_container_rows_for_nested_missing() -> None:
    tree = build_form_tree(_Schema)
    tree.set_value("api_key", "k")
    tree.set_value("api_secret", "s")
    tree.add_item("items")
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert _cursor_path(app) == "items"


@pytest.mark.asyncio
async def test_n_noop_when_nothing_missing() -> None:
    tree = build_form_tree(_Schema)
    tree.set_value("api_key", "k")
    tree.set_value("api_secret", "s")
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        before = _cursor_path(app)
        await pilot.press("n")
        await pilot.pause()
        assert _cursor_path(app) == before
