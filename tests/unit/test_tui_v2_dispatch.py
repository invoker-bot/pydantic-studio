"""Unit tests for the StudioApp env-var dispatch between the legacy
EditorScreen and the new ConfigScreen.
"""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.screens import ConfigScreen, EditorScreen


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 5


@pytest.mark.asyncio
async def test_studio_app_default_pushes_editor_screen() -> None:
    """Without the env var, the legacy EditorScreen is what mounts."""
    # Ensure the flag is unset (some dev shells may have it on).
    prior = os.environ.pop("PYDANTIC_STUDIO_TUI_V2", None)
    try:
        tree = build_form_tree(_Schema)
        app = StudioApp(tree=tree, save_path=None)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, EditorScreen)
    finally:
        if prior is not None:
            os.environ["PYDANTIC_STUDIO_TUI_V2"] = prior


@pytest.mark.asyncio
async def test_studio_app_v2_flag_pushes_config_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With PYDANTIC_STUDIO_TUI_V2=1, ConfigScreen takes over."""
    monkeypatch.setenv("PYDANTIC_STUDIO_TUI_V2", "1")
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen)
