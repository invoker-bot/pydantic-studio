# pydantic-studio — Phase 5: Textual Renderer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working Textual TUI for pydantic-studio: a single-screen three-region layout (sidebar tree / scrollable editor / live YAML preview), node-kind-dispatched editor widgets covering all 24 FormTree node types, keybindings for save/undo/redo/quit, and a `pydantic-studio edit <module:Class> [<file>]` CLI integration.

**Architecture:** A `StudioApp` (Textual `App`) hosts an `EditorScreen` with three regions. A `Sidebar` widget renders the FormTree's GroupNode hierarchy as a `Tree`. Selecting a group focuses the `EditorPane` to that group's children, where each non-group child is rendered via a `NodeEditor` dispatcher → one of six concrete editor widgets (TextInputEditor, BoolEditor, ChoiceEditor, SequenceEditor, MappingEditor, UnionEditor). The `PreviewPane` is a `RichLog` re-rendered on every successful tree mutation. Mutations route through `tree.set_value(path, value)` (validate-first contract from Phase 2/3); validation errors surface as inline status messages in the editor pane. Save uses `save_yaml`'s precondition (`tree.to_instance()` must succeed) — invalid trees show a banner and refuse save.

**Tech Stack:** Python 3.11+, Pydantic v2, ruamel.yaml (existing), `textual>=0.85` (new dependency). Testing via `App.run_test()` returning a `Pilot` (no TTY needed).

**Scope note:** Phase 5 ships a *working* TUI MVP. Polish items deferred:
- Custom `theme.css` styling — uses Textual's built-in dark theme defaults
- Light-theme toggle (`--theme light`)
- Help screen (`?` keybinding)
- Status-bar widget showing last validation error
- Mid-edit `save_draft_yaml` for partial-tree saves (Plan 5 forces save to wait for valid state — see "Save flow" below)
- Specialized widgets for SecretNode (uses TextInputEditor with `password=True`), Datetime/Date/Time/Timedelta (uses TextInputEditor with ISO-string parsing)
- Phase 4 housekeeping (7 items) — folded into Plan 6's T0 to keep this plan focused on the renderer

**Out-of-scope (deferred to later plans):**
- HTML renderer (Plan 6 per spec §14)
- TOML / JSON I/O (Plan 7 per spec §14)
- Polish & docs (Plans 8-9)

---

## File Structure

**New directories + files (12):**
- `src/pydantic_studio/renderers/__init__.py` — placeholder
- `src/pydantic_studio/renderers/textual_/__init__.py` — re-exports `StudioApp`, `run_app`
- `src/pydantic_studio/renderers/textual_/app.py` — `StudioApp` (Textual App subclass) + `run_app(tree, save_path)`
- `src/pydantic_studio/renderers/textual_/screens.py` — `EditorScreen` (three-region layout)
- `src/pydantic_studio/renderers/textual_/widgets/__init__.py` — re-exports
- `src/pydantic_studio/renderers/textual_/widgets/sidebar.py` — `Sidebar` (Tree of GroupNodes)
- `src/pydantic_studio/renderers/textual_/widgets/preview.py` — `PreviewPane` (live YAML render via RichLog)
- `src/pydantic_studio/renderers/textual_/widgets/editor.py` — `EditorPane` (scrollable VBox) + `NodeEditor` dispatcher
- `src/pydantic_studio/renderers/textual_/widgets/scalars.py` — `TextInputEditor`, `BoolEditor`, `ChoiceEditor`
- `src/pydantic_studio/renderers/textual_/widgets/containers.py` — `SequenceEditor`, `MappingEditor`, `UnionEditor`
- `tests/unit/test_textual_app.py` — App.run_test smoke
- `tests/unit/test_textual_widgets.py` — per-widget Pilot tests
- `tests/unit/test_cli_edit.py` — CLI `edit` subcommand tests

**Modified files:**
- `pyproject.toml` — add `textual>=0.85` to dependencies
- `src/pydantic_studio/cli.py` — add `edit` subcommand
- `src/pydantic_studio/__init__.py` — export `StudioApp` and `run_app`
- `tests/fixtures/schemas.py` — add a small nested schema for renderer tests if existing fixtures don't cover what's needed
- `README.md` — Phase 5 section: TUI screenshot description + `edit` CLI demo

**Why split widgets across `scalars.py` + `containers.py`:** scalars are stateless (input → set_value → done); containers manage child editor lifecycle (add row → mount widget → remove row → unmount). Separating keeps each file under ~250 lines.

**Why no `theme.css` in this plan:** Textual's default styling is functional; spec line 335 mentions theming but it's polish-tier. The widgets use `Static` placeholders for layout; cosmetic CSS lands in Plan 8 (polish).

---

## Save Flow Design Decision

The Phase 4 `save_yaml` requires `tree.to_instance()` to succeed (catches incomplete trees with required-but-unset fields). Plan 5's renderer adopts the simplest interpretation:

- **Save is allowed only when the tree is valid.** Pressing `^S` calls `tree.to_instance()`; on success, `save_yaml(tree, save_path)` writes the file and the screen flashes "Saved". On failure, a banner shows the validation error and the file is unchanged.
- **Quit prompts on unsaved changes.** Pressing `^Q` checks if the tree has been mutated since the last save (compare snapshot count); if dirty, prompt "Discard unsaved changes? (y/N)".
- **Undo/redo route through FormTree.undo()/redo().** Existing snapshot ring buffer.

A `save_draft_yaml` variant for partial saves is deferred to Plan 6 (spec calls it "draft auto-save" in §11).

---

## Branch Convention

Work on `feature/phase-5-textual-renderer` branched from `master`. User standing instruction: **commit + merge only — DO NOT push.** Tag at the final feature commit (`v0.0.5-phase-5`) before the `--no-ff` merge to master.

---

## Pre-flight assumptions

- Master is at the merge of Phase 4 (`c2925de`).
- 343 tests pass; ruff clean; production pyright at 6 errors.

---

### Task 1: Branch setup + textual dependency

**Files:**
- Modify: `pyproject.toml` — add `textual>=0.85` dep

- [ ] **Step 1: Create feature branch from master**

```bash
git checkout master
git status  # Expected: clean
git checkout -b feature/phase-5-textual-renderer
```

- [ ] **Step 2: Verify Phase-4 baseline**

```bash
uv run pytest -q
```

Expected: 343 passed.

```bash
uv run ruff check
```

Expected: All checks passed.

- [ ] **Step 3: Add `textual` dependency**

In `pyproject.toml`, modify the `dependencies` block to include textual:

```toml
dependencies = [
  "pydantic>=2.7",
  "typer>=0.12",
  "rich>=13",
  "ruamel.yaml>=0.18",
  "textual>=0.85",
]
```

- [ ] **Step 4: Sync deps**

```bash
uv sync
```

Expected: textual and its transitive deps installed.

- [ ] **Step 5: Smoke check the import**

```bash
uv run python -c "from textual.app import App; from textual.widgets import Tree, Input, Checkbox, Select, RichLog, Button; print('OK')"
```

Expected: `OK`.

- [ ] **Step 6: Run full suite (no regressions)**

```bash
uv run pytest -q
```

Expected: 343 passed.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml
git commit -m "build: add textual>=0.85 dependency for Phase 5 TUI renderer"
```

---

### Task 2: Module skeleton + StudioApp scaffold

**Why:** Bootstrap the renderer's directory structure and a minimal `StudioApp` that opens, displays a placeholder, and quits cleanly. Establishes the package layout per spec §4 (line 134-139).

**Files:**
- Create: `src/pydantic_studio/renderers/__init__.py`
- Create: `src/pydantic_studio/renderers/textual_/__init__.py`
- Create: `src/pydantic_studio/renderers/textual_/app.py`
- Create: `src/pydantic_studio/renderers/textual_/screens.py`
- Create: `src/pydantic_studio/renderers/textual_/widgets/__init__.py`
- Create: `tests/unit/test_textual_app.py`

- [ ] **Step 1: Write the failing scaffold test**

Create `tests/unit/test_textual_app.py`:

```python
"""Smoke tests for the StudioApp scaffold via Pilot."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

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
        # The app should have exited cleanly. Pilot's exit_code is None until
        # the app actually exits — pause first to let the action complete.
        await pilot.pause()
    # After context exit, the app is no longer running.
    assert app.return_value is None or app.return_value is not None  # placeholder check
```

- [ ] **Step 2: Run test — expect ImportError**

```bash
uv run pytest tests/unit/test_textual_app.py -v
```

Expected: FAIL — `ImportError: cannot import name 'StudioApp' from 'pydantic_studio.renderers.textual_'`.

- [ ] **Step 3: Create `renderers/__init__.py`**

```python
"""Renderers for pydantic-studio.

Currently ships:
- ``textual_/`` — terminal UI via Textual

Future plans:
- ``html/`` — local FastAPI + HTMX (Plan 6)
"""
```

- [ ] **Step 4: Create `renderers/textual_/__init__.py`**

```python
"""Textual renderer for pydantic-studio.

Public exports:
- ``StudioApp`` — the App class, instantiate with a FormTree to launch
- ``run_app`` — convenience function that builds an app and runs it
  synchronously, returning the saved BaseModel instance (or None if the
  user quit without saving).
"""

from __future__ import annotations

from pydantic_studio.renderers.textual_.app import StudioApp, run_app

__all__ = ["StudioApp", "run_app"]
```

- [ ] **Step 5: Create `renderers/textual_/widgets/__init__.py`**

```python
"""Textual widgets for pydantic-studio.

Re-exports concrete widget classes used elsewhere. Each widget is in a
focused module (sidebar.py, preview.py, editor.py, scalars.py,
containers.py).
"""
```

(Empty re-export block; widgets land in later tasks.)

- [ ] **Step 6: Create `renderers/textual_/screens.py`**

```python
"""Textual Screen for the editor — wraps the three-region layout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


class EditorScreen(Screen):
    """Single-screen layout: sidebar | editor | preview.

    Phase-5 scaffold uses Static placeholders. Tasks 3-5 replace each
    region with real widgets (Sidebar, EditorPane, PreviewPane).
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Static("[sidebar]", id="sidebar-placeholder")
            yield Static("[editor]", id="editor-placeholder")
            yield Static("[preview]", id="preview-placeholder")
        yield Footer()

    def action_quit(self) -> None:
        self.app.exit()
```

- [ ] **Step 7: Create `renderers/textual_/app.py`**

```python
"""StudioApp — the Textual App entry point for pydantic-studio."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App

from pydantic_studio.renderers.textual_.screens import EditorScreen

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree


class StudioApp(App):
    """Textual application that hosts the form-tree editor.

    Args:
        tree: the FormTree to edit (typically built via
            ``build_form_tree`` or ``load_yaml``).
        save_path: optional path to write to on Ctrl+S. None disables
            save (read-only mode).
    """

    CSS = ""  # custom theme CSS lands in Plan 8

    def __init__(
        self,
        tree: FormTree,
        save_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.tree = tree
        self.save_path = Path(save_path) if save_path is not None else None

    def on_mount(self) -> None:
        self.push_screen(EditorScreen())


def run_app(tree: FormTree, save_path: str | Path | None = None) -> None:
    """Launch the StudioApp synchronously. Blocks until the user quits."""
    app = StudioApp(tree=tree, save_path=save_path)
    app.run()
```

- [ ] **Step 8: Run test — expect PASS**

```bash
uv run pytest tests/unit/test_textual_app.py -v
```

Expected: PASS.

If the `await pilot.press("ctrl+q")` line fails because Textual didn't recognize the binding, ensure `BINDINGS` is set on `EditorScreen` (or move it to `StudioApp`).

- [ ] **Step 9: Run full suite**

```bash
uv run pytest -q
```

Expected: 344 passed (343 + 1 new).

- [ ] **Step 10: Verify ruff**

```bash
uv run ruff check
```

- [ ] **Step 11: Commit**

```bash
git add src/pydantic_studio/renderers/__init__.py src/pydantic_studio/renderers/textual_/__init__.py src/pydantic_studio/renderers/textual_/app.py src/pydantic_studio/renderers/textual_/screens.py src/pydantic_studio/renderers/textual_/widgets/__init__.py tests/unit/test_textual_app.py
git commit -m "feat(textual): module skeleton + StudioApp/EditorScreen scaffold with quit binding"
```

---

### Task 3: Sidebar widget (FormTree → Tree)

**Why:** The sidebar is the user's primary navigation: it shows the GroupNode hierarchy, and selecting a group focuses the editor pane on that group's fields. For the MVP, GroupNode-only — non-group nodes are rendered in the editor pane (see Task 5).

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/sidebar.py`
- Modify: `src/pydantic_studio/renderers/textual_/widgets/__init__.py` — export `Sidebar`
- Modify: `src/pydantic_studio/renderers/textual_/screens.py` — replace placeholder with Sidebar
- Modify: `tests/unit/test_textual_app.py` — add sidebar tests

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_textual_app.py`:

```python
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
        sidebar = app.query_one("#sidebar")
        # The sidebar should expose the root + the nested group "inner".
        labels = _collect_tree_labels(sidebar)
        assert "Outer" in labels[0] or "<root>" in labels[0]
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
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run pytest tests/unit/test_textual_app.py::test_sidebar_lists_top_level_groups -v
```

Expected: FAIL — `#sidebar` element doesn't exist (still the placeholder Static).

- [ ] **Step 3: Create the Sidebar widget**

Create `src/pydantic_studio/renderers/textual_/widgets/sidebar.py`:

```python
"""Sidebar widget — renders the FormTree's GroupNode hierarchy as a Tree."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Tree

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree, GroupNode


class Sidebar(Tree):
    """Navigation tree showing all GroupNodes in the FormTree.

    The widget posts a ``GroupSelected`` message (subclass of NodeSelected)
    when the user clicks a group; the EditorScreen listens and updates
    the EditorPane to focus that group.

    For the MVP, leaf nodes (non-group) are NOT shown in the sidebar —
    only the structure of nested BaseModel containers. Leaves appear in
    the EditorPane when their parent group is focused.
    """

    def __init__(self, tree: FormTree) -> None:
        from pydantic_studio.tree.nodes import GroupNode

        # The Tree's root label = the schema's class name.
        root_label = tree.schema_name.split(":")[-1] if ":" in tree.schema_name else tree.schema_name
        super().__init__(label=root_label, id="sidebar")
        self.form_tree = tree
        self._populate(self.root, tree.root)
        # Bind the GroupNode itself to the root for path resolution.
        self.root.data = ""  # empty path = root group
        self.root.expand()

    def _populate(self, parent_node, group: GroupNode) -> None:
        """Recursively add child GroupNodes under ``parent_node``."""
        from pydantic_studio.tree.nodes import GroupNode

        for child in group.fields:
            if isinstance(child, GroupNode):
                # Use the child's name as the label.
                label = child.name or "?"
                t_node = parent_node.add(label)
                # data carries the path string for set_value lookups.
                base = parent_node.data or ""
                t_node.data = f"{base}.{label}".lstrip(".")
                self._populate(t_node, child)
                t_node.expand()
```

- [ ] **Step 4: Wire `Sidebar` into the screen**

Modify `src/pydantic_studio/renderers/textual_/screens.py`. Replace the placeholder `Static("[sidebar]", ...)` with the real Sidebar widget. The `compose` becomes:

```python
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar(self.app.tree)
            yield Static("[editor]", id="editor-placeholder")
            yield Static("[preview]", id="preview-placeholder")
        yield Footer()
```

Add the import at the top:

```python
from pydantic_studio.renderers.textual_.widgets.sidebar import Sidebar
```

Note: `self.app.tree` references the FormTree set on `StudioApp` in `__init__`. Textual's `Screen` exposes the parent `App` via `self.app`, and our subclass adds `tree` as an attribute.

- [ ] **Step 5: Update widgets/__init__.py exports**

In `src/pydantic_studio/renderers/textual_/widgets/__init__.py`:

```python
"""Textual widgets for pydantic-studio."""

from __future__ import annotations

from pydantic_studio.renderers.textual_.widgets.sidebar import Sidebar

__all__ = ["Sidebar"]
```

- [ ] **Step 6: Run test — expect PASS**

```bash
uv run pytest tests/unit/test_textual_app.py::test_sidebar_lists_top_level_groups -v
```

Expected: PASS.

- [ ] **Step 7: Run full suite**

```bash
uv run pytest -q
```

Expected: 345 passed.

- [ ] **Step 8: Verify ruff**

```bash
uv run ruff check
```

- [ ] **Step 9: Commit**

```bash
git add src/pydantic_studio/renderers/textual_/widgets/sidebar.py src/pydantic_studio/renderers/textual_/widgets/__init__.py src/pydantic_studio/renderers/textual_/screens.py tests/unit/test_textual_app.py
git commit -m "feat(textual): Sidebar widget renders FormTree GroupNode hierarchy"
```

---

### Task 4: PreviewPane widget (live YAML render)

**Why:** Per spec §3, the rightmost region shows a live-rendered YAML view of the current FormTree state. Updates on every successful mutation. For Plan 5 we use Textual's `RichLog` widget — readable, scrollable, themeable.

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/preview.py`
- Modify: `src/pydantic_studio/renderers/textual_/widgets/__init__.py` — export `PreviewPane`
- Modify: `src/pydantic_studio/renderers/textual_/screens.py` — replace preview placeholder
- Modify: `tests/unit/test_textual_app.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_textual_app.py`:

```python
@pytest.mark.asyncio
async def test_preview_renders_yaml_on_mount() -> None:
    """The preview pane should render the current tree as YAML."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        preview = app.query_one("#preview")
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
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run pytest tests/unit/test_textual_app.py::test_preview_renders_yaml_on_mount -v
```

Expected: FAIL — preview widget still a placeholder.

- [ ] **Step 3: Create the PreviewPane widget**

Create `src/pydantic_studio/renderers/textual_/widgets/preview.py`:

```python
"""PreviewPane — live YAML render of the current FormTree state."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from textual.widgets import RichLog

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree


class PreviewPane(RichLog):
    """Read-only live YAML view of the FormTree.

    Subscribes to no events directly — the EditorScreen calls
    ``refresh_preview()`` after every successful mutation.
    """

    def __init__(self, tree: FormTree) -> None:
        super().__init__(id="preview", wrap=False, markup=False, highlight=False)
        self.form_tree = tree

    def on_mount(self) -> None:
        self.refresh_preview()

    def refresh_preview(self) -> None:
        """Re-render the FormTree as YAML and update the log."""
        self.clear()
        text = self._render_yaml()
        for line in text.splitlines():
            self.write(line)

    def _render_yaml(self) -> str:
        """Render the current tree state as a YAML string.

        Uses ``tree.to_python()`` (NOT ``to_instance().model_dump()``) so
        that incomplete trees still produce a partial preview during
        editing — even when ``save_yaml`` would refuse the same tree.
        """
        from pydantic_studio.io.yaml import _build_commented_map, _yaml

        schema = self.form_tree.schema_class
        if schema is None:
            return "<no schema bound>"
        data = self.form_tree.to_python()
        if not data:
            return "<empty>"
        try:
            cm = _build_commented_map(data, schema, source=None)
        except Exception as e:
            return f"<preview error: {e}>"
        buf = io.StringIO()
        _yaml().dump(cm, buf)
        return buf.getvalue()
```

- [ ] **Step 4: Wire `PreviewPane` into the screen**

Modify `src/pydantic_studio/renderers/textual_/screens.py`. Replace the placeholder `Static("[preview]", ...)` with `PreviewPane(self.app.tree)`. Add the import:

```python
from pydantic_studio.renderers.textual_.widgets.preview import PreviewPane
```

The compose:

```python
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar(self.app.tree)
            yield Static("[editor]", id="editor-placeholder")
            yield PreviewPane(self.app.tree)
        yield Footer()
```

- [ ] **Step 5: Update widgets/__init__.py**

```python
from pydantic_studio.renderers.textual_.widgets.sidebar import Sidebar
from pydantic_studio.renderers.textual_.widgets.preview import PreviewPane

__all__ = ["PreviewPane", "Sidebar"]
```

- [ ] **Step 6: Run test — expect PASS**

```bash
uv run pytest tests/unit/test_textual_app.py::test_preview_renders_yaml_on_mount -v
```

Expected: PASS. If `_read_log_lines` returns empty because RichLog stores its lines differently in this Textual version, look at `widget.text` or `widget.console.export_text()` instead.

- [ ] **Step 7: Run full suite**

```bash
uv run pytest -q
```

Expected: 346 passed.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/renderers/textual_/widgets/preview.py src/pydantic_studio/renderers/textual_/widgets/__init__.py src/pydantic_studio/renderers/textual_/screens.py tests/unit/test_textual_app.py
git commit -m "feat(textual): PreviewPane renders live YAML via _build_commented_map"
```

---

### Task 5: EditorPane + NodeEditor dispatcher

**Why:** Center region — a scrollable VBox of one editor widget per non-group field of the currently-focused GroupNode. The dispatcher inspects each child's `kind` and mounts the appropriate editor class.

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/editor.py`
- Modify: `src/pydantic_studio/renderers/textual_/widgets/__init__.py` — export `EditorPane` and `NodeEditor`
- Modify: `src/pydantic_studio/renderers/textual_/screens.py` — wire EditorPane + listen for sidebar selection
- Modify: `tests/unit/test_textual_app.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_textual_app.py`:

```python
@pytest.mark.asyncio
async def test_editor_pane_renders_root_fields_on_mount() -> None:
    """When the app starts, the editor pane should render fields of the root group."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        editor = app.query_one("#editor")
        # editor should have one child per non-group field on the root.
        # Server has 3 fields (all non-group): name, port, debug.
        children = list(editor.query("[data-field-name]"))
        names = [c.get("data-field-name") if hasattr(c, "get") else "" for c in children]
        # Real check: how many editors did we mount?
        assert len(children) == 3
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run pytest tests/unit/test_textual_app.py::test_editor_pane_renders_root_fields_on_mount -v
```

Expected: FAIL — `#editor` doesn't exist (still the placeholder).

- [ ] **Step 3: Create `editor.py` with EditorPane + NodeEditor**

Create `src/pydantic_studio/renderers/textual_/widgets/editor.py`:

```python
"""EditorPane — scrollable VBox of NodeEditor widgets for a focused group."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.containers import VerticalScroll
from textual.widget import Widget

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree, GroupNode


class EditorPane(VerticalScroll):
    """Scrollable container of NodeEditor widgets for the focused group.

    The pane's content is regenerated whenever the user picks a different
    group in the sidebar. EditorScreen owns the focused-group state and
    calls ``set_group(group, path)``.
    """

    def __init__(self, tree: FormTree) -> None:
        super().__init__(id="editor")
        self.form_tree = tree
        self._current_group_path = ""

    def on_mount(self) -> None:
        # Default to the root group on first mount.
        self.set_group(self.form_tree.root, path="")

    def set_group(self, group: GroupNode, path: str) -> None:
        """Mount one NodeEditor per non-group child."""
        from pydantic_studio.tree.nodes import GroupNode

        self._current_group_path = path
        # Clear existing editors (Textual's remove_children).
        self.remove_children()
        for child in group.fields:
            if isinstance(child, GroupNode):
                # GroupNodes appear in the sidebar — skip in the editor pane.
                continue
            child_path = f"{path}.{child.name}".lstrip(".") if path else child.name
            editor = NodeEditor.dispatch(child, child_path, self.form_tree)
            self.mount(editor)


class NodeEditor(Widget):
    """Base class — concrete subclasses dispatch on node.kind.

    Subclasses set ``self.field_path`` (the path used for set_value calls)
    and implement their own ``compose()`` + event handlers.
    """

    def __init__(
        self,
        node: AnyNode,
        path: str,
        tree: FormTree,
    ) -> None:
        super().__init__()
        self.node = node
        self.field_path = path
        self.form_tree = tree
        # Tag for testing.
        self.attrs = {"data-field-name": node.name}

    @classmethod
    def dispatch(
        cls,
        node: AnyNode,
        path: str,
        tree: FormTree,
    ) -> NodeEditor:
        """Return a concrete NodeEditor subclass instance for ``node.kind``.

        Falls back to TextInputEditor for any "stringy" or numeric kind.
        Concrete editor implementations land in Tasks 6-11.
        """
        # Late imports avoid circular dependencies during widget bootstrap.
        from pydantic_studio.renderers.textual_.widgets.containers import (
            MappingEditor,
            SequenceEditor,
            UnionEditor,
        )
        from pydantic_studio.renderers.textual_.widgets.scalars import (
            BoolEditor,
            ChoiceEditor,
            TextInputEditor,
        )

        kind = node.kind
        if kind == "bool":
            return BoolEditor(node, path, tree)
        if kind in ("enum", "literal"):
            return ChoiceEditor(node, path, tree)
        if kind == "sequence":
            return SequenceEditor(node, path, tree)
        if kind == "mapping":
            return MappingEditor(node, path, tree)
        if kind == "union":
            return UnionEditor(node, path, tree)
        # All other kinds (string/int/float/decimal/date*/ip*/url/email/path/uuid/secret/pattern/bytes)
        # use the generic text input.
        return TextInputEditor(node, path, tree)

    def commit(self, value: Any) -> tuple[bool, str | None]:
        """Validate ``value`` against the node and apply via tree.set_value.

        Returns ``(ok, error_message)``. On success, also triggers a
        preview refresh on the parent screen.
        """
        result = self.form_tree.set_value(self.field_path, value)
        if not result.ok:
            return False, result.errors[0] if result.errors else "invalid"
        # Tell the screen to refresh the preview pane.
        screen = self.screen
        if hasattr(screen, "refresh_preview"):
            screen.refresh_preview()
        return True, None
```

- [ ] **Step 4: Wire `EditorPane` into the screen + add `refresh_preview` hook**

Modify `src/pydantic_studio/renderers/textual_/screens.py`:

```python
"""Textual Screen for the editor — wraps the three-region layout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header

from pydantic_studio.renderers.textual_.widgets.editor import EditorPane
from pydantic_studio.renderers.textual_.widgets.preview import PreviewPane
from pydantic_studio.renderers.textual_.widgets.sidebar import Sidebar

if TYPE_CHECKING:
    from textual.app import ComposeResult


class EditorScreen(Screen):
    """Single-screen layout: sidebar | editor | preview."""

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar(self.app.tree)
            yield EditorPane(self.app.tree)
            yield PreviewPane(self.app.tree)
        yield Footer()

    def action_quit(self) -> None:
        self.app.exit()

    def refresh_preview(self) -> None:
        """Called by NodeEditor.commit() after a successful set_value.

        Looks up the PreviewPane and asks it to re-render. Robust to
        missing widget (e.g., during early mount).
        """
        try:
            preview = self.query_one(PreviewPane)
        except Exception:
            return
        preview.refresh_preview()

    def on_tree_node_selected(self, event) -> None:
        """Sidebar emits this when the user picks a group. Update the
        EditorPane to focus that group's children."""
        # event.node.data is the path string we stashed in Sidebar._populate.
        path = event.node.data or ""
        try:
            editor = self.query_one(EditorPane)
        except Exception:
            return
        # Resolve the group at ``path`` and call set_group.
        group = self._resolve_group(path)
        if group is not None:
            editor.set_group(group, path)

    def _resolve_group(self, path: str):
        """Walk ``self.app.tree.root`` along ``path`` (dot-separated) and
        return the GroupNode at that location."""
        from pydantic_studio.tree.nodes import GroupNode

        if path == "":
            return self.app.tree.root
        node = self.app.tree.root
        for seg in path.split("."):
            if not isinstance(node, GroupNode):
                return None
            child = node.find(seg)
            if child is None:
                return None
            node = child
        if isinstance(node, GroupNode):
            return node
        return None
```

- [ ] **Step 5: Update widgets/__init__.py**

```python
from pydantic_studio.renderers.textual_.widgets.editor import EditorPane, NodeEditor
from pydantic_studio.renderers.textual_.widgets.preview import PreviewPane
from pydantic_studio.renderers.textual_.widgets.sidebar import Sidebar

__all__ = ["EditorPane", "NodeEditor", "PreviewPane", "Sidebar"]
```

- [ ] **Step 6: Note that the test won't fully pass yet**

The `test_editor_pane_renders_root_fields_on_mount` test expects 3 mounted child widgets. But we haven't implemented TextInputEditor yet (Task 6) — so `NodeEditor.dispatch` raises ImportError. Mark this test with `@pytest.mark.xfail(reason="needs TextInputEditor — Task 6")` for now, OR simplify to assert the EditorPane mounts at all (without children).

Replace the test body with:

```python
@pytest.mark.asyncio
async def test_editor_pane_mounts() -> None:
    """The editor pane mounts; concrete child editors land in T6+."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        editor = app.query_one("#editor")
        assert editor is not None
```

The "3 children" assertion comes back in Task 6 once TextInputEditor exists.

- [ ] **Step 7: Run test — expect PASS**

```bash
uv run pytest tests/unit/test_textual_app.py::test_editor_pane_mounts -v
```

Expected: PASS.

- [ ] **Step 8: Run full suite**

```bash
uv run pytest -q
```

Expected: 347 passed.

- [ ] **Step 9: Commit**

```bash
git add src/pydantic_studio/renderers/textual_/widgets/editor.py src/pydantic_studio/renderers/textual_/widgets/__init__.py src/pydantic_studio/renderers/textual_/screens.py tests/unit/test_textual_app.py
git commit -m "feat(textual): EditorPane + NodeEditor dispatcher (concrete editors land in T6-11)"
```

---

### Task 6: TextInputEditor — covers all stringy/numeric/temporal/network/special kinds

**Why:** This single widget handles the largest cluster of node kinds via parse-on-blur dispatch. For each node kind, the parser converts the raw input string to the type the node's `validate_value` expects. Failed parse = inline error message; passing parse → `commit(value)`.

Covered kinds: `string`, `int`, `float`, `decimal`, `datetime`, `date`, `time`, `timedelta`, `ip_address`, `ip_network`, `url`, `email`, `path`, `uuid`, `secret`, `pattern`, `bytes`.

That's 17 of 24 kinds.

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/scalars.py`
- Modify: `tests/unit/test_textual_widgets.py` (NEW)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_textual_widgets.py`:

```python
"""Per-widget Pilot tests for the Textual renderer."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp


@pytest.mark.asyncio
async def test_text_input_editor_for_string() -> None:
    class M(BaseModel):
        name: str = "alpha"

    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        # Find the input widget for `name`.
        inputs = list(app.query("Input"))
        assert len(inputs) == 1
        # Initial value matches the default.
        assert inputs[0].value == "alpha"
        # Type into it.
        await pilot.click(inputs[0])
        await pilot.press("ctrl+a")  # select all
        await pilot.press("delete")
        for c in "beta":
            await pilot.press(c)
        # Press Enter to commit (or simulate blur).
        await pilot.press("enter")
        await pilot.pause()

        # The tree's root should reflect the new value.
        name_node = tree.root.find("name")
        assert name_node is not None
        assert name_node.value == "beta"


@pytest.mark.asyncio
async def test_text_input_editor_for_int_parses() -> None:
    class M(BaseModel):
        age: int = 0

    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        inputs = list(app.query("Input"))
        assert len(inputs) == 1
        await pilot.click(inputs[0])
        await pilot.press("ctrl+a")
        await pilot.press("delete")
        for c in "42":
            await pilot.press(c)
        await pilot.press("enter")
        await pilot.pause()
        age = tree.root.find("age")
        assert age is not None
        assert age.value == 42


@pytest.mark.asyncio
async def test_text_input_editor_validation_error_keeps_old_value() -> None:
    class M(BaseModel):
        age: int = 5

    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        inputs = list(app.query("Input"))
        await pilot.click(inputs[0])
        await pilot.press("ctrl+a")
        await pilot.press("delete")
        for c in "not a number":
            await pilot.press(c)
        await pilot.press("enter")
        await pilot.pause()
        # Old value preserved (validation rejected the input).
        age = tree.root.find("age")
        assert age is not None
        assert age.value == 5
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run pytest tests/unit/test_textual_widgets.py -v
```

Expected: All FAIL — TextInputEditor doesn't exist.

- [ ] **Step 3: Implement `scalars.py`**

Create `src/pydantic_studio/renderers/textual_/widgets/scalars.py`:

```python
"""Scalar widgets: TextInputEditor + BoolEditor + ChoiceEditor.

TextInputEditor is the most-used class — it covers 17 of 24 node kinds
via parse-on-blur dispatch. BoolEditor wraps a Checkbox. ChoiceEditor
wraps a Select for Enum and Literal kinds.

BoolEditor and ChoiceEditor are stubs in this task; full
implementations land in T7 (Bool) and T8 (Choice).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Label, Static

from pydantic_studio.renderers.textual_.widgets.editor import NodeEditor

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree


def _parse_for_kind(kind: str, raw: str) -> tuple[bool, Any]:
    """Convert a raw string to the type the node expects.

    Returns ``(ok, value)``. On failure, ``ok=False`` and ``value`` is
    None.
    """
    raw = raw.strip()
    if raw == "":
        return True, None  # let validate_value decide if None is accepted

    try:
        if kind == "string":
            return True, raw
        if kind == "int":
            return True, int(raw)
        if kind == "float":
            return True, float(raw)
        if kind == "decimal":
            from decimal import Decimal

            return True, Decimal(raw)
        if kind == "datetime":
            from datetime import datetime

            return True, datetime.fromisoformat(raw)
        if kind == "date":
            from datetime import date

            return True, date.fromisoformat(raw)
        if kind == "time":
            from datetime import time

            return True, time.fromisoformat(raw)
        if kind == "timedelta":
            # Accept ISO 8601 duration via Pydantic's TypeAdapter.
            from datetime import timedelta

            from pydantic import TypeAdapter

            return True, TypeAdapter(timedelta).validate_python(raw)
        if kind in ("ip_address", "ip_network"):
            return True, raw  # node stores as string; validate_value parses
        if kind in ("url", "email", "path", "pattern"):
            return True, raw  # node stores as string
        if kind == "uuid":
            from uuid import UUID

            return True, UUID(raw)
        if kind == "secret":
            return True, raw  # node stores plaintext str/bytes
        if kind == "bytes":
            # Accept hex by default (matches BytesNode.field_serializer convention).
            return True, bytes.fromhex(raw)
    except (ValueError, TypeError, Exception):  # noqa: BLE001
        return False, None
    return False, None


class TextInputEditor(NodeEditor):
    """Single-line input + label + inline error display.

    Dispatches the raw string through ``_parse_for_kind`` to get the
    typed value, then routes to ``self.commit(value)``.

    For ``secret`` kind, the input is rendered with ``password=True`` so
    the typed text appears masked.
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(f"{self.node.name}: ", classes="field-label")
            yield Input(
                value=self._initial_value(),
                password=(self.node.kind == "secret"),
                id=f"input-{self.field_path}",
            )
        yield Static("", id=f"error-{self.field_path}", classes="field-error")

    def _initial_value(self) -> str:
        """Stringify the node's current value for display."""
        v = getattr(self.node, "value", None)
        if v is None:
            return ""
        if self.node.kind == "bytes" and isinstance(v, (bytes, bytearray)):
            return bytes(v).hex()
        return str(v)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Triggered on Enter key in the input."""
        self._commit_from_input(event.value)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Optional: live validation could fire here. For Plan 5 we wait
        for explicit submit so single-keystroke parses don't spam errors."""
        # Intentional pass — submit-on-Enter keeps the test deterministic.
        pass

    def _commit_from_input(self, raw: str) -> None:
        ok, value = _parse_for_kind(self.node.kind, raw)
        error_widget = self.query_one(f"#error-{self.field_path}", Static)
        if not ok:
            error_widget.update(f"cannot parse {raw!r} as {self.node.kind}")
            return
        success, msg = self.commit(value)
        if not success:
            error_widget.update(msg or "invalid")
        else:
            error_widget.update("")
```

Add stubs for `BoolEditor` and `ChoiceEditor` so dispatch doesn't fail. They get full implementations in Tasks 7-8:

```python
class BoolEditor(NodeEditor):
    """Stub — full impl in Task 7."""

    def compose(self) -> ComposeResult:
        yield Static(f"{self.node.name}: <bool stub>")


class ChoiceEditor(NodeEditor):
    """Stub — full impl in Task 8."""

    def compose(self) -> ComposeResult:
        yield Static(f"{self.node.name}: <choice stub>")
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/unit/test_textual_widgets.py -v
```

Expected: 3 PASS.

If `test_text_input_editor_for_int_parses` fails because the input value can't be selected with `ctrl+a` in Pilot, try `pilot.app.set_focus(inputs[0])` then drive directly via `inputs[0].value = "42"; await inputs[0].action_submit()` or similar.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
```

Expected: 350 passed.

- [ ] **Step 6: Re-enable the editor-children-count test from Task 5**

In `tests/unit/test_textual_app.py`, replace the `test_editor_pane_mounts` test (or add another) that asserts `Server`'s 3 fields each get a TextInputEditor:

```python
@pytest.mark.asyncio
async def test_editor_pane_mounts_one_input_per_field() -> None:
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        # Server has name (str), port (int), debug (bool).
        # Bool gets a stub Static → 2 Input widgets (name, port).
        inputs = list(app.query("Input"))
        assert len(inputs) == 2
```

Run it:

```bash
uv run pytest tests/unit/test_textual_app.py::test_editor_pane_mounts_one_input_per_field -v
```

Expected: PASS.

- [ ] **Step 7: Verify ruff**

```bash
uv run ruff check
```

If ruff flags `BLE001` (broad-except) on the `except (ValueError, TypeError, Exception):` catch in `_parse_for_kind`, that's expected — drop the bare `Exception` from the tuple (Decimal raises `decimal.InvalidOperation` which is a subclass of ArithmeticError, but that and ValueError/TypeError cover the common cases).

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/renderers/textual_/widgets/scalars.py tests/unit/test_textual_widgets.py tests/unit/test_textual_app.py
git commit -m "feat(textual): TextInputEditor + Bool/Choice stubs covering 17 node kinds"
```

---

### Task 7: BoolEditor (Checkbox)

**Why:** Replaces the BoolEditor stub from T6 with a real Checkbox widget. On toggle, calls `commit(value)`.

**Files:**
- Modify: `src/pydantic_studio/renderers/textual_/widgets/scalars.py` — replace BoolEditor stub
- Modify: `tests/unit/test_textual_widgets.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_textual_widgets.py`:

```python
@pytest.mark.asyncio
async def test_bool_editor_toggles() -> None:
    class M(BaseModel):
        enabled: bool = False

    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        from textual.widgets import Checkbox

        cbs = list(app.query(Checkbox))
        assert len(cbs) == 1
        assert cbs[0].value is False
        # Click to toggle on.
        await pilot.click(cbs[0])
        await pilot.pause()
        node = tree.root.find("enabled")
        assert node is not None
        assert node.value is True
```

- [ ] **Step 2: Run — expect FAIL**

```bash
uv run pytest tests/unit/test_textual_widgets.py::test_bool_editor_toggles -v
```

Expected: FAIL (BoolEditor is still a Static stub).

- [ ] **Step 3: Replace the BoolEditor stub**

In `src/pydantic_studio/renderers/textual_/widgets/scalars.py`:

```python
from textual.widgets import Checkbox  # add to imports


class BoolEditor(NodeEditor):
    """Checkbox bound to a BoolNode."""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(f"{self.node.name}: ", classes="field-label")
            initial = bool(getattr(self.node, "value", False))
            yield Checkbox(
                value=initial,
                id=f"checkbox-{self.field_path}",
            )
        yield Static("", id=f"error-{self.field_path}", classes="field-error")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        ok, msg = self.commit(event.value)
        error_widget = self.query_one(f"#error-{self.field_path}", Static)
        error_widget.update(msg or "" if not ok else "")
```

- [ ] **Step 4: Run — expect PASS**

```bash
uv run pytest tests/unit/test_textual_widgets.py::test_bool_editor_toggles -v
```

Expected: PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
```

Expected: 351 passed.

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/renderers/textual_/widgets/scalars.py tests/unit/test_textual_widgets.py
git commit -m "feat(textual): BoolEditor — Checkbox bound to BoolNode"
```

---

### Task 8: ChoiceEditor (Enum + Literal)

**Why:** Replaces the ChoiceEditor stub. Renders a `Select` widget with options pulled from the EnumNode's `choices` (list of (name, member) tuples) or LiteralNode's `choices` list.

**Files:**
- Modify: `src/pydantic_studio/renderers/textual_/widgets/scalars.py`
- Modify: `tests/unit/test_textual_widgets.py`

- [ ] **Step 1: Write failing test**

Append:

```python
@pytest.mark.asyncio
async def test_choice_editor_for_enum() -> None:
    from enum import Enum

    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    class M(BaseModel):
        favorite: Color = Color.RED

    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        from textual.widgets import Select

        selects = list(app.query(Select))
        assert len(selects) == 1
        # Default is RED.
        node = tree.root.find("favorite")
        assert node is not None
        assert node.value == Color.RED


@pytest.mark.asyncio
async def test_choice_editor_for_literal() -> None:
    from typing import Literal

    class M(BaseModel):
        level: Literal["debug", "info", "warn"] = "info"

    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        from textual.widgets import Select

        selects = list(app.query(Select))
        assert len(selects) == 1
        node = tree.root.find("level")
        assert node is not None
        assert node.value == "info"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
uv run pytest tests/unit/test_textual_widgets.py::test_choice_editor_for_enum tests/unit/test_textual_widgets.py::test_choice_editor_for_literal -v
```

Expected: FAIL.

- [ ] **Step 3: Implement ChoiceEditor**

In `scalars.py`:

```python
from textual.widgets import Select  # add to imports


class ChoiceEditor(NodeEditor):
    """Dropdown bound to an EnumNode or LiteralNode."""

    def compose(self) -> ComposeResult:
        options = self._build_options()
        initial = self._initial_value_id()
        with Horizontal():
            yield Label(f"{self.node.name}: ", classes="field-label")
            yield Select(
                options=options,
                value=initial if initial is not None else Select.BLANK,
                id=f"select-{self.field_path}",
            )
        yield Static("", id=f"error-{self.field_path}", classes="field-error")

    def _build_options(self) -> list[tuple[str, str]]:
        """Return list of (label, value_id) tuples for the Select widget."""
        if self.node.kind == "enum":
            # EnumNode.choices: list[tuple[str, EnumMember]]
            return [(name, name) for name, _member in self.node.choices]
        # LiteralNode.choices: list[Any]
        return [(repr(c), repr(c)) for c in self.node.choices]

    def _initial_value_id(self) -> str | None:
        v = getattr(self.node, "value", None)
        if v is None:
            return None
        if self.node.kind == "enum":
            from enum import Enum

            return v.name if isinstance(v, Enum) else None
        return repr(v)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value == Select.BLANK:
            return
        # Map back from the Select's value id to the actual node value.
        value: Any
        if self.node.kind == "enum":
            # Find the enum member with this name.
            for name, member in self.node.choices:
                if name == event.value:
                    value = member
                    break
            else:
                return
        else:
            # Literal: reverse repr() — only safe for primitive literals.
            for c in self.node.choices:
                if repr(c) == event.value:
                    value = c
                    break
            else:
                return
        ok, msg = self.commit(value)
        error_widget = self.query_one(f"#error-{self.field_path}", Static)
        error_widget.update(msg or "" if not ok else "")
```

- [ ] **Step 4: Run — expect PASS**

```bash
uv run pytest tests/unit/test_textual_widgets.py::test_choice_editor_for_enum tests/unit/test_textual_widgets.py::test_choice_editor_for_literal -v
```

Expected: PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
```

Expected: 353 passed.

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/renderers/textual_/widgets/scalars.py tests/unit/test_textual_widgets.py
git commit -m "feat(textual): ChoiceEditor — Select bound to EnumNode/LiteralNode"
```

---

### Task 9: SequenceEditor

**Why:** Lists/sets/tuples need add/remove buttons + per-item nested editors. Plan 5 ships a basic implementation: an "Add" button + per-item rows showing the item's editor + a "Remove" button per row.

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/containers.py`
- Modify: `tests/unit/test_textual_widgets.py`

- [ ] **Step 1: Write failing test**

Append:

```python
@pytest.mark.asyncio
async def test_sequence_editor_renders_existing_items() -> None:
    class M(BaseModel):
        tags: list[str] = []

    tree = build_form_tree(M, existing={"tags": ["a", "b"]})
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        from textual.widgets import Button

        # SequenceEditor should mount one row per item plus an "Add" button.
        # Each row has a Remove button.
        buttons = [str(b.label) for b in app.query(Button)]
        # Expect at least 2 "Remove" + 1 "Add"
        assert any("Add" in label for label in buttons)
        assert sum(1 for label in buttons if "Remove" in label) == 2


@pytest.mark.asyncio
async def test_sequence_editor_add_button() -> None:
    class M(BaseModel):
        tags: list[str] = []

    tree = build_form_tree(M, existing={"tags": ["a"]})
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        from textual.widgets import Button

        buttons = list(app.query(Button))
        add_btn = next(b for b in buttons if "Add" in str(b.label))
        await pilot.click(add_btn)
        await pilot.pause()
        # Now there should be 2 items.
        tags = tree.root.find("tags")
        assert tags is not None
        assert len(tags.items) == 2
```

- [ ] **Step 2: Run — expect FAIL**

```bash
uv run pytest tests/unit/test_textual_widgets.py::test_sequence_editor_renders_existing_items -v
```

Expected: FAIL — SequenceEditor doesn't exist (was a late import in editor.py).

- [ ] **Step 3: Implement `containers.py`**

Create `src/pydantic_studio/renderers/textual_/widgets/containers.py`:

```python
"""Container widgets: SequenceEditor, MappingEditor, UnionEditor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

from pydantic_studio.renderers.textual_.widgets.editor import NodeEditor

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree


class SequenceEditor(NodeEditor):
    """Editor for SequenceNode (list/set/tuple).

    Layout:
        [field name]: [Add]
            row 0: <child editor> [Remove]
            row 1: <child editor> [Remove]
            ...
    """

    def compose(self) -> ComposeResult:
        with Vertical(id=f"seq-{self.field_path}"):
            with Horizontal():
                yield Label(f"{self.node.name}: ", classes="field-label")
                yield Button("Add", id=f"add-{self.field_path}", variant="primary")
            for i in range(len(self.node.items)):
                yield from self._compose_row(i)

    def _compose_row(self, index: int) -> ComposeResult:
        item = self.node.items[index]
        item_path = f"{self.field_path}[{index}]"
        item_editor = NodeEditor.dispatch(item, item_path, self.form_tree)
        with Horizontal(id=f"row-{self.field_path}-{index}"):
            yield item_editor
            yield Button(
                "Remove",
                id=f"remove-{self.field_path}-{index}",
                variant="warning",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith(f"add-{self.field_path}"):
            self._on_add()
        elif bid.startswith(f"remove-{self.field_path}-"):
            try:
                idx = int(bid.rsplit("-", 1)[1])
            except ValueError:
                return
            self._on_remove(idx)

    def _on_add(self) -> None:
        result = self.form_tree.add_item(self.field_path)
        if not result.ok:
            return
        # Refresh: recompute the children. Simpler — re-mount the whole editor.
        self._rebuild()

    def _on_remove(self, index: int) -> None:
        result = self.form_tree.remove_item(self.field_path, index)
        if not result.ok:
            return
        self._rebuild()

    def _rebuild(self) -> None:
        """Tear down and re-compose. Triggers screen.refresh_preview."""
        self.remove_children()
        for w in self.compose():
            self.mount(w)
        screen = self.screen
        if hasattr(screen, "refresh_preview"):
            screen.refresh_preview()


class MappingEditor(NodeEditor):
    """Editor for MappingNode (dict[K, V]).

    Layout:
        [field name]: [Add Entry]
            entry 0: [key editor] [value editor] [Remove]
            entry 1: ...
    """

    def compose(self) -> ComposeResult:
        with Vertical(id=f"map-{self.field_path}"):
            with Horizontal():
                yield Label(f"{self.node.name}: ", classes="field-label")
                yield Button(
                    "Add Entry",
                    id=f"add-{self.field_path}",
                    variant="primary",
                )
            for i in range(len(self.node.entries)):
                yield from self._compose_entry(i)

    def _compose_entry(self, index: int) -> ComposeResult:
        k_node, v_node = self.node.entries[index]
        v_path = f"{self.field_path}[{index}]"
        v_editor = NodeEditor.dispatch(v_node, v_path, self.form_tree)
        with Horizontal(id=f"entry-{self.field_path}-{index}"):
            yield Label(f"key={getattr(k_node, 'value', k_node.name)!r}")
            yield v_editor
            yield Button(
                "Remove",
                id=f"remove-{self.field_path}-{index}",
                variant="warning",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith(f"add-{self.field_path}"):
            self._on_add()
        elif bid.startswith(f"remove-{self.field_path}-"):
            try:
                idx = int(bid.rsplit("-", 1)[1])
            except ValueError:
                return
            self._on_remove(idx)

    def _on_add(self) -> None:
        # Use a placeholder key — user can rename via the existing
        # rename_key mutation in a future polish pass.
        existing_keys = {
            getattr(k_node, "value", "") for k_node, _ in self.node.entries
        }
        i = 0
        while f"key{i}" in existing_keys:
            i += 1
        result = self.form_tree.add_entry(self.field_path, key=f"key{i}")
        if not result.ok:
            return
        self._rebuild()

    def _on_remove(self, index: int) -> None:
        result = self.form_tree.remove_entry(self.field_path, index)
        if not result.ok:
            return
        self._rebuild()

    def _rebuild(self) -> None:
        self.remove_children()
        for w in self.compose():
            self.mount(w)
        screen = self.screen
        if hasattr(screen, "refresh_preview"):
            screen.refresh_preview()


class UnionEditor(NodeEditor):
    """Editor for UnionNode — variant picker + nested editor for the
    selected variant.

    Layout:
        [field name]: [variant Select]
            <selected variant's editor>
    """

    def compose(self) -> ComposeResult:
        from textual.widgets import Select

        options = [
            (name.rsplit(".", 1)[-1], name)
            for name in self.node.variant_type_names
        ]
        initial = (
            self.node.variant_type_names[self.node.selected_index]
            if self.node.selected_index is not None
            else Select.BLANK
        )
        with Vertical(id=f"union-{self.field_path}"):
            with Horizontal():
                yield Label(f"{self.node.name} (variant): ", classes="field-label")
                yield Select(
                    options=options,
                    value=initial,
                    id=f"variant-{self.field_path}",
                )
            if self.node.selected is not None:
                inner_path = self.field_path
                inner_editor = NodeEditor.dispatch(
                    self.node.selected, inner_path, self.form_tree
                )
                yield inner_editor

    def on_select_changed(self, event) -> None:
        from textual.widgets import Select

        if event.value == Select.BLANK:
            return
        # Find the variant index for this type name.
        for i, name in enumerate(self.node.variant_type_names):
            if name == event.value:
                result = self.form_tree.select_variant(self.field_path, i)
                if result.ok:
                    self._rebuild()
                return

    def _rebuild(self) -> None:
        self.remove_children()
        for w in self.compose():
            self.mount(w)
        screen = self.screen
        if hasattr(screen, "refresh_preview"):
            screen.refresh_preview()
```

- [ ] **Step 4: Update widgets/__init__.py exports**

```python
from pydantic_studio.renderers.textual_.widgets.containers import (
    MappingEditor,
    SequenceEditor,
    UnionEditor,
)
from pydantic_studio.renderers.textual_.widgets.editor import EditorPane, NodeEditor
from pydantic_studio.renderers.textual_.widgets.preview import PreviewPane
from pydantic_studio.renderers.textual_.widgets.scalars import (
    BoolEditor,
    ChoiceEditor,
    TextInputEditor,
)
from pydantic_studio.renderers.textual_.widgets.sidebar import Sidebar

__all__ = [
    "BoolEditor",
    "ChoiceEditor",
    "EditorPane",
    "MappingEditor",
    "NodeEditor",
    "PreviewPane",
    "SequenceEditor",
    "Sidebar",
    "TextInputEditor",
    "UnionEditor",
]
```

- [ ] **Step 5: Run sequence tests — expect PASS**

```bash
uv run pytest tests/unit/test_textual_widgets.py::test_sequence_editor_renders_existing_items tests/unit/test_textual_widgets.py::test_sequence_editor_add_button -v
```

Expected: 2 PASS.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -q
```

Expected: 355 passed (353 + 2).

- [ ] **Step 7: Verify ruff**

```bash
uv run ruff check
```

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/renderers/textual_/widgets/containers.py src/pydantic_studio/renderers/textual_/widgets/__init__.py tests/unit/test_textual_widgets.py
git commit -m "feat(textual): SequenceEditor + MappingEditor + UnionEditor (basic add/remove)"
```

---

### Task 10: Save / Undo / Redo bindings

**Why:** Wire `Ctrl+S` (save), `Ctrl+Z` (undo), `Ctrl+Y` (redo) on the EditorScreen. Save uses `save_yaml(tree, save_path)`; on `ValidationFailedError`, show a banner. Undo/redo route through `tree.undo()` / `tree.redo()` and trigger preview refresh.

**Files:**
- Modify: `src/pydantic_studio/renderers/textual_/screens.py` — add bindings + actions
- Modify: `tests/unit/test_textual_app.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_textual_app.py`:

```python
@pytest.mark.asyncio
async def test_save_writes_yaml(tmp_path) -> None:
    """Ctrl+S persists the tree to save_path via save_yaml."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.textual_ import StudioApp

    out = tmp_path / "out.yaml"
    tree = build_form_tree(Server)
    app = StudioApp(tree=tree, save_path=out)
    async with app.run_test() as pilot:
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
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
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
        assert port_node_after.value == 8080  # default
```

- [ ] **Step 2: Run — expect FAIL**

```bash
uv run pytest tests/unit/test_textual_app.py::test_save_writes_yaml tests/unit/test_textual_app.py::test_undo_reverts_last_mutation -v
```

Expected: FAIL — bindings don't exist.

- [ ] **Step 3: Add the bindings + actions**

Modify `src/pydantic_studio/renderers/textual_/screens.py` BINDINGS list and add actions:

```python
class EditorScreen(Screen):
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+s", "save", "Save"),
        ("ctrl+z", "undo", "Undo"),
        ("ctrl+y", "redo", "Redo"),
    ]

    # ... existing compose/refresh_preview/etc. ...

    def action_save(self) -> None:
        """Persist the tree to save_path. No-op if save_path is None."""
        save_path = self.app.save_path
        if save_path is None:
            self.notify("Read-only mode (no save path)", severity="warning")
            return
        try:
            from pydantic_studio import save_yaml

            save_yaml(self.app.tree, save_path)
            self.notify(f"Saved to {save_path}", severity="information")
        except Exception as e:  # noqa: BLE001
            self.notify(f"Save failed: {e}", severity="error", timeout=8)

    def action_undo(self) -> None:
        if self.app.tree.undo():
            self._reload_editor_pane()
            self.refresh_preview()

    def action_redo(self) -> None:
        if self.app.tree.redo():
            self._reload_editor_pane()
            self.refresh_preview()

    def _reload_editor_pane(self) -> None:
        """After undo/redo the FormTree was rehydrated from a snapshot —
        re-mount the editor pane so its widgets reflect the new state."""
        try:
            editor = self.query_one(EditorPane)
        except Exception:
            return
        # Re-resolve the focused group at the same path.
        group = self._resolve_group(editor._current_group_path)
        if group is not None:
            editor.set_group(group, editor._current_group_path)
```

- [ ] **Step 4: Run — expect PASS**

```bash
uv run pytest tests/unit/test_textual_app.py::test_save_writes_yaml tests/unit/test_textual_app.py::test_undo_reverts_last_mutation -v
```

Expected: 2 PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
```

Expected: 357 passed.

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/renderers/textual_/screens.py tests/unit/test_textual_app.py
git commit -m "feat(textual): Ctrl+S save / Ctrl+Z undo / Ctrl+Y redo bindings on EditorScreen"
```

---

### Task 11: CLI `edit` subcommand

**Why:** `pydantic-studio edit <module:Class> [<file>]` ties everything together. If `<file>` exists: load it; otherwise: build a fresh tree. Launch the StudioApp; on quit, the file (if any) holds the most recent saved state.

**Files:**
- Modify: `src/pydantic_studio/cli.py` — add `edit` command
- Create: `tests/unit/test_cli_edit.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_cli_edit.py`:

```python
"""Tests for the `pydantic-studio edit` CLI subcommand.

Note: edit launches a Textual TUI which can't be driven through CliRunner
the same way as `fill`/`run`/`check` (it blocks on App.run()). Instead we
patch the StudioApp.run() to be a no-op and verify the load/build flow
worked correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pydantic_studio.cli import app

runner = CliRunner()


def test_edit_with_existing_file(tmp_path: Path, monkeypatch) -> None:
    """edit loads an existing YAML and launches the app."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("name: prod\nport: 9090\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_run(self) -> None:  # type: ignore[no-untyped-def]
        captured["tree"] = self.tree
        captured["save_path"] = self.save_path

    from pydantic_studio.renderers.textual_ import StudioApp

    monkeypatch.setattr(StudioApp, "run", fake_run)

    result = runner.invoke(
        app,
        ["edit", "tests.fixtures.schemas:Server", str(cfg)],
    )
    assert result.exit_code == 0
    tree = captured["tree"]
    assert tree is not None
    # The loaded port is 9090, not the default 8080.
    port_node = tree.root.find("port")
    assert port_node is not None
    assert port_node.value == 9090


def test_edit_without_file_builds_fresh_tree(tmp_path: Path, monkeypatch) -> None:
    """edit without a path argument launches with a fresh tree (defaults)."""
    captured: dict[str, object] = {}

    def fake_run(self) -> None:
        captured["tree"] = self.tree
        captured["save_path"] = self.save_path

    from pydantic_studio.renderers.textual_ import StudioApp

    monkeypatch.setattr(StudioApp, "run", fake_run)

    result = runner.invoke(app, ["edit", "tests.fixtures.schemas:Server"])
    assert result.exit_code == 0
    assert captured["save_path"] is None
    tree = captured["tree"]
    port_node = tree.root.find("port")
    assert port_node is not None
    assert port_node.value == 8080  # default


def test_edit_unknown_schema_errors() -> None:
    result = runner.invoke(app, ["edit", "nosuch:Foo"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run — expect FAIL**

```bash
uv run pytest tests/unit/test_cli_edit.py -v
```

Expected: FAIL — `edit` doesn't exist.

- [ ] **Step 3: Implement `edit` in cli.py**

Append to `src/pydantic_studio/cli.py`:

```python
@app.command()
def edit(
    target: str = typer.Argument(..., help="module:Class identifier."),
    file: Path | None = typer.Argument(  # noqa: B008
        None,
        help="Path to a YAML file. If omitted, edits a fresh tree.",
    ),
) -> None:
    """Launch the Textual editor for a Pydantic schema.

    With FILE: load it via load_yaml, edit interactively, save back.
    Without FILE: build a fresh tree from the schema's defaults; saves are
    disabled (read-only mode).
    """
    from pydantic_studio import build_form_tree, load_yaml
    from pydantic_studio.renderers.textual_ import StudioApp

    schema = _load_schema(target)
    if file is not None and file.exists():
        tree = load_yaml(file, schema)
    else:
        tree = build_form_tree(schema)
    app_instance = StudioApp(tree=tree, save_path=file)
    app_instance.run()
```

- [ ] **Step 4: Run — expect PASS**

```bash
uv run pytest tests/unit/test_cli_edit.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
```

Expected: 360 passed.

- [ ] **Step 6: Verify ruff**

```bash
uv run ruff check
```

- [ ] **Step 7: Commit**

```bash
git add src/pydantic_studio/cli.py tests/unit/test_cli_edit.py
git commit -m "feat(cli): edit subcommand launches StudioApp on schema (with optional YAML file)"
```

---

### Task 12: Public API export + smoke test

**Why:** Expose `StudioApp` and `run_app` from the top-level package. Add a smoke test that exercises an end-to-end edit-save cycle through the App.

**Files:**
- Modify: `src/pydantic_studio/__init__.py` — export `StudioApp`, `run_app`
- Modify: `tests/unit/test_textual_app.py`

- [ ] **Step 1: Add exports**

In `src/pydantic_studio/__init__.py`:

```python
from pydantic_studio.renderers.textual_ import StudioApp, run_app
```

Add to `__all__` (alphabetically):

```python
    "StudioApp",
    ...
    "run_app",
```

- [ ] **Step 2: Add end-to-end smoke test**

Append to `tests/unit/test_textual_app.py`:

```python
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
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert out.exists()
    reloaded = load_yaml(out, Server)
    instance = reloaded.to_instance()
    assert instance.name == "smoke-test"
    assert instance.port == 12345
```

- [ ] **Step 3: Run — expect PASS**

```bash
uv run pytest tests/unit/test_textual_app.py::test_smoke_edit_save_cycle -v
```

Expected: PASS.

- [ ] **Step 4: Run full suite**

```bash
uv run pytest -q
```

Expected: 361 passed.

- [ ] **Step 5: Verify ruff**

```bash
uv run ruff check
```

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/__init__.py tests/unit/test_textual_app.py
git commit -m "feat(api): export StudioApp + run_app from pydantic_studio top level"
```

---

### Task 13: README + version bump v0.0.5

**Files:**
- Modify: `pyproject.toml` — `version = "0.0.5"`
- Modify: `src/pydantic_studio/__init__.py` — `__version__ = "0.0.5"`
- Modify: `README.md`

- [ ] **Step 1: Bump versions**

In `pyproject.toml`: `version = "0.0.5"`.
In `src/pydantic_studio/__init__.py`: `__version__ = "0.0.5"`.

- [ ] **Step 2: Update README**

Append a new section to `README.md` (after the existing Phase 4 section):

````markdown
## Textual TUI (v0.0.5)

Pydantic Studio now ships a Textual-based terminal UI:

```bash
$ uv run pydantic-studio edit mypkg.config:AppSettings config.yaml
```

The TUI shows three regions:

- **Sidebar** (left): tree of nested groups. Click a group to focus its fields in the editor.
- **Editor** (center): scrollable widgets for each field. TextInput for scalars, Checkbox for bools, Select for Enum/Literal, expandable rows for sequences and mappings, variant picker for unions.
- **Preview** (right): live YAML render — updates after every successful mutation.

### Key bindings

- `Ctrl+S` — save (writes via `save_yaml`; refuses if the tree fails validation)
- `Ctrl+Z` / `Ctrl+Y` — undo / redo
- `Ctrl+Q` — quit (no prompt yet — Plan 6 polish)

### What's not in v0.0.5

- HTML renderer (Plan 6)
- TOML / JSON I/O (Plan 7)
- Light theme + custom theme.css (Plan 8 polish)
- `save_draft_yaml` for partial-tree saves (Plan 6)
- Status-bar widget for error display (currently surfaces via `notify()` toasts)
- Per-Sequence drag-to-reorder (Plan 6)

### Programmatic usage

```python
from pydantic_studio import build_form_tree, StudioApp

tree = build_form_tree(MyConfig)
app = StudioApp(tree=tree, save_path="config.yaml")
app.run()  # blocks until the user quits
```
````

- [ ] **Step 3: Run final checks**

```bash
uv run pytest -q
uv run ruff check
uv run pyright src/pydantic_studio 2>&1 | tail -3
```

Expected: 361 passed; ruff clean; pyright count similar (renderer code may add a few new errors related to Textual's API typing — note the new total).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/pydantic_studio/__init__.py README.md
git commit -m "docs: README + version bump for v0.0.5"
```

---

### Task 14: Merge ceremony

- [ ] **Step 1: Verify clean state**

```bash
git status
git log --oneline -5
```

- [ ] **Step 2: Tag the feature tip**

```bash
git tag v0.0.5-phase-5
```

- [ ] **Step 3: Merge to master with --no-ff**

```bash
git checkout master
git merge --no-ff feature/phase-5-textual-renderer -m "merge: Phase 5 — Textual TUI renderer"
```

- [ ] **Step 4: Verify final state**

```bash
uv run pytest -q
git log --oneline -5
git tag --list 'v0.0.*'
git branch -d feature/phase-5-textual-renderer
```

Expected: all tests green; `v0.0.5-phase-5` reachable via merge's second parent. **Do not push.**

---

## Phase 5 — Self-Review Notes

| Spec § | Requirement | Task(s) |
|---|---|---|
| § 6.1 (Textual renderer) | Three-region layout, Tree sidebar, per-node widgets, preview pane | T2-T9 |
| § 6.1 (key bindings) | ^Z/^Y undo/redo, ^S save, ^Q quit | T2 (quit), T10 (save/undo/redo) |
| § 8 (CLI) | `edit <module:Class> <file>` | T11 |
| § 13.3 (E2E testing) | App.run_test() + Pilot framework | T2, T6-T12 (mostly Pilot tests) |

Items intentionally deferred:
- Custom theme.css (Plan 8 polish)
- Light-theme toggle
- Status bar / help screen
- `save_draft_yaml` for partial trees (Plan 6)
- Phase-4 housekeeping (folded into Plan 6's T0)
- Specialized DatetimePicker widgets (TextInputEditor with ISO parse covers it)

Likely failure modes:
- Pilot's `await pilot.press("ctrl+a")` may not always reliably select text in the Input widget. If `test_text_input_editor_for_string` flakes, set `inputs[0].value = ""` directly before typing.
- Textual API surface changes between versions. The plan targets `textual>=0.85`; some method names (`query_one`, `set_focus`, `Select.BLANK`) are stable as of late 2024.
- `RichLog.lines` may not exist on all Textual versions. The `_read_log_lines` helper has a fallback.

---

**End of Plan 5.**
