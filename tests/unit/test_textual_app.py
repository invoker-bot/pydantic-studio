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


@pytest.mark.asyncio
async def test_sidebar_lists_top_level_groups() -> None:
    """Sidebar renders the root GroupNode and any nested GroupNode children."""
    from pydantic import BaseModel

    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    class Inner(BaseModel):
        x: int = 0

    class Outer(BaseModel):
        inner: Inner = Inner()
        leaf: str = "hi"

    tree = build_form_tree(Outer)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        sidebar = app.screen.query_one("#sidebar")
        # The sidebar should expose the root + the nested group "inner".
        labels = _collect_tree_labels(sidebar)
        assert any("Outer" in label or "<root>" in label for label in labels)
        # The nested Inner group is visible.
        assert any("inner" in label for label in labels)


def _collect_tree_labels(sidebar) -> list[str]:
    """Walk a Textual Tree widget and collect all visible node labels as strings."""
    labels: list[str] = []

    def walk(node) -> None:
        labels.append(str(node.label))
        for child in node.children:
            walk(child)

    walk(sidebar.root)
    return labels
