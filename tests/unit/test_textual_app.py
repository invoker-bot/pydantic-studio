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


@pytest.mark.asyncio
async def test_preview_renders_yaml_on_mount() -> None:
    """The preview pane should render the current tree as YAML."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()  # let on_mount push EditorScreen
        preview = app.screen.query_one("#preview")
        # The preview widget should have content with the schema's defaults.
        rendered = _read_log_lines(preview)
        all_text = "\n".join(rendered)
        assert "name:" in all_text
        assert "port:" in all_text


def _read_log_lines(widget) -> list[str]:
    """Extract text lines from a RichLog widget. Pilot has no direct
    accessor, so we reach into the widget's internal Strip list."""
    if hasattr(widget, "lines"):
        return [str(line) for line in widget.lines]
    return []


@pytest.mark.asyncio
async def test_editor_pane_mounts() -> None:
    """The editor pane mounts; concrete child editors land in T6+."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.screen.query_one("#editor")
        assert editor is not None


@pytest.mark.asyncio
async def test_editor_pane_mounts_one_input_per_field() -> None:
    """After T6, Server's name+port get TextInputEditors; debug uses BoolEditor stub."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Input

        inputs = list(app.screen.query(Input))
        # Server has name (str), port (int), debug (bool).
        # Bool gets a stub Static -> 2 Input widgets (name, port).
        assert len(inputs) == 2
