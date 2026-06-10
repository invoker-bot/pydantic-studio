"""`/` filter — substring-narrow the visible rows of a group screen.

23+ field forms were arrow-key-only. `/` mounts a filter input above
the list; typing narrows live; Enter returns focus to the (filtered)
list; Esc clears. Esc is layered: filter → child screen → session.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow


class _Inner(BaseModel):
    network: str = "TRC20"
    address: str = "T000"


class _Schema(BaseModel):
    proxy: str = ""
    swap_maker_fee: float = 0.0002
    swap_taker_fee: float = 0.0005
    spot_maker_fee: float = 0.0008
    leverage: int = 1
    items: list[_Inner] = Field(default_factory=list)


def _visible_labels(app: StudioApp) -> list[str]:
    return [row.label_text for row in app.screen.query(FieldRow)]


@pytest.mark.asyncio
async def test_slash_filters_rows_live() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        for ch in "fee":
            await pilot.press(ch)
        await pilot.pause()
        labels = _visible_labels(app)
        assert labels == ["swap_maker_fee", "swap_taker_fee", "spot_maker_fee"]


@pytest.mark.asyncio
async def test_enter_keeps_filter_and_returns_focus_to_list() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash")
        for ch in "swap":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        labels = _visible_labels(app)
        assert labels == ["swap_maker_fee", "swap_taker_fee"]
        view = app.screen.query_one(FieldListView)
        await pilot.press("down")
        await pilot.pause()
        assert view._row_specs()[view.cursor].path == "swap_taker_fee"


@pytest.mark.asyncio
async def test_escape_clears_filter_before_anything_else() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash")
        for ch in "fee":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")  # 1st Esc: clear the filter
        await pilot.pause()
        assert app.is_running
        assert len(_visible_labels(app)) == 6
        await pilot.press("escape")  # 2nd Esc at root, clean tree: cancel
        await pilot.pause()
    assert app.outcome.submitted is False


@pytest.mark.asyncio
async def test_escape_while_typing_clears_and_restores() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash")
        for ch in "fee":
            await pilot.press(ch)
        await pilot.press("escape")
        await pilot.pause()
        assert app.is_running
        assert len(_visible_labels(app)) == 6


@pytest.mark.asyncio
async def test_slash_is_noop_on_sequence_screens() -> None:
    from textual.widgets import Input

    tree = build_form_tree(_Schema)
    tree.add_item("items")
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        view = app.screen.query_one(FieldListView)
        view.focus_path("items")
        await pilot.press("enter")  # drill into the sequence
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        assert not list(app.screen.query(Input))
