"""ErrorsScreen tests — pushed on save when the tree fails validation.

When the user presses Ctrl+S on a tree that doesn't satisfy its
schema, the StudioApp pushes a modal listing every validation error.
The user reads them, presses Esc, and lands back on the ConfigScreen
to fix things.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.screens import ConfigScreen, ErrorsScreen


class _Required(BaseModel):
    api_key: str = Field(...)
    db_host: str = Field(...)


@pytest.mark.asyncio
async def test_save_with_validation_failure_pushes_errors_screen(tmp_path):
    """Ctrl+S on a tree missing required fields pushes ErrorsScreen."""
    save = tmp_path / "config.yaml"
    tree = build_form_tree(_Required)
    app = StudioApp(tree=tree, save_path=save)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.pause()
        active = app.screen
        assert isinstance(active, ErrorsScreen), (
            f"Expected ErrorsScreen on top of stack, got {type(active).__name__}"
        )


@pytest.mark.asyncio
async def test_errors_screen_lists_every_error(tmp_path):
    """The pushed screen surfaces each error string."""
    save = tmp_path / "config.yaml"
    tree = build_form_tree(_Required)
    app = StudioApp(tree=tree, save_path=save)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ErrorsScreen)
        # Both api_key and db_host are required+unset, so the error
        # list should reference both field names.
        rendered = screen.error_text
        assert "api_key" in rendered, (
            f"Expected 'api_key' in error screen body; got: {rendered!r}"
        )
        assert "db_host" in rendered, (
            f"Expected 'db_host' in error screen body; got: {rendered!r}"
        )


@pytest.mark.asyncio
async def test_esc_on_errors_screen_pops_back_to_config(tmp_path):
    """Esc on ErrorsScreen returns to the ConfigScreen underneath."""
    save = tmp_path / "config.yaml"
    tree = build_form_tree(_Required)
    app = StudioApp(tree=tree, save_path=save)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, ErrorsScreen)
        await pilot.press("escape")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen), (
            f"Expected ConfigScreen after Esc, got {type(app.screen).__name__}"
        )


@pytest.mark.asyncio
async def test_successful_save_does_not_push_errors_screen(tmp_path):
    """When save succeeds, no ErrorsScreen is pushed."""

    class _Trivial(BaseModel):
        name: str = "alpha"

    save = tmp_path / "config.yaml"
    tree = build_form_tree(_Trivial)
    app = StudioApp(tree=tree, save_path=save)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen), (
            f"Expected ConfigScreen after successful save, got {type(app.screen).__name__}"
        )
