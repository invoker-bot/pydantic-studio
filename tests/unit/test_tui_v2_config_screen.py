"""Unit tests for ConfigScreen — composes Breadcrumb + list + footer
and loads theme.tcss via CSS_PATH.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.screens import ConfigScreen
from pydantic_studio.renderers.textual_.widgets.breadcrumb import Breadcrumb
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow
from pydantic_studio.renderers.textual_.widgets.footer_hints import FooterHints


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 5


class _Host(App):
    def __init__(self, screen: ConfigScreen) -> None:
        super().__init__()
        self._screen = screen

    def on_mount(self) -> None:
        self.push_screen(self._screen)


@pytest.mark.asyncio
async def test_config_screen_composes_three_regions() -> None:
    tree = build_form_tree(_Schema)
    screen = ConfigScreen(group=tree.root, form_tree=tree, breadcrumb_parts=["AppSettings"])
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.query_one(Breadcrumb) is not None
        assert app.screen.query_one(FieldListView) is not None
        assert app.screen.query_one(FooterHints) is not None


@pytest.mark.asyncio
async def test_config_screen_breadcrumb_shows_provided_parts() -> None:
    tree = build_form_tree(_Schema)
    screen = ConfigScreen(group=tree.root, form_tree=tree, breadcrumb_parts=["a", "b"])
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == "a › b"  # noqa: RUF001


@pytest.mark.asyncio
async def test_config_screen_footer_starts_in_idle_mode() -> None:
    tree = build_form_tree(_Schema)
    screen = ConfigScreen(group=tree.root, form_tree=tree, breadcrumb_parts=["AppSettings"])
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "navigate" in fh.line1


@pytest.mark.asyncio
async def test_config_screen_field_list_carries_group() -> None:
    tree = build_form_tree(_Schema)
    screen = ConfigScreen(group=tree.root, form_tree=tree, breadcrumb_parts=["AppSettings"])
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        rows = list(app.screen.query(FieldRow))
        assert [r.label_text for r in rows] == ["name", "count"]


@pytest.mark.asyncio
async def test_config_screen_loads_theme_tcss() -> None:
    tree = build_form_tree(_Schema)
    screen = ConfigScreen(group=tree.root, form_tree=tree, breadcrumb_parts=["AppSettings"])
    # CSS_PATH should point at theme.tcss (one of the values may be a list).
    css = screen.CSS_PATH
    paths = css if isinstance(css, list) else [css]
    assert any(str(p).endswith("theme.tcss") for p in paths)
