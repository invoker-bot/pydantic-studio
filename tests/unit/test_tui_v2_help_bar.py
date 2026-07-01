"""HelpBar — the description / constraints / guidance line.

The schema already carries the most valuable onboarding content
(FieldInfo.description, constraints, required-ness); pre-v0.2 the TUI
never displayed any of it. The HelpBar sits between the field list and
the footer and always describes the focused row, plus a counter of
required fields still missing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.widgets.help_bar import HelpBar, describe_node


class _Schema(BaseModel):
    port: int = Field(8080, ge=1, le=65535, description="Listening port")
    name: str = Field("svc", description="Service identifier")
    api_key: str = Field(..., description="Exchange API key")
    plain: bool = False


class _DecimalSchema(BaseModel):
    price: Decimal = Field(
        default=Decimal("1.00"),
        max_digits=4,
        decimal_places=2,
        allow_inf_nan=False,
        description="Invoice amount",
    )


@pytest.mark.asyncio
async def test_config_screen_composes_help_bar() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.query_one(HelpBar) is not None


@pytest.mark.asyncio
async def test_help_bar_shows_focused_field_description_and_constraints() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.screen.query_one(HelpBar)
        assert "Listening port" in bar.text
        assert "ge=1" in bar.text
        assert "le=65535" in bar.text
        assert "int" in bar.text


def test_help_bar_describes_decimal_precision_and_finite_constraint() -> None:
    tree = build_form_tree(_DecimalSchema)
    node = tree.root.find("price")

    assert node is not None
    text = describe_node(node)

    assert "max_digits=4" in text
    assert "decimal_places=2" in text
    assert "finite" in text
    assert "Invoice amount" in text


@pytest.mark.asyncio
async def test_help_bar_follows_cursor() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        bar = app.screen.query_one(HelpBar)
        assert "Service identifier" in bar.text


@pytest.mark.asyncio
async def test_help_bar_counts_missing_required() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.screen.query_one(HelpBar)
        assert "1 required" in bar.text
        tree.set_value("api_key", "k")
        await pilot.press("down")  # any cursor move refreshes the bar
        await pilot.pause()
        assert "missing" not in bar.text


@pytest.mark.asyncio
async def test_help_bar_handles_missing_description() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        for _ in range(3):
            await pilot.press("down")
        await pilot.pause()
        bar = app.screen.query_one(HelpBar)
        assert "plain" in bar.text
        assert "bool" in bar.text
