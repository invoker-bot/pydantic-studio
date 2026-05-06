"""Smoke tests for the StudioApp scaffold via Pilot."""

from __future__ import annotations

import pytest

from tests.fixtures.schemas import Server


@pytest.mark.asyncio
async def test_app_starts_and_quits_cleanly() -> None:
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        assert app.tree is tree
        # Press Ctrl+Q to quit.
        await pilot.press("ctrl+q")
        await pilot.pause()
    # After context exit, the app is no longer running.
    # Pilot's test harness handles app cleanup automatically.
