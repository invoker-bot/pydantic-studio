# TUI Redesign M1: Chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the visual chrome (theme, breadcrumb, footer-hints bar, field-row shell, field-list view, config-screen shell, feature-flag dispatch) for the TUI v2 redesign per `docs/superpowers/specs/2026-05-15-tui-config-aesthetic-redesign-design.md` §4–§6. No editing cells yet (M2). No drill-down (M3). The legacy `EditorScreen` stays the default; v2 is opt-in via `PYDANTIC_STUDIO_TUI_V2=1`.

**Architecture:** Five new widgets (`Breadcrumb`, `FooterHints`, `FieldRow`, `FieldListView`, plus a temporary `PlaceholderCell` so the row chrome can render in isolation) and one new screen (`ConfigScreen`) land in `renderers/textual_/`. A new `theme.tcss` file defines a warm-amber accent on near-black palette. The existing `StudioApp` gets a feature-flag dispatch so M1 ships under an opt-in without breaking any current user.

**Tech Stack:** Textual 8.x (existing), Pydantic v2, pytest + pytest-asyncio with Textual's Pilot harness.

---

## Scope and constraints

- All work happens on the existing feature branch `feat/tui-config-aesthetic-redesign` (already created and currently checked out; the spec was committed there as `1907f90`).
- Per the spec §11, M1 ships under `PYDANTIC_STUDIO_TUI_V2=1`. Users without that env var see the unchanged legacy TUI.
- TDD throughout: write the failing test, run, implement, run, commit. One TDD cycle per task.
- Per CLAUDE.md: ASCII-only commit messages, `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer, never push without explicit user OK.
- Renderer files are excluded from pyright (`[tool.pyright] exclude = ["src/pydantic_studio/renderers/textual_/**", ...]`), so pyright noise on new files is expected. Use `# noqa` only when truly needed; otherwise let the exclude carry it.
- New widgets live in `src/pydantic_studio/renderers/textual_/widgets/` next to the existing `scalars.py` / `containers.py`. The widgets v2 reads as flat modules (no `widgets/v2/` subdir) — the cells subdirectory lands in M2.

---

## File Structure

**Files to create:**

| Path | Responsibility |
|---|---|
| `src/pydantic_studio/renderers/textual_/theme.tcss` | Custom CSS palette: $surface, $text, $accent, $error + per-widget rules for FieldRow, Breadcrumb, FooterHints. |
| `src/pydantic_studio/renderers/textual_/widgets/breadcrumb.py` | `Breadcrumb(Static)` widget. Reads `parts: list[str]`, renders `"a › b › c"` with middle ellipsis at depth ≥ 4. |
| `src/pydantic_studio/renderers/textual_/widgets/footer_hints.py` | `FooterHints(Static)` widget. Reads `mode: Literal["idle","editing","sequence","mapping","errors"]`, renders the matching 2-line keybind hint. |
| `src/pydantic_studio/renderers/textual_/widgets/field_row.py` | `FieldRow(Widget)` shell. Reads `node`, `path`, `focused`. Composes focus-marker + label + leader + placeholder value + drill-marker. Also defines `PlaceholderCell` (single-line `Static` rendering `str(node.value)`) so M1 has something to dispatch to before M2 ships real cells. |
| `src/pydantic_studio/renderers/textual_/widgets/field_list.py` | `FieldListView(Vertical)` widget. Reads `group: GroupNode`, `path: str`. Composes one `FieldRow` per child. Owns the `cursor: int` reactive and handles `up`/`down` keys to move focus. |
| `tests/unit/test_tui_v2_theme.py` | Smoke for theme.tcss file existence + variable declarations. |
| `tests/unit/test_tui_v2_breadcrumb.py` | Unit tests for Breadcrumb (rendering + truncation). |
| `tests/unit/test_tui_v2_footer_hints.py` | Unit tests for FooterHints (mode-dependent rendering). |
| `tests/unit/test_tui_v2_field_row.py` | Unit tests for FieldRow (focus state, error helper, drill marker, placeholder cell). |
| `tests/unit/test_tui_v2_field_list.py` | Unit tests for FieldListView (mounts N rows, up/down moves cursor, scroll-on-overflow). |
| `tests/unit/test_tui_v2_config_screen.py` | Unit tests for ConfigScreen (composes 3 regions, loads theme). |
| `tests/unit/test_tui_v2_dispatch.py` | Unit tests for StudioApp env-var dispatch (default → EditorScreen, flag set → ConfigScreen). |

**Files to modify:**

| Path | Change |
|---|---|
| `src/pydantic_studio/renderers/textual_/screens.py` | Add `ConfigScreen(GroupNode, path)` class alongside the existing `EditorScreen`. Composes `Breadcrumb`, `FieldListView`, `FooterHints`. Loads `theme.tcss`. |
| `src/pydantic_studio/renderers/textual_/app.py` | Add feature-flag dispatch in `on_mount`: if `os.environ.get("PYDANTIC_STUDIO_TUI_V2") == "1"`, push `ConfigScreen` instead of `EditorScreen`. |

**Files NOT touched in M1:**

- `widgets/scalars.py`, `widgets/containers.py`, `widgets/editor.py`, `widgets/sidebar.py` — legacy, kept until M6.
- `tests/unit/test_textual_widgets.py`, `test_textual_app.py` — legacy tests, kept until M6.

---

## Test infrastructure

All new widgets are tested via a tiny host app:

```python
import pytest
from textual.app import App

class _HostApp(App):
    """Mounts a single widget for Pilot-driven testing."""
    def __init__(self, widget):
        super().__init__()
        self._widget = widget
    def compose(self):
        yield self._widget
```

That host is duplicated inline in each test file (~7 lines). Don't extract to a fixture — the duplication is minimal and keeping tests self-contained avoids cross-file coupling on a fixture that might evolve.

Run all unit tests with:
```
./.venv/Scripts/python.exe -m pytest tests/unit -p no:playwright -q
```

(Note: `python -m pytest`, not `pytest` directly. `uv run pytest` fails on Windows with "trampoline failed to canonicalize" per the session journal.)

---

## Task 1: Theme palette (theme.tcss)

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/theme.tcss`
- Test: `tests/unit/test_tui_v2_theme.py` (smoke that the CSS file exists and declares required variables)

The theme defines six color variables and per-widget rules. Lives at the renderer root (not under `widgets/`) so screens can reference it as a sibling.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_tui_v2_theme.py`:

```python
"""Smoke test for theme.tcss: file must exist and declare the
variables the M1 widgets depend on. Renderable styling is verified
indirectly by the widget tests that mount under a theme-loading
ConfigScreen.
"""

from __future__ import annotations

from pathlib import Path


def test_theme_tcss_file_exists() -> None:
    here = Path(__file__).parent.parent.parent / "src" / "pydantic_studio"
    theme = here / "renderers" / "textual_" / "theme.tcss"
    assert theme.exists(), f"missing theme.tcss at {theme}"
    body = theme.read_text(encoding="utf-8")
    for var in ("$surface", "$text", "$text-muted", "$accent", "$error"):
        assert var in body, f"theme.tcss missing variable {var}"
```

- [ ] **Step 2: Run test to verify it fails**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_theme.py -v
```

Expected: FAIL with `AssertionError: missing theme.tcss at ...`

- [ ] **Step 3: Create theme.tcss**

Write `src/pydantic_studio/renderers/textual_/theme.tcss`:

```css
/* TUI v2 palette — warm muted, matching Claude Code /config aesthetic.
   See docs/superpowers/specs/2026-05-15-tui-config-aesthetic-redesign-design.md §6. */

$surface: #0f0f10;
$surface-lighten-1: #1a1a1c;
$text: #e8e6e3;
$text-muted: #6e6e6e;
$accent: #d18b40;
$error: #cc6666;

Screen {
    background: $surface;
    color: $text;
}

Breadcrumb {
    height: 1;
    background: $surface;
    color: $text-muted;
    padding: 0 1;
}

Breadcrumb .breadcrumb--current {
    color: $accent;
    text-style: bold;
}

FooterHints {
    height: 2;
    background: $surface;
    color: $text-muted;
    padding: 0 1;
    border-top: hkey $text-muted;
}

FooterHints .footer-hints--key {
    color: $accent;
}

FieldListView {
    height: 1fr;
    padding: 0 1;
    background: $surface;
}

FieldRow {
    height: auto;
    padding: 0 1;
    color: $text;
}

FieldRow.-focused {
    background: $surface-lighten-1;
}

FieldRow .field-row--marker {
    width: 2;
    color: $text-muted;
}

FieldRow.-focused .field-row--marker {
    color: $accent;
    text-style: bold;
}

FieldRow .field-row--label {
    width: 22;
    color: $text;
}

FieldRow .field-row--leader {
    color: $text-muted;
}

FieldRow .field-row--value {
    color: $text;
}

FieldRow .field-row--drill {
    width: 3;
    color: $text-muted;
    content-align: right top;
}

FieldRow .field-row--helper {
    color: $error;
    padding-left: 24;
}
```

- [ ] **Step 4: Run test to verify it passes**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_theme.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/renderers/textual_/theme.tcss tests/unit/test_tui_v2_theme.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): theme.tcss palette (M1 T1)

Warm-muted palette matching Claude Code /config: near-black surface,
warm off-white text, warm-amber accent (#d18b40) for selection +
primary actions, muted red for errors. Defines per-widget rules for
Breadcrumb / FooterHints / FieldListView / FieldRow that the M1
widget tasks below consume.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Breadcrumb widget

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/breadcrumb.py`
- Test: `tests/unit/test_tui_v2_breadcrumb.py`

`Breadcrumb` is a single-line `Static` displaying the schema path. At depth 1–3 it renders all parts joined with `" › "`. At depth ≥ 4 it renders `"<first> › … › <last>"` (middle ellipsis) so the title bar never overflows the modal width.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_breadcrumb.py`:

```python
"""Unit tests for the TUI v2 Breadcrumb widget."""

from __future__ import annotations

import pytest
from textual.app import App

from pydantic_studio.renderers.textual_.widgets.breadcrumb import Breadcrumb


class _Host(App):
    def __init__(self, parts: list[str]) -> None:
        super().__init__()
        self._parts = parts

    def compose(self):
        yield Breadcrumb(parts=self._parts)


@pytest.mark.asyncio
async def test_breadcrumb_renders_single_part() -> None:
    app = _Host(["AppSettings"])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == "AppSettings"


@pytest.mark.asyncio
async def test_breadcrumb_joins_parts_with_chevron() -> None:
    app = _Host(["AppSettings", "database"])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == "AppSettings › database"


@pytest.mark.asyncio
async def test_breadcrumb_full_depth_three_no_truncation() -> None:
    app = _Host(["a", "b", "c"])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == "a › b › c"


@pytest.mark.asyncio
async def test_breadcrumb_truncates_middle_at_depth_four() -> None:
    app = _Host(["a", "b", "c", "d"])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        # Middle parts (b, c) collapse to ellipsis; first and last preserved.
        assert bc.label_text == "a › … › d"


@pytest.mark.asyncio
async def test_breadcrumb_truncates_middle_at_depth_five() -> None:
    app = _Host(["a", "b", "c", "d", "e"])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == "a › … › e"


@pytest.mark.asyncio
async def test_breadcrumb_empty_parts_renders_blank() -> None:
    app = _Host([])
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_breadcrumb.py -v
```

Expected: 6 FAILs with `ModuleNotFoundError: No module named 'pydantic_studio.renderers.textual_.widgets.breadcrumb'`

- [ ] **Step 3: Implement Breadcrumb**

Create `src/pydantic_studio/renderers/textual_/widgets/breadcrumb.py`:

```python
"""Breadcrumb widget for the TUI v2 ConfigScreen title bar.

Renders the navigation path as ``"a > b > c"`` (joined with U+203A
SINGLE RIGHT-POINTING ANGLE QUOTATION MARK). Past depth 3, the
middle parts collapse to ellipsis so the title bar stays within
modal width.
"""

from __future__ import annotations

from textual.widgets import Static

_SEP = " › "          # ' > ' with thin spaces
_ELLIPSIS = "…"       # ' ... '


class Breadcrumb(Static):
    """Single-line breadcrumb. Read ``label_text`` to inspect the rendered string."""

    DEFAULT_CSS = ""  # styling comes from theme.tcss

    def __init__(self, parts: list[str]) -> None:
        self._parts = list(parts)
        super().__init__(self._compute_label())

    @property
    def label_text(self) -> str:
        """The plain text of the breadcrumb (no markup)."""
        return self._compute_label()

    def _compute_label(self) -> str:
        if not self._parts:
            return ""
        if len(self._parts) <= 3:
            return _SEP.join(self._parts)
        # 4+ parts: keep first + last, collapse middle to ellipsis.
        return f"{self._parts[0]}{_SEP}{_ELLIPSIS}{_SEP}{self._parts[-1]}"
```

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_breadcrumb.py -v
```

Expected: 6 PASS

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/breadcrumb.py tests/unit/test_tui_v2_breadcrumb.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): Breadcrumb widget (M1 T2)

Single-line widget for the ConfigScreen title bar. Joins parts with
U+203A (single right-pointing angle quotation mark). Past depth 3,
middle parts collapse to U+2026 ellipsis so the title bar stays
within the modal width. 6 unit tests cover: single part, joined
parts, depth-3 (no truncation), depth-4 and depth-5 (truncation),
empty parts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: FooterHints widget

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/footer_hints.py`
- Test: `tests/unit/test_tui_v2_footer_hints.py`

`FooterHints` is a 2-line `Static` showing context-sensitive keybind hints. Mode is one of `"idle" | "editing" | "sequence" | "mapping" | "errors"`. Line 2 is always `Ctrl+S save · Ctrl+Q quit`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_footer_hints.py`:

```python
"""Unit tests for the TUI v2 FooterHints widget."""

from __future__ import annotations

import pytest
from textual.app import App

from pydantic_studio.renderers.textual_.widgets.footer_hints import FooterHints


class _Host(App):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self._mode = mode

    def compose(self):
        yield FooterHints(mode=self._mode)


@pytest.mark.asyncio
async def test_footer_idle_mode_shows_navigation() -> None:
    app = _Host("idle")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "navigate" in fh.line1
        assert "Enter" in fh.line1
        assert "Esc" in fh.line1
        assert "Ctrl+S" in fh.line2
        assert "Ctrl+Q" in fh.line2


@pytest.mark.asyncio
async def test_footer_editing_mode_shows_edit_keys() -> None:
    app = _Host("editing")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "Enter" in fh.line1
        assert "commit" in fh.line1
        assert "cancel" in fh.line1
        # save/quit always on line 2
        assert "Ctrl+S" in fh.line2


@pytest.mark.asyncio
async def test_footer_sequence_mode_shows_delete() -> None:
    app = _Host("sequence")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "D" in fh.line1
        assert "delete" in fh.line1


@pytest.mark.asyncio
async def test_footer_mapping_mode_shows_rename() -> None:
    app = _Host("mapping")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "R" in fh.line1
        assert "rename" in fh.line1
        assert "D" in fh.line1


@pytest.mark.asyncio
async def test_footer_errors_mode_shows_jump() -> None:
    app = _Host("errors")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "Esc" in fh.line1
        assert "Enter" in fh.line1


@pytest.mark.asyncio
async def test_footer_unknown_mode_falls_back_to_idle() -> None:
    app = _Host("nonexistent-mode")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        # Idle text on unknown modes — safe default, never crash.
        assert "navigate" in fh.line1
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_footer_hints.py -v
```

Expected: 6 FAILs with `ModuleNotFoundError`.

- [ ] **Step 3: Implement FooterHints**

Create `src/pydantic_studio/renderers/textual_/widgets/footer_hints.py`:

```python
"""FooterHints widget — context-sensitive 2-line keybind bar at the bottom
of the ConfigScreen. Line 1 changes with the active mode; line 2 is the
always-visible save/quit reminder.
"""

from __future__ import annotations

from typing import Literal

from textual.widgets import Static

Mode = Literal["idle", "editing", "sequence", "mapping", "errors"]

_LINE1: dict[str, str] = {
    "idle": "↑↓ navigate · Enter edit · Tab cycle · Esc back",
    "editing": "Type to edit · Enter commit · Esc cancel",
    "sequence": "↑↓ navigate · Enter edit · D delete · Esc back",
    "mapping": "↑↓ navigate · Enter edit · R rename · D delete · Esc back",
    "errors": "Esc back to edit · Enter jump to first error",
}
_LINE2 = "Ctrl+S save · Ctrl+Q quit"


class FooterHints(Static):
    """2-line keybind bar. Read ``line1`` / ``line2`` for the raw strings."""

    DEFAULT_CSS = ""  # styled via theme.tcss

    def __init__(self, mode: str = "idle") -> None:
        self._mode = mode
        super().__init__(self._render())

    @property
    def line1(self) -> str:
        return _LINE1.get(self._mode, _LINE1["idle"])

    @property
    def line2(self) -> str:
        return _LINE2

    def set_mode(self, mode: str) -> None:
        """Swap the active mode and re-render. Used by ConfigScreen when
        focus enters an editing cell."""
        self._mode = mode
        self.update(self._render())

    def _render(self) -> str:
        return f"{self.line1}\n{self.line2}"
```

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_footer_hints.py -v
```

Expected: 6 PASS

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/footer_hints.py tests/unit/test_tui_v2_footer_hints.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): FooterHints widget (M1 T3)

2-line keybind bar at the bottom of ConfigScreen. Line 1 is
mode-dependent (idle / editing / sequence / mapping / errors).
Line 2 is the always-visible Ctrl+S save / Ctrl+Q quit. Unknown
mode falls back to idle so a misspelled mode label can't blank
the bar. 6 unit tests cover each mode + the fallback.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: FieldRow shell + PlaceholderCell

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/field_row.py`
- Test: `tests/unit/test_tui_v2_field_row.py`

`FieldRow` is the per-field row in `FieldListView`. M1 ships the chrome (focus marker, label, leader, value cell, drill marker, optional error helper). Real cells land in M2; for M1 the row dispatches to a `PlaceholderCell` (one-line `Static` showing `str(node.value)`). M1 also pre-renders the drill marker for container kinds so the layout shape locks in early.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_field_row.py`:

```python
"""Unit tests for FieldRow shell + PlaceholderCell."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.field_row import (
    FieldRow,
    PlaceholderCell,
)


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 5
    tags: list[str] = []


def _node(field_name: str):
    tree = build_form_tree(_Schema)
    n = tree.root.find(field_name)
    assert n is not None
    return n


class _Host(App):
    def __init__(self, row: FieldRow) -> None:
        super().__init__()
        self._row = row

    def compose(self):
        yield self._row


@pytest.mark.asyncio
async def test_field_row_renders_label_and_value() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        # Label and value are accessible via row API for tests.
        assert row.label_text == "name"
        # PlaceholderCell renders str(node.value); name was seeded "alpha".
        assert row.value_text == "alpha"


@pytest.mark.asyncio
async def test_field_row_focused_shows_marker() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=True)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.marker_text == "▸"  # filled right-pointing triangle


@pytest.mark.asyncio
async def test_field_row_unfocused_marker_is_blank() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.marker_text == " "


@pytest.mark.asyncio
async def test_field_row_container_kind_renders_drill_marker() -> None:
    # tags is a SequenceNode -> drillable -> drill marker visible.
    row = FieldRow(node=_node("tags"), path="tags", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.drill_marker_text == ">"


@pytest.mark.asyncio
async def test_field_row_leaf_kind_hides_drill_marker() -> None:
    # name is a StringNode -> not drillable -> blank drill marker.
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.drill_marker_text == ""


@pytest.mark.asyncio
async def test_field_row_error_helper_hidden_by_default() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert row.helper_text == ""


@pytest.mark.asyncio
async def test_field_row_set_error_shows_helper() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        row.set_error("pattern requires ^[a-z]+$")
        await pilot.pause()
        assert row.helper_text == "[!] pattern requires ^[a-z]+$"


@pytest.mark.asyncio
async def test_field_row_clear_error_hides_helper() -> None:
    row = FieldRow(node=_node("name"), path="name", focused=False)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        row.set_error("oops")
        await pilot.pause()
        row.set_error(None)
        await pilot.pause()
        assert row.helper_text == ""


@pytest.mark.asyncio
async def test_placeholder_cell_renders_str_value() -> None:
    cell = PlaceholderCell(node=_node("count"))
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # count is seeded 5 -> stringified.
        assert cell.value_text == "5"


@pytest.mark.asyncio
async def test_placeholder_cell_renders_empty_when_value_none() -> None:
    # Build a tree without seeding -> value is None.
    tree = build_form_tree(_Schema)
    # Don't set anything; default-seeding was removed in Phase 6
    # housekeeping, so freshly built nodes have value=None.
    node = tree.root.find("name")
    assert node is not None
    cell = PlaceholderCell(node=node)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # None renders as the empty string, not "None".
        assert cell.value_text == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_field_row.py -v
```

Expected: 10 FAILs with `ModuleNotFoundError`.

- [ ] **Step 3: Implement field_row.py**

Create `src/pydantic_studio/renderers/textual_/widgets/field_row.py`:

```python
"""FieldRow shell + PlaceholderCell for the TUI v2 chrome.

M1 ships the row chrome (focus marker, label, dotted leader, value
cell slot, drill marker, optional error helper). The value cell is a
PlaceholderCell that just stringifies node.value; M2 replaces it with
per-kind editor cells (TextCell / BoolCell / ChoiceCell / SecretCell).
The drill-marker logic for container kinds is wired here so the layout
is final, even though Enter-to-drill doesn't fire until M3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import AnyNode


_FOCUS_MARKER = "▸"        # filled right-pointing small triangle
_LEADER = " " + ("· " * 5)  # ' . . . . . ' middle-dot leader

_DRILLABLE_KINDS = {"group", "sequence", "mapping", "union"}


class PlaceholderCell(Widget):
    """Minimal value cell for M1: stringifies node.value (or empty for None).

    Replaced by real cells in M2. Kept as a separate widget so M2's
    cell tests can be authored independently.
    """

    DEFAULT_CSS = ""

    def __init__(self, node: AnyNode) -> None:
        super().__init__()
        self._node = node

    @property
    def value_text(self) -> str:
        v = getattr(self._node, "value", None)
        return "" if v is None else str(v)

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value")


class FieldRow(Widget):
    """One row in the FieldListView. Composes marker + label + leader +
    value cell + drill marker, plus an optional error helper line below.
    """

    DEFAULT_CSS = ""

    def __init__(
        self,
        node: AnyNode,
        path: str,
        focused: bool = False,
    ) -> None:
        super().__init__()
        self._node = node
        self._path = path
        self._focused = focused
        self._error: str | None = None
        if focused:
            self.add_class("-focused")

    @property
    def node(self) -> AnyNode:
        return self._node

    @property
    def path(self) -> str:
        return self._path

    @property
    def label_text(self) -> str:
        return self._node.name

    @property
    def marker_text(self) -> str:
        return _FOCUS_MARKER if self._focused else " "

    @property
    def value_text(self) -> str:
        # Proxy through the inner PlaceholderCell so tests can hit it
        # without having to query the child widget tree.
        return PlaceholderCell(self._node).value_text

    @property
    def drill_marker_text(self) -> str:
        return ">" if self._node.kind in _DRILLABLE_KINDS else ""

    @property
    def helper_text(self) -> str:
        return "" if self._error is None else f"[!] {self._error}"

    def set_focused(self, focused: bool) -> None:
        self._focused = focused
        if focused:
            self.add_class("-focused")
        else:
            self.remove_class("-focused")
        self._refresh_marker()

    def set_error(self, message: str | None) -> None:
        self._error = message
        if message is None:
            self.remove_class("-error")
        else:
            self.add_class("-error")
        self._refresh_helper()

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal():
                yield Static(self.marker_text, classes="field-row--marker")
                yield Static(self.label_text, classes="field-row--label")
                yield Static(_LEADER, classes="field-row--leader")
                yield PlaceholderCell(self._node)
                yield Static(self.drill_marker_text, classes="field-row--drill")
            yield Static(self.helper_text, classes="field-row--helper")

    def _refresh_marker(self) -> None:
        # Query the marker Static and rewrite it. Cheap, avoids a full
        # recompose which would churn the value cell.
        try:
            marker = self.query_one(".field-row--marker", Static)
        except Exception:
            return
        marker.update(self.marker_text)

    def _refresh_helper(self) -> None:
        try:
            helper = self.query_one(".field-row--helper", Static)
        except Exception:
            return
        helper.update(self.helper_text)
```

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_field_row.py -v
```

Expected: 10 PASS

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/field_row.py tests/unit/test_tui_v2_field_row.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): FieldRow shell + PlaceholderCell (M1 T4)

Per-field row chrome: focus marker (U+25B8), 22-col label, middle-dot
leader, value cell (PlaceholderCell -> str(node.value) for M1), and
drill marker (>) for container kinds. Optional error helper line
below the row with "[!] message" prefix. set_focused / set_error
expose imperative API so FieldListView can drive focus without
re-mounting. 10 unit tests cover render, focus toggle, drill-marker
visibility for container vs leaf kinds, error helper show/hide, and
PlaceholderCell stringification (including None -> empty).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: FieldListView

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/field_list.py`
- Test: `tests/unit/test_tui_v2_field_list.py`

`FieldListView` mounts one `FieldRow` per child of the group, manages the cursor (focused index), and translates `up` / `down` key events into cursor moves. Scrolling is delegated to Textual's `VerticalScroll` container; we don't manage scroll position by hand.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_field_list.py`:

```python
"""Unit tests for FieldListView — row mount, cursor nav, scroll."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 1
    enabled: bool = False


class _Big(BaseModel):
    """30 fields to exercise scroll behavior."""
    f00: str = ""
    f01: str = ""
    f02: str = ""
    f03: str = ""
    f04: str = ""
    f05: str = ""
    f06: str = ""
    f07: str = ""
    f08: str = ""
    f09: str = ""
    f10: str = ""
    f11: str = ""
    f12: str = ""
    f13: str = ""
    f14: str = ""
    f15: str = ""
    f16: str = ""
    f17: str = ""
    f18: str = ""
    f19: str = ""
    f20: str = ""
    f21: str = ""
    f22: str = ""
    f23: str = ""
    f24: str = ""
    f25: str = ""
    f26: str = ""
    f27: str = ""
    f28: str = ""
    f29: str = ""


class _Host(App):
    def __init__(self, view: FieldListView) -> None:
        super().__init__()
        self._view = view

    def compose(self):
        yield self._view


@pytest.mark.asyncio
async def test_field_list_mounts_one_row_per_child() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        rows = list(view.query(FieldRow))
        assert len(rows) == 3
        names = [r.label_text for r in rows]
        assert names == ["name", "count", "enabled"]


@pytest.mark.asyncio
async def test_field_list_initial_cursor_is_zero() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        assert view.cursor == 0
        rows = list(view.query(FieldRow))
        assert rows[0].marker_text == "▸"
        assert rows[1].marker_text == " "


@pytest.mark.asyncio
async def test_field_list_down_advances_cursor() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert view.cursor == 1
        rows = list(view.query(FieldRow))
        assert rows[0].marker_text == " "
        assert rows[1].marker_text == "▸"


@pytest.mark.asyncio
async def test_field_list_up_at_top_clamps_to_zero() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        assert view.cursor == 0


@pytest.mark.asyncio
async def test_field_list_down_at_bottom_clamps() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("down")
        await pilot.press("down")  # one past the end
        await pilot.press("down")  # extra
        await pilot.pause()
        assert view.cursor == 2  # last index for 3 rows


@pytest.mark.asyncio
async def test_field_list_empty_group_mounts_zero_rows() -> None:
    class _Empty(BaseModel):
        pass

    tree = build_form_tree(_Empty)
    view = FieldListView(group=tree.root, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        assert list(view.query(FieldRow)) == []
        # Cursor stays at 0 (no clamp underflow).
        assert view.cursor == 0


@pytest.mark.asyncio
async def test_field_list_focused_row_path_is_dotted() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, base_path="root")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        rows = list(view.query(FieldRow))
        # Each row's path is `<base>.<name>`; base="root" -> "root.name".
        assert rows[0].path == "root.name"
        assert rows[1].path == "root.count"
        # At base_path="" the dot is omitted -> just the name (Task 6 covers).


@pytest.mark.asyncio
async def test_field_list_blank_base_path_uses_name_only() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        rows = list(view.query(FieldRow))
        assert rows[0].path == "name"


@pytest.mark.asyncio
async def test_field_list_thirty_rows_mount_without_crash() -> None:
    """Smoke: scroll container handles 30 rows. Detail visual check is manual."""
    tree = build_form_tree(_Big)
    view = FieldListView(group=tree.root, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        rows = list(view.query(FieldRow))
        assert len(rows) == 30
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_field_list.py -v
```

Expected: 9 FAILs.

- [ ] **Step 3: Implement field_list.py**

Create `src/pydantic_studio/renderers/textual_/widgets/field_list.py`:

```python
"""FieldListView — the scrollable vertical stack of FieldRows that
sits between the Breadcrumb and FooterHints inside a ConfigScreen.

Owns the focused-row cursor and translates up/down key events into
cursor moves. Scroll is delegated to Textual's VerticalScroll
container; we never set scroll_y manually.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll

from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow

if TYPE_CHECKING:
    from typing import ClassVar

    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import GroupNode


class FieldListView(VerticalScroll):
    """Scrollable vertical stack of FieldRows for a GroupNode."""

    DEFAULT_CSS = ""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor_up", "up", show=False),
        Binding("down", "cursor_down", "down", show=False),
    ]

    def __init__(self, group: GroupNode, base_path: str = "") -> None:
        super().__init__()
        self._group = group
        self._base_path = base_path
        self._cursor: int = 0

    @property
    def cursor(self) -> int:
        return self._cursor

    def compose(self) -> ComposeResult:
        for idx, child in enumerate(self._group.fields):
            path = (
                f"{self._base_path}.{child.name}" if self._base_path else child.name
            )
            yield FieldRow(node=child, path=path, focused=(idx == 0))

    def action_cursor_up(self) -> None:
        if self._cursor <= 0:
            return
        self._move_cursor(self._cursor - 1)

    def action_cursor_down(self) -> None:
        if self._cursor >= len(self._group.fields) - 1:
            return
        self._move_cursor(self._cursor + 1)

    def _move_cursor(self, new_idx: int) -> None:
        rows = list(self.query(FieldRow))
        if not rows:
            return
        rows[self._cursor].set_focused(False)
        self._cursor = new_idx
        rows[new_idx].set_focused(True)
        # Let VerticalScroll bring the newly focused row into view.
        rows[new_idx].scroll_visible()
```

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_field_list.py -v
```

Expected: 9 PASS

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/field_list.py tests/unit/test_tui_v2_field_list.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): FieldListView with cursor navigation (M1 T5)

Scrollable vertical stack of FieldRows that owns the focused-row
cursor. up/down keys move the cursor with clamping at both ends.
Empty groups mount zero rows without underflow. Child paths are
built as "<base>.<name>" or just "<name>" when base is blank.
Subclasses VerticalScroll so Textual handles scroll-into-view via
scroll_visible() when the focused row goes off screen. 9 unit
tests cover row mount, cursor init/move/clamp, empty groups, path
construction, and 30-row scroll smoke.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: ConfigScreen + theme wiring

**Files:**
- Modify: `src/pydantic_studio/renderers/textual_/screens.py` (append `ConfigScreen` class — leave `EditorScreen` untouched)
- Test: `tests/unit/test_tui_v2_config_screen.py` (new file)

`ConfigScreen` composes `Breadcrumb` + `FieldListView` + `FooterHints` and loads `theme.tcss` via `CSS_PATH`. It's the screen that v2 mounts in place of `EditorScreen`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_config_screen.py`:

```python
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
    screen = ConfigScreen(group=tree.root, breadcrumb_parts=["AppSettings"])
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.query_one(Breadcrumb) is not None
        assert app.screen.query_one(FieldListView) is not None
        assert app.screen.query_one(FooterHints) is not None


@pytest.mark.asyncio
async def test_config_screen_breadcrumb_shows_provided_parts() -> None:
    tree = build_form_tree(_Schema)
    screen = ConfigScreen(group=tree.root, breadcrumb_parts=["a", "b"])
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        bc = app.screen.query_one(Breadcrumb)
        assert bc.label_text == "a › b"


@pytest.mark.asyncio
async def test_config_screen_footer_starts_in_idle_mode() -> None:
    tree = build_form_tree(_Schema)
    screen = ConfigScreen(group=tree.root, breadcrumb_parts=["AppSettings"])
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "navigate" in fh.line1


@pytest.mark.asyncio
async def test_config_screen_field_list_carries_group() -> None:
    tree = build_form_tree(_Schema)
    screen = ConfigScreen(group=tree.root, breadcrumb_parts=["AppSettings"])
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        rows = list(app.screen.query(FieldRow))
        assert [r.label_text for r in rows] == ["name", "count"]


@pytest.mark.asyncio
async def test_config_screen_loads_theme_tcss() -> None:
    tree = build_form_tree(_Schema)
    screen = ConfigScreen(group=tree.root, breadcrumb_parts=["AppSettings"])
    # CSS_PATH should point at theme.tcss (one of the values may be a list).
    css = screen.CSS_PATH
    paths = css if isinstance(css, list) else [css]
    assert any(str(p).endswith("theme.tcss") for p in paths)
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_config_screen.py -v
```

Expected: 5 FAILs with `ImportError: cannot import name 'ConfigScreen' from 'pydantic_studio.renderers.textual_.screens'`.

- [ ] **Step 3: Add ConfigScreen to screens.py**

Open `src/pydantic_studio/renderers/textual_/screens.py`. Append (do NOT modify or delete `EditorScreen`):

```python
class ConfigScreen(Screen):
    """TUI v2 single-panel screen: Breadcrumb + FieldListView + FooterHints.

    M1 ships the chrome with PlaceholderCell value rendering. Editing
    cells, container drill-down, sequence/mapping management, union
    cycling, and the errors screen land in M2-M5. Opt in via env var
    PYDANTIC_STUDIO_TUI_V2=1; otherwise StudioApp pushes EditorScreen
    as before.
    """

    CSS_PATH = "theme.tcss"

    def __init__(
        self,
        group: GroupNode,
        breadcrumb_parts: list[str],
    ) -> None:
        super().__init__()
        self._group = group
        self._breadcrumb_parts = breadcrumb_parts

    def compose(self) -> ComposeResult:
        yield Breadcrumb(parts=self._breadcrumb_parts)
        yield FieldListView(group=self._group, base_path="")
        yield FooterHints(mode="idle")
```

Also add the imports near the top of `screens.py`:

```python
from pydantic_studio.renderers.textual_.widgets.breadcrumb import Breadcrumb
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.footer_hints import FooterHints
```

And, inside the `TYPE_CHECKING:` block if it isn't already there:

```python
from pydantic_studio.tree.nodes import GroupNode
```

(`Screen` and `ComposeResult` should already be importable in screens.py from the existing EditorScreen.)

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_config_screen.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Run the full unit suite to verify EditorScreen still works**

```
./.venv/Scripts/python.exe -m pytest tests/unit -p no:playwright -q
```

Expected: all green (≥ 536 from the prior state, plus the new chrome tests).

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/renderers/textual_/screens.py tests/unit/test_tui_v2_config_screen.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): ConfigScreen composing Breadcrumb + list + footer (M1 T6)

ConfigScreen subclasses Screen, loads theme.tcss via CSS_PATH, and
composes Breadcrumb (title bar) + FieldListView (scrollable field
list) + FooterHints (2-line keybind bar). Coexists with the legacy
EditorScreen; nothing in the existing app wiring changes yet
(feature-flag dispatch lands in T7). 5 unit tests cover composition,
breadcrumb wiring, footer idle mode, list group passthrough, and
CSS_PATH targeting theme.tcss.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Feature-flag dispatch in StudioApp

**Files:**
- Modify: `src/pydantic_studio/renderers/textual_/app.py` (extend `on_mount` to dispatch on env var)
- Test: `tests/unit/test_tui_v2_dispatch.py` (new file)

When `PYDANTIC_STUDIO_TUI_V2=1` is set in the env, `StudioApp.on_mount` pushes the new `ConfigScreen` instead of the legacy `EditorScreen`. Otherwise behavior is unchanged. The env var lookup happens once at mount; toggling at runtime doesn't change the active screen.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_dispatch.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_dispatch.py -v
```

Expected: `test_studio_app_default_pushes_editor_screen` PASSES (no code change yet — the legacy default still applies). `test_studio_app_v2_flag_pushes_config_screen` FAILS with `AssertionError` (the env var sets but dispatch isn't wired).

- [ ] **Step 3: Wire the env-var dispatch**

Open `src/pydantic_studio/renderers/textual_/app.py`. Find the existing `on_mount` method (it currently pushes `EditorScreen`). Modify it to:

```python
def on_mount(self) -> None:
    import os

    if os.environ.get("PYDANTIC_STUDIO_TUI_V2") == "1":
        # M1+ chrome path; cells / drill / save land in M2-M5.
        from pydantic_studio.renderers.textual_.screens import ConfigScreen

        short_name = (
            self.tree.schema_name.split(":")[-1]
            if ":" in self.tree.schema_name
            else self.tree.schema_name
        )
        self.push_screen(
            ConfigScreen(group=self.tree.root, breadcrumb_parts=[short_name])
        )
        return

    # Legacy default — unchanged.
    from pydantic_studio.renderers.textual_.screens import EditorScreen

    self.push_screen(EditorScreen(tree=self.tree, save_path=self.save_path))
```

If the existing `on_mount` differs in signature, preserve all of its pre-existing behavior — only insert the env-var early-return block at the top. **Do not modify** any other StudioApp method.

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_dispatch.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Run the full unit suite to verify nothing regressed**

```
./.venv/Scripts/python.exe -m pytest tests/unit -p no:playwright -q
```

Expected: all green. The `test_textual_app.py` and `test_textual_widgets.py` legacy tests must still pass — the env var is unset in their test envs, so they hit the unchanged EditorScreen path.

- [ ] **Step 6: Manual smoke (one-off; not committed)**

Run the example with the flag set to eyeball the new chrome in a real terminal:

```
$env:PYDANTIC_STUDIO_TUI_V2 = "1"
./.venv/Scripts/python.exe examples/01_basic_settings.py tui
```

Expected: see the new ConfigScreen with breadcrumb `AppSettings`, the 5 field rows with placeholder cells (string values shown as text, bool as `False`/`True`, etc.), the 2-line footer hint bar. Up/down arrows should move the focus marker. No editing is wired yet — Enter does nothing (cells land in M2). Ctrl+C exits. Then unset:

```
Remove-Item Env:PYDANTIC_STUDIO_TUI_V2
```

Do not commit this step's output; it's just a manual confirmation. If something looks off (e.g., the modal hugs the left edge, the breadcrumb shows `__main__.AppSettings`), file a follow-up note in the M2 plan rather than patching here.

- [ ] **Step 7: Commit**

```
git add src/pydantic_studio/renderers/textual_/app.py tests/unit/test_tui_v2_dispatch.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): feature-flag dispatch in StudioApp.on_mount (M1 T7)

When PYDANTIC_STUDIO_TUI_V2=1 is set, StudioApp.on_mount pushes the
new ConfigScreen with breadcrumb seeded to the schema's short name.
Otherwise the legacy EditorScreen path is unchanged. The env var is
read once at mount; toggling at runtime does not switch screens. 2
new dispatch tests + the existing legacy test suite all pass.

This completes M1 (chrome). M2 will replace PlaceholderCell with
real editor cells (TextCell, BoolCell, ChoiceCell, SecretCell) and
land actual editing on the focused row.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final review (run after all 7 tasks land)

- [ ] **Run the full test suite one more time**

```
./.venv/Scripts/python.exe -m pytest tests/unit -p no:playwright -q
```

Expected: all green. New tests added: 1 (theme) + 6 (breadcrumb) + 6 (footer) + 10 (field row) + 9 (field list) + 5 (config screen) + 2 (dispatch) = **39 new tests** across **7 new test files**.

- [ ] **Run ruff over all M1 files**

```
./.venv/Scripts/python.exe -m ruff check src/pydantic_studio/renderers/textual_/widgets/breadcrumb.py src/pydantic_studio/renderers/textual_/widgets/footer_hints.py src/pydantic_studio/renderers/textual_/widgets/field_row.py src/pydantic_studio/renderers/textual_/widgets/field_list.py src/pydantic_studio/renderers/textual_/screens.py src/pydantic_studio/renderers/textual_/app.py tests/unit/test_tui_v2_*.py
```

Expected: `All checks passed!`

- [ ] **Manual confirmation in terminal**

```
$env:PYDANTIC_STUDIO_TUI_V2 = "1"
./.venv/Scripts/python.exe examples/01_basic_settings.py tui
```

Verify:
- The screen shows a single ConfigScreen with breadcrumb `AppSettings` at the top.
- The 5 fields render as rows with focus on `name`.
- Up/down arrows move the focus marker (`▸`).
- The footer hint bar shows `↑↓ navigate · Enter edit · Tab cycle · Esc back` on line 1 and `Ctrl+S save · Ctrl+Q quit` on line 2.
- Ctrl+C exits cleanly.

Then unset and confirm legacy still works:

```
Remove-Item Env:PYDANTIC_STUDIO_TUI_V2
./.venv/Scripts/python.exe examples/01_basic_settings.py tui
```

Verify the original sidebar + editor pane TUI mounts.

- [ ] **Update the project journal / spec to mark M1 done**

No file change — just note in the merge commit body that M1 is complete and the next plan covers M2 (leaf cells: TextCell, BoolCell, ChoiceCell, SecretCell).

---

## Out of scope for M1

These are M2–M6 work, listed here to keep M1 focused:

- Any editable cell (TextCell, BoolCell, ChoiceCell, SecretCell). M1 ships PlaceholderCell only.
- Drill-down on Enter for Group / Sequence / Mapping / Union. The drill marker is drawn but Enter is a no-op.
- ChooserScreen for choice cells with >7 options.
- SequenceScreen, MappingScreen, ErrorsScreen.
- Ctrl+S save flow (validation + save_yaml + exit). The legacy bindings still apply when on EditorScreen; the new ConfigScreen has no Ctrl+S binding yet.
- Ctrl+Q cancel flow.
- The legacy widgets/scalars.py / containers.py / editor.py / sidebar.py modules and their tests. They stay running as the default until M6.

---

## Definition of done

- All 7 tasks committed, in order, on `feat/tui-config-aesthetic-redesign`.
- 44 new unit tests pass; all prior unit tests still pass; ruff clean.
- Manual smoke confirms ConfigScreen mounts under the flag and EditorScreen mounts without it.
- The merge commit on `main` is a `--no-ff` merge per project convention; tag the branch tip as `v0.3.0-tui-v2-m1` before merging.

---

## What's next (M2 preview, not in this plan)

After M1 lands, the next plan (`2026-05-...-tui-redesign-m2-cells.md`) will:
- Replace `PlaceholderCell` with a `Cell` base class + four concrete cells: `TextCell`, `BoolCell`, `ChoiceCell`, `SecretCell`.
- Wire `FieldRow` to dispatch to the right cell based on `node.kind`.
- Add inline edit mode on `Enter`, commit via `FormTree.set_value`, show error helper on validation failure.
- Add Space-toggle for bool, Tab-cycle for small-choice enums/literals, push `ChooserScreen` for large-choice.
- Land Ctrl+S save / Ctrl+Q cancel keybinds.

Per the spec, M3 brings container drill-down; M4 the Sequence/Mapping screens; M5 union variant cycling + ErrorsScreen; M6 cutover.
