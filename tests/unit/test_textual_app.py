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


@pytest.mark.asyncio
async def test_save_writes_yaml(tmp_path) -> None:
    """Ctrl+S persists the tree to save_path via save_yaml."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    out = tmp_path / "out.yaml"
    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=out)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
    # File should exist with the schema's defaults.
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "name:" in content
    assert "port:" in content


@pytest.mark.asyncio
async def test_undo_reverts_last_mutation(tmp_path) -> None:
    """Ctrl+Z calls tree.undo() and refreshes the preview."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    # Explicit seed (was implicit via default-seeding).
    tree.set_value("port", 8080)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Mutate via direct API (simpler than driving through widgets).
        tree.set_value("port", 9999)
        port_node = tree.root.find("port")
        assert port_node is not None
        assert port_node.value == 9999
        # Trigger undo.
        await pilot.press("ctrl+z")
        await pilot.pause()
        # Tree restored.
        port_node_after = tree.root.find("port")
        assert port_node_after is not None
        # The default for Server.port is 8080.
        assert port_node_after.value == 8080


@pytest.mark.asyncio
async def test_smoke_edit_save_cycle(tmp_path) -> None:
    """End-to-end: build tree, mutate via API, save via Ctrl+S, reload, verify."""
    from pydantic_studio import (
        StudioApp,
        build_form_tree,
        load_yaml,
    )

    out = tmp_path / "smoke.yaml"
    tree = build_form_tree(Server)
    tree.set_value("name", "smoke-test")
    tree.set_value("port", 12345)
    app = StudioApp(tree=tree, save_path=out)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert out.exists()
    reloaded = load_yaml(out, Server)
    instance = reloaded.to_instance()
    assert instance.name == "smoke-test"
    assert instance.port == 12345


@pytest.mark.asyncio
async def test_smoke_edit_save_cycle_with_enum(tmp_path) -> None:
    """End-to-end: enum-bearing schema, edit-save round-trip."""
    from enum import Enum

    from pydantic import BaseModel

    from pydantic_studio import StudioApp, build_form_tree, load_yaml

    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    class M(BaseModel):
        favorite: Color = Color.RED

    out = tmp_path / "smoke_enum.yaml"
    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=out)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert out.exists()
    reloaded = load_yaml(out, M)
    instance = reloaded.to_instance()
    assert instance.favorite == Color.RED


@pytest.mark.asyncio
async def test_quit_prompts_when_dirty(tmp_path) -> None:
    """If the tree has been mutated, Ctrl+Q sets _quit_confirm_active."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    tree.set_value("port", 9999)  # dirty
    app = StudioApp(tree=tree, save_path=tmp_path / "out.yaml")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+q")
        await pilot.pause()
        screen = app.screen
        # The first Ctrl+Q should NOT exit; instead it sets the confirm flag.
        assert getattr(screen, "_quit_confirm_active", False) is True
        # Second Ctrl+Q within the window confirms exit.
        await pilot.press("ctrl+q")
        await pilot.pause()


@pytest.mark.asyncio
async def test_quit_does_not_prompt_when_clean(tmp_path) -> None:
    """Fresh tree with no mutations + Ctrl+Q exits cleanly without setting confirm."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=tmp_path / "out.yaml")
    async with app.run_test() as pilot:
        await pilot.pause()
        # Don't mutate; press Ctrl+Q.
        await pilot.press("ctrl+q")
        await pilot.pause()
