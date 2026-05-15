"""Unit tests for the TUI v2 Breadcrumb widget."""

from __future__ import annotations

import pytest
from textual.app import App

from pydantic_studio.renderers.textual_.widgets.breadcrumb import Breadcrumb


class _Host(App):
    def __init__(self, parts: list[str]) -> None:
        super().__init__()
        self._parts = parts

    def compose(self):
        yield Breadcrumb(parts=self._parts)


@pytest.mark.asyncio
async def test_breadcrumb_renders_single_part() -> None:
    app = _Host(["AppSettings"])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == "AppSettings"


@pytest.mark.asyncio
async def test_breadcrumb_joins_parts_with_chevron() -> None:
    app = _Host(["AppSettings", "database"])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == "AppSettings › database"


@pytest.mark.asyncio
async def test_breadcrumb_full_depth_three_no_truncation() -> None:
    app = _Host(["a", "b", "c"])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == "a › b › c"


@pytest.mark.asyncio
async def test_breadcrumb_truncates_middle_at_depth_four() -> None:
    app = _Host(["a", "b", "c", "d"])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        # Middle parts (b, c) collapse to ellipsis; first and last preserved.
        assert bc.label_text == "a › … › d"


@pytest.mark.asyncio
async def test_breadcrumb_truncates_middle_at_depth_five() -> None:
    app = _Host(["a", "b", "c", "d", "e"])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == "a › … › e"


@pytest.mark.asyncio
async def test_breadcrumb_empty_parts_renders_blank() -> None:
    app = _Host([])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == ""
