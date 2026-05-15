"""Unit tests for StudioApp.on_mount — verifies ConfigScreen is the
single screen the app mounts after the legacy cutover.

Pre-cutover, the dispatch was env-var gated. The env var was removed
once the legacy EditorScreen + its sidebar/editor/preview widgets were
deleted; there is no other screen to dispatch to.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.screens import ConfigScreen
from pydantic_studio.renderers.textual_.widgets.breadcrumb import Breadcrumb


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 5


@pytest.mark.asyncio
async def test_studio_app_mounts_config_screen() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen)


@pytest.mark.asyncio
async def test_studio_app_seeds_breadcrumb_with_schema_short_name() -> None:
    """The breadcrumb's first segment is the schema's short class name
    (the part after the last ``:`` in the qualified name, else the whole
    name).
    """
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        # _Schema's fully-qualified name ends with "_Schema" — the
        # breadcrumb shows just the short tail.
        assert bc.label_text.endswith("_Schema")
