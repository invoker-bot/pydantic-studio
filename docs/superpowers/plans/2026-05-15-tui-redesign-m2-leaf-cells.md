# TUI Redesign M2: Leaf Cells Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace M1's `PlaceholderCell` with four real editor cells (`TextCell`, `BoolCell`, `ChoiceCell`, `SecretCell`) so the TUI is actually editable again. Each cell handles its node kinds, manages an idle ↔ editing lifecycle, and routes commits through `FormTree.set_value`. ChooserScreen handles choice fields with > 7 options. Footer hint bar swaps modes when a cell enters/exits edit via a Textual `Message`. Save (Ctrl+S) and Cancel (Ctrl+Q) are out of scope — they land in M3.

**Architecture:** New `widgets/cells/` package houses the four cell classes + a `Cell` base + a `_parse_for_kind` helper resurrected from the cutover-deleted `scalars.py`. `FieldRow` swaps its single `PlaceholderCell(node)` dispatch for a kind-based factory function. Cell lifecycle (idle/editing) is internal to each cell; transitions post Textual messages that `ConfigScreen` listens for to flip the footer mode. ChooserScreen is a small push-screen for the >7-choice case.

**Tech Stack:** Textual 8.x (existing), Pydantic v2, pytest + pytest-asyncio with Textual's Pilot harness.

---

## Scope and constraints

- Branch already created and checked out: `feat/tui-v2-m2-leaf-cells`. M1 + legacy cutover merged at `78be196` on main; M2 builds on that.
- TDD throughout. One TDD cycle per task. Each task → its own commit.
- ASCII commit messages (HEREDOC). `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.
- Don't push. Don't run interactive TUI smokes from a subagent — Pilot tests are proof.
- Renderer files excluded from pyright; LSP noise is expected. The `# noqa: RUF001` pattern fixes ambiguous-Unicode lint when needed (precedent: T2 fixup `fdd2f55`).
- Test command: `./.venv/Scripts/python.exe -m pytest`. The `uv run` form fails on Windows; plain `pytest` has path issues.
- Spec: `docs/superpowers/specs/2026-05-15-tui-config-aesthetic-redesign-design.md` §5.3 (Per-kind cell behavior).

**Out of scope (M3+):**
- Ctrl+S save flow (validate → save_yaml → exit).
- Ctrl+Q cancel flow (set app.cancelled, exit).
- Container drill-down for Group/Sequence/Mapping/Union (M3-M5).
- ErrorsScreen for save-time validation failures (M5).
- AnyValueNode kind (folds in later — Treat as TextCell with JSON in M3 housekeeping).

---

## File structure

**Files to create:**

| Path | Responsibility |
|---|---|
| `src/pydantic_studio/renderers/textual_/widgets/cells/__init__.py` | Package marker + a `make_cell(node)` factory dispatcher. |
| `src/pydantic_studio/renderers/textual_/widgets/cells/parse.py` | `parse_for_kind(kind, raw) -> (ok, value)` — resurrects the helper deleted with `scalars.py` during cutover. Covers 16 leaf kinds. |
| `src/pydantic_studio/renderers/textual_/widgets/cells/base.py` | `Cell(Widget)` abstract base. Defines lifecycle (`enter_edit()` / `exit_edit()`), the `EditModeEntered`/`EditModeExited` Messages, and the `commit(value)` helper that routes through `FormTree.set_value`. |
| `src/pydantic_studio/renderers/textual_/widgets/cells/text_cell.py` | `TextCell(Cell)` — covers 16 leaf kinds (string/int/float/decimal/date/datetime/time/timedelta/ip_address/ip_network/url/email/path/uuid/pattern/bytes). Enter → inline `Input`; Enter commits via `parse_for_kind`; Esc cancels. |
| `src/pydantic_studio/renderers/textual_/widgets/cells/bool_cell.py` | `BoolCell(Cell)` — Space (or Enter) toggles immediately; no edit mode. |
| `src/pydantic_studio/renderers/textual_/widgets/cells/choice_cell.py` | `ChoiceCell(Cell)` — Tab/← /→ cycles in place when ≤7 choices; >7 pushes ChooserScreen. |
| `src/pydantic_studio/renderers/textual_/widgets/cells/secret_cell.py` | `SecretCell(Cell)` — masked render; Enter opens `Input(password=True)` for edit. |
| `tests/unit/test_tui_v2_parse.py` | Unit tests for `parse_for_kind`. |
| `tests/unit/test_tui_v2_cell_base.py` | Unit tests for `Cell` base lifecycle + Messages. |
| `tests/unit/test_tui_v2_cell_text.py` | Unit tests for TextCell. |
| `tests/unit/test_tui_v2_cell_bool.py` | Unit tests for BoolCell. |
| `tests/unit/test_tui_v2_cell_choice.py` | Unit tests for ChoiceCell + ChooserScreen. |
| `tests/unit/test_tui_v2_cell_secret.py` | Unit tests for SecretCell. |

**Files to modify:**

| Path | Change |
|---|---|
| `src/pydantic_studio/renderers/textual_/widgets/field_row.py` | Replace the hard-coded `PlaceholderCell(self._node)` in `compose()` with `make_cell(self._node, path)`. Drop `PlaceholderCell` definition. Update `value_text` proxy. |
| `src/pydantic_studio/renderers/textual_/widgets/__init__.py` | Drop `PlaceholderCell` export. The cells live under `cells/` and aren't surfaced as top-level widgets (internal to FieldRow). |
| `src/pydantic_studio/renderers/textual_/screens.py` | Add `ChooserScreen` class for ChoiceCell large-choice drill. Add `on_edit_mode_entered`/`on_edit_mode_exited` handlers that flip the FooterHints mode. |
| `tests/unit/test_tui_v2_field_row.py` | The 2 `PlaceholderCell` tests die; the row-shell tests stay (label/marker/drill marker/error helper). Add 1 test for kind-based dispatch. |

**Files NOT touched:**
- `theme.tcss` — palette unchanged. Cells inherit `.field-row--value` styling.
- `widgets/breadcrumb.py`, `widgets/footer_hints.py`, `widgets/field_list.py` — chrome layer is stable.

---

## Test infrastructure

Same `_HostApp(App)` pattern as M1: a host app per test file that mounts the widget under test.

```python
import pytest
from textual.app import App

class _Host(App):
    """Mounts a single widget for Pilot-driven testing."""
    def __init__(self, widget):
        super().__init__()
        self._widget = widget
    def compose(self):
        yield self._widget
```

For cell tests that need a real `node` to commit against, build one via `build_form_tree(_Schema)` in the test body — same pattern as `test_tui_v2_field_row.py`.

Run all unit tests with:
```
./.venv/Scripts/python.exe -m pytest tests/unit -p no:playwright -q
```

---

## Task 1: parse_for_kind helper

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/cells/__init__.py` (empty for now — populated in T7)
- Create: `src/pydantic_studio/renderers/textual_/widgets/cells/parse.py`
- Test: `tests/unit/test_tui_v2_parse.py`

The cutover deleted `widgets/scalars.py` along with its `_parse_for_kind` function. This task resurrects it as a public `parse_for_kind` (no leading underscore — it's the cells package's public surface) under `cells/parse.py`. The same logic also lives duplicated in `src/pydantic_studio/renderers/html/routes.py:_parse_for_kind`; that copy stays for now and is consolidated in a separate housekeeping task post-M2.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_parse.py`:

```python
"""Unit tests for cells.parse.parse_for_kind — converts a raw string
from a text Input into the typed value the node expects.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from pydantic_studio.renderers.textual_.widgets.cells.parse import parse_for_kind


@pytest.mark.parametrize(
    ("kind", "raw", "expected"),
    [
        ("string", "alpha", "alpha"),
        ("int", "42", 42),
        ("float", "0.5", 0.5),
        ("decimal", "9.99", Decimal("9.99")),
        ("datetime", "2025-01-01T12:00:00", datetime(2025, 1, 1, 12, 0, 0)),
        ("date", "2025-01-01", date(2025, 1, 1)),
        ("time", "02:30:00", time(2, 30, 0)),
        ("ip_address", "10.0.0.1", "10.0.0.1"),  # stored as str; node validates
        ("ip_network", "10.0.0.0/24", "10.0.0.0/24"),
        ("url", "https://example.com", "https://example.com"),
        ("email", "ops@example.com", "ops@example.com"),
        ("path", "/etc/conf", "/etc/conf"),
        ("pattern", "^[a-z]+$", "^[a-z]+$"),
        ("secret", "hunter2", "hunter2"),
        ("uuid", "00000000-0000-0000-0000-000000000001", UUID(int=1)),
        ("bytes", "deadbeef", b"\xde\xad\xbe\xef"),
    ],
)
def test_parse_for_kind_happy_path(kind: str, raw: str, expected) -> None:
    ok, value = parse_for_kind(kind, raw)
    assert ok is True
    assert value == expected


def test_parse_for_kind_empty_returns_none() -> None:
    """Empty input passes (ok=True) with value=None so the node's
    validate_value gets to decide whether None is acceptable (e.g.,
    Optional[T] fields)."""
    ok, value = parse_for_kind("string", "")
    assert ok is True
    assert value is None


def test_parse_for_kind_int_bad_input_returns_failure() -> None:
    ok, value = parse_for_kind("int", "not-a-number")
    assert ok is False
    assert value is None


def test_parse_for_kind_float_bad_input_returns_failure() -> None:
    ok, value = parse_for_kind("float", "abc")
    assert ok is False
    assert value is None


def test_parse_for_kind_decimal_bad_input_returns_failure() -> None:
    ok, value = parse_for_kind("decimal", "not-numeric")
    assert ok is False
    assert value is None


def test_parse_for_kind_uuid_bad_input_returns_failure() -> None:
    ok, value = parse_for_kind("uuid", "not-a-uuid")
    assert ok is False
    assert value is None


def test_parse_for_kind_bytes_odd_hex_returns_failure() -> None:
    """bytes.fromhex rejects odd-length hex; the function surfaces this
    as ok=False instead of letting the ValueError escape."""
    ok, value = parse_for_kind("bytes", "abc")  # odd length
    assert ok is False
    assert value is None


def test_parse_for_kind_strips_whitespace() -> None:
    ok, value = parse_for_kind("int", "  42  ")
    assert ok is True
    assert value == 42


def test_parse_for_kind_unknown_kind_returns_failure() -> None:
    """A kind the helper doesn't know about returns ok=False, not a
    surprise raise. Defensive — the dispatcher in FieldRow ensures we
    never reach here in practice."""
    ok, value = parse_for_kind("not-a-kind", "anything")
    assert ok is False
    assert value is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_parse.py -v
```

Expected: 23 FAILs (16 parametrized + 7 explicit) with `ModuleNotFoundError`.

- [ ] **Step 3: Create the cells package + parse.py**

Create empty `src/pydantic_studio/renderers/textual_/widgets/cells/__init__.py`:

```python
"""Per-kind editor cells for the TUI v2 FieldRow.

Each cell handles one logical group of node kinds (text/numeric leaves,
bool, enum/literal choice, secret). FieldRow dispatches to the right
cell via ``make_cell(node, path)`` from this package.
"""

from __future__ import annotations
```

(Note: `make_cell` factory lands in T7 once all cells exist; M2 T1 leaves the package body docstring-only.)

Create `src/pydantic_studio/renderers/textual_/widgets/cells/parse.py`:

```python
"""Parse raw text input into the typed value a node expects.

Resurrects the helper that lived in the cutover-deleted ``scalars.py``.
Same surface, different name (no leading underscore — this is the
cells package's public parser).

For 16 leaf kinds the function returns ``(True, value)`` on success
and ``(False, None)`` on any parse failure. Empty input is treated as
None with ``ok=True`` so the calling cell can defer to the node's
own ``validate_value`` for Optional[T] handling.
"""

from __future__ import annotations

from typing import Any


def parse_for_kind(kind: str, raw: str) -> tuple[bool, Any]:
    """Convert ``raw`` to the type ``kind`` expects.

    Returns ``(ok, value)``. ``ok=False`` means the raw string could not
    be parsed (e.g., "abc" for kind="int"); the caller should display a
    parse error and leave the node's value unchanged. ``ok=True`` with
    ``value=None`` means the user entered empty text — let the node's
    validate_value decide.
    """
    raw = raw.strip()
    if raw == "":
        return True, None

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
            from datetime import timedelta

            from pydantic import TypeAdapter

            return True, TypeAdapter(timedelta).validate_python(raw)
        if kind in ("ip_address", "ip_network", "url", "email", "path", "pattern"):
            # Node stores these as strings; the node's validate_value parses.
            return True, raw
        if kind == "secret":
            return True, raw
        if kind == "uuid":
            from uuid import UUID

            return True, UUID(raw)
        if kind == "bytes":
            # Hex by default — matches BytesNode.field_serializer convention.
            return True, bytes.fromhex(raw)
    except (ValueError, TypeError):
        return False, None
    return False, None
```

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_parse.py -v
```

Expected: 23 PASS.

- [ ] **Step 5: Verify ruff**

```
./.venv/Scripts/python.exe -m ruff check src/pydantic_studio/renderers/textual_/widgets/cells/ tests/unit/test_tui_v2_parse.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/cells/__init__.py src/pydantic_studio/renderers/textual_/widgets/cells/parse.py tests/unit/test_tui_v2_parse.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): parse_for_kind helper for cell input parsing (M2 T1)

Resurrects the parse helper that lived in the cutover-deleted
scalars.py. Covers 16 leaf kinds (string, int, float, decimal,
datetime, date, time, timedelta, ip_address, ip_network, url,
email, path, pattern, secret, uuid, bytes).

Returns (ok, value): ok=True with value=None for empty input
(node's validate_value handles Optional[T]); ok=False on any
parse error (caller displays parse error, value unchanged).
Strips whitespace, defensive on unknown kinds.

23 unit tests (16 parametrized happy-path + 7 explicit edge cases:
empty, bad int / float / decimal / uuid / bytes, whitespace strip,
unknown kind).

The same logic remains duplicated in routes.py:_parse_for_kind;
that copy is consolidated in a separate post-M2 housekeeping task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Cell base class + lifecycle messages

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/cells/base.py`
- Test: `tests/unit/test_tui_v2_cell_base.py`

`Cell` is the abstract base for all per-kind cells. It defines:
- `__init__(node, path, form_tree)` — every cell holds these three.
- `value_text` property — the display text in idle mode.
- `enter_edit()` / `exit_edit()` — lifecycle that posts `EditModeEntered` / `EditModeExited` messages so the surrounding screen can swap footer mode.
- `commit(value)` — calls `form_tree.set_value(path, value)` and returns the `ValidationResult`. On failure, the cell can show an error.

The base class is `abstract` only in convention — subclasses are expected to override `compose()` to render their idle UI, and to call `enter_edit()` / `exit_edit()` themselves. No `@abstractmethod` decorators (Textual `Widget` doesn't play well with `ABCMeta`).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_cell_base.py`:

```python
"""Unit tests for Cell base lifecycle + Messages."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App
from textual.widgets import Static

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.cells.base import (
    Cell,
    EditModeEntered,
    EditModeExited,
)


class _Schema(BaseModel):
    name: str = "alpha"


class _StubCell(Cell):
    """Minimal concrete subclass: renders a Static."""

    def compose(self):
        yield Static(self.value_text, classes="field-row--value")

    @property
    def value_text(self) -> str:
        v = getattr(self._node, "value", None)
        return "" if v is None else str(v)


class _Host(App):
    def __init__(self, cell: _StubCell) -> None:
        super().__init__()
        self._cell = cell
        self.entered_events: list[EditModeEntered] = []
        self.exited_events: list[EditModeExited] = []

    def compose(self):
        yield self._cell

    def on_edit_mode_entered(self, event: EditModeEntered) -> None:
        self.entered_events.append(event)

    def on_edit_mode_exited(self, event: EditModeExited) -> None:
        self.exited_events.append(event)


def _build_tree_and_node():
    tree = build_form_tree(_Schema)
    node = tree.root.find("name")
    assert node is not None
    return tree, node


@pytest.mark.asyncio
async def test_cell_idle_value_text_reads_node_value() -> None:
    tree, node = _build_tree_and_node()
    tree.set_value("name", "beta")
    cell = _StubCell(node=node, path="name", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "beta"


@pytest.mark.asyncio
async def test_cell_enter_edit_posts_event() -> None:
    tree, node = _build_tree_and_node()
    cell = _StubCell(node=node, path="name", form_tree=tree)
    host = _Host(cell)
    async with host.run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        assert len(host.entered_events) == 1
        assert host.entered_events[0].path == "name"


@pytest.mark.asyncio
async def test_cell_exit_edit_posts_event() -> None:
    tree, node = _build_tree_and_node()
    cell = _StubCell(node=node, path="name", form_tree=tree)
    host = _Host(cell)
    async with host.run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        cell.exit_edit()
        await pilot.pause()
        assert len(host.exited_events) == 1
        assert host.exited_events[0].path == "name"


@pytest.mark.asyncio
async def test_cell_commit_success_returns_ok_and_mutates_tree() -> None:
    tree, node = _build_tree_and_node()
    cell = _StubCell(node=node, path="name", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        result = cell.commit("new-name")
        assert result.ok is True
        assert tree.root.find("name").value == "new-name"


@pytest.mark.asyncio
async def test_cell_commit_failure_returns_errors_and_leaves_tree() -> None:
    """A failed commit returns ok=False with errors; the tree is not
    mutated (validate-first contract)."""

    class _ConstrainedSchema(BaseModel):
        port: int = 8080

    tree = build_form_tree(_ConstrainedSchema)
    tree.set_value("port", 8080)
    node = tree.root.find("port")
    cell = _StubCell(node=node, path="port", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # int is fine; pass a string that set_value can't coerce -> failure.
        result = cell.commit("not-an-int")
        assert result.ok is False
        assert len(result.errors) > 0
        assert tree.root.find("port").value == 8080  # unchanged


@pytest.mark.asyncio
async def test_cell_tracks_editing_flag() -> None:
    tree, node = _build_tree_and_node()
    cell = _StubCell(node=node, path="name", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.editing is False
        cell.enter_edit()
        assert cell.editing is True
        cell.exit_edit()
        assert cell.editing is False
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_cell_base.py -v
```

Expected: 6 FAILs with `ModuleNotFoundError: cells.base`.

- [ ] **Step 3: Implement Cell base**

Create `src/pydantic_studio/renderers/textual_/widgets/cells/base.py`:

```python
"""Cell base class + edit-lifecycle messages.

Subclasses override ``compose()`` to render their idle UI and call
``enter_edit()`` / ``exit_edit()`` to drive the lifecycle. The base
posts ``EditModeEntered`` / ``EditModeExited`` messages so the
surrounding screen (ConfigScreen) can flip the footer mode without
needing a parent reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from textual.message import Message
from textual.widget import Widget

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree
    from pydantic_studio.tree.validation import ValidationResult


@dataclass
class EditModeEntered(Message):
    """Posted by a Cell when it enters edit mode."""

    path: str


@dataclass
class EditModeExited(Message):
    """Posted by a Cell when it exits edit mode (commit OR cancel)."""

    path: str


class Cell(Widget):
    """Base class for per-kind editor cells.

    Subclasses are responsible for:
    - overriding ``compose()`` to render their idle UI
    - calling ``enter_edit()`` / ``exit_edit()`` at the right moments
    - implementing ``value_text`` property for tests + chrome proxies

    The base provides:
    - ``commit(value)`` — routes a typed value through
      ``form_tree.set_value(path, value)`` and returns the result
    - ``editing`` — bool flag that's True between enter_edit/exit_edit
    """

    DEFAULT_CSS = ""

    def __init__(self, node: AnyNode, path: str, form_tree: FormTree) -> None:
        super().__init__()
        self._node = node
        self._path = path
        self._form_tree = form_tree
        self._editing = False

    @property
    def node(self) -> AnyNode:
        return self._node

    @property
    def path(self) -> str:
        return self._path

    @property
    def editing(self) -> bool:
        return self._editing

    @property
    def value_text(self) -> str:
        """Subclasses override for kind-specific display formatting.

        Default reads ``node.value`` with str() and empty for None.
        """
        v = getattr(self._node, "value", None)
        return "" if v is None else str(v)

    def enter_edit(self) -> None:
        if self._editing:
            return
        self._editing = True
        self.post_message(EditModeEntered(path=self._path))

    def exit_edit(self) -> None:
        if not self._editing:
            return
        self._editing = False
        self.post_message(EditModeExited(path=self._path))

    def commit(self, value: Any) -> ValidationResult:
        """Route a typed value through FormTree.set_value and return
        the result. The tree owns validation; the cell just dispatches.
        """
        return self._form_tree.set_value(self._path, value)
```

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_cell_base.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Verify ruff**

```
./.venv/Scripts/python.exe -m ruff check src/pydantic_studio/renderers/textual_/widgets/cells/base.py tests/unit/test_tui_v2_cell_base.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/cells/base.py tests/unit/test_tui_v2_cell_base.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): Cell base class + edit lifecycle messages (M2 T2)

Cell(Widget) base for all per-kind editor cells. Defines:
- (node, path, form_tree) constructor signature
- value_text property (default str(node.value) with empty for None)
- enter_edit() / exit_edit() lifecycle, idempotent, sets internal flag
- editing property (bool, True between enter/exit)
- commit(value) -> ValidationResult, routes through FormTree.set_value

EditModeEntered / EditModeExited Textual messages (dataclasses
carrying the cell's path) bubble up so ConfigScreen can flip the
FooterHints mode without needing a parent reference.

6 unit tests via a _StubCell concrete subclass: value_text reads
node.value, enter_edit posts an EditModeEntered, exit_edit posts
EditModeExited, commit-success returns ok=True and mutates the
tree, commit-failure returns ok=False and leaves the tree
unchanged (validate-first), editing flag flips correctly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: TextCell

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/cells/text_cell.py`
- Test: `tests/unit/test_tui_v2_cell_text.py`

`TextCell` is the workhorse — it covers 16 of the 24 node kinds. Idle state shows the value as text (`str(node.value)`, with hex encoding for bytes). On `enter_edit()`, the Static gets replaced with a Textual `Input` widget pre-filled with the current value. **Enter** commits via `parse_for_kind` → `Cell.commit`. **Esc** cancels. A failed parse or validate returns the cell to idle state and surfaces the error through the FieldRow's error-helper line (via a `set_error` callback the FieldRow installs).

For M2, the error surfacing is direct: the `TextCell` exposes a `last_error: str | None` property; `FieldRow` queries it after `commit()` returns and calls `row.set_error(cell.last_error)`. This is simpler than threading another Message; we revisit during M5 when ErrorsScreen lands.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_cell_text.py`:

```python
"""Unit tests for TextCell — covers 16 leaf node kinds via parse_for_kind."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App
from textual.widgets import Input, Static

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.cells.text_cell import TextCell


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 5


class _Host(App):
    def __init__(self, cell: TextCell) -> None:
        super().__init__()
        self._cell = cell

    def compose(self):
        yield self._cell


def _make_cell(field: str, value):
    tree = build_form_tree(_Schema)
    tree.set_value(field, value)
    node = tree.root.find(field)
    assert node is not None
    return tree, node, TextCell(node=node, path=field, form_tree=tree)


@pytest.mark.asyncio
async def test_text_cell_idle_renders_string_value() -> None:
    _, _, cell = _make_cell("name", "beta")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "beta"
        # Static shows the value in idle mode.
        assert cell.query_one(Static).renderable == "beta"


@pytest.mark.asyncio
async def test_text_cell_idle_renders_int_value() -> None:
    _, _, cell = _make_cell("count", 42)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "42"


@pytest.mark.asyncio
async def test_text_cell_enter_edit_swaps_to_input() -> None:
    _, _, cell = _make_cell("name", "beta")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        # Input is mounted; Static is gone or hidden.
        input_widget = cell.query_one(Input)
        assert input_widget.value == "beta"
        assert cell.editing is True


@pytest.mark.asyncio
async def test_text_cell_commit_on_enter_in_input() -> None:
    tree, _, cell = _make_cell("name", "beta")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        input_widget = cell.query_one(Input)
        input_widget.value = "gamma"
        await input_widget.action_submit()
        await pilot.pause()
        assert tree.root.find("name").value == "gamma"
        assert cell.editing is False
        # Back to idle text rendering.
        assert cell.value_text == "gamma"


@pytest.mark.asyncio
async def test_text_cell_esc_cancels_edit() -> None:
    tree, _, cell = _make_cell("name", "beta")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        # Esc triggers cell.cancel_edit (binding wires it).
        cell.cancel_edit()
        await pilot.pause()
        assert tree.root.find("name").value == "beta"  # unchanged
        assert cell.editing is False


@pytest.mark.asyncio
async def test_text_cell_unparseable_int_sets_last_error() -> None:
    tree, _, cell = _make_cell("count", 5)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        input_widget = cell.query_one(Input)
        input_widget.value = "not-an-int"
        await input_widget.action_submit()
        await pilot.pause()
        # Tree NOT mutated.
        assert tree.root.find("count").value == 5
        # Cell records the parse failure.
        assert cell.last_error is not None
        assert "parse" in cell.last_error.lower() or "int" in cell.last_error.lower()
        # Exits edit mode.
        assert cell.editing is False


@pytest.mark.asyncio
async def test_text_cell_validate_failure_sets_last_error() -> None:
    """An int that parses fine but violates a constraint (e.g., ge=1)
    surfaces via the FormTree's validate-first contract."""
    from pydantic import Field

    class _Constrained(BaseModel):
        port: int = Field(default=8080, ge=1, le=65535)

    tree = build_form_tree(_Constrained)
    tree.set_value("port", 8080)
    node = tree.root.find("port")
    cell = TextCell(node=node, path="port", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        input_widget = cell.query_one(Input)
        input_widget.value = "99999"  # > 65535
        await input_widget.action_submit()
        await pilot.pause()
        assert tree.root.find("port").value == 8080  # unchanged
        assert cell.last_error is not None
        assert cell.editing is False


@pytest.mark.asyncio
async def test_text_cell_bytes_renders_hex_and_parses_hex() -> None:
    class _BSchema(BaseModel):
        salt: bytes = b""

    tree = build_form_tree(_BSchema)
    tree.set_value("salt", b"\xde\xad")
    node = tree.root.find("salt")
    cell = TextCell(node=node, path="salt", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "dead"  # hex of b"\xde\xad"
        cell.enter_edit()
        await pilot.pause()
        input_widget = cell.query_one(Input)
        assert input_widget.value == "dead"
        input_widget.value = "beef"
        await input_widget.action_submit()
        await pilot.pause()
        assert tree.root.find("salt").value == b"\xbe\xef"
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_cell_text.py -v
```

Expected: 8 FAILs with `ModuleNotFoundError: cells.text_cell`.

- [ ] **Step 3: Implement TextCell**

Create `src/pydantic_studio/renderers/textual_/widgets/cells/text_cell.py`:

```python
"""TextCell — covers 16 leaf node kinds via parse_for_kind.

Idle: renders ``str(node.value)`` (with hex encoding for bytes).
Editing: replaces the Static with a Textual Input pre-filled with the
current value. Enter commits via parse_for_kind -> Cell.commit;
Esc cancels without mutating. Parse failures and validate-first
rejections both stash a message on ``last_error`` for FieldRow to
read after the round-trip.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Input, Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell
from pydantic_studio.renderers.textual_.widgets.cells.parse import parse_for_kind

if TYPE_CHECKING:
    from textual.app import ComposeResult


class TextCell(Cell):
    """Single-line editor for textual leaf kinds."""

    DEFAULT_CSS = ""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_error: str | None = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def value_text(self) -> str:
        v = getattr(self._node, "value", None)
        if v is None:
            return ""
        if self._node.kind == "bytes" and isinstance(v, (bytes, bytearray)):
            return bytes(v).hex()
        return str(v)

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value")

    def enter_edit(self) -> None:
        if self.editing:
            return
        super().enter_edit()
        self._last_error = None
        # Swap the Static for an Input. Order: mount the Input, remove
        # the Static, focus the Input.
        try:
            static = self.query_one(Static)
        except Exception:
            static = None
        new_input = Input(value=self.value_text, classes="field-row--value")
        self.mount(new_input)
        if static is not None:
            static.remove()
        new_input.focus()

    def cancel_edit(self) -> None:
        """Esc handler — exit edit without mutating."""
        if not self.editing:
            return
        self._exit_to_idle()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter on the Input widget."""
        raw = event.value
        ok, parsed = parse_for_kind(self._node.kind, raw)
        if not ok:
            self._last_error = f"cannot parse {raw!r} as {self._node.kind}"
            self._exit_to_idle()
            return
        result = self.commit(parsed)
        if not result.ok:
            self._last_error = "; ".join(result.errors) or "invalid"
            self._exit_to_idle()
            return
        self._last_error = None
        self._exit_to_idle()

    def _exit_to_idle(self) -> None:
        """Tear down the Input and re-mount the Static (idle view)."""
        try:
            input_widget = self.query_one(Input)
        except Exception:
            input_widget = None
        new_static = Static(self.value_text, classes="field-row--value")
        self.mount(new_static)
        if input_widget is not None:
            input_widget.remove()
        super().exit_edit()
```

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_cell_text.py -v
```

Expected: 8 PASS.

- [ ] **Step 5: Verify ruff**

```
./.venv/Scripts/python.exe -m ruff check src/pydantic_studio/renderers/textual_/widgets/cells/text_cell.py tests/unit/test_tui_v2_cell_text.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/cells/text_cell.py tests/unit/test_tui_v2_cell_text.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): TextCell for 16 leaf kinds (M2 T3)

TextCell(Cell) covers string / int / float / decimal / datetime /
date / time / timedelta / ip_address / ip_network / url / email /
path / uuid / pattern / bytes. Idle renders str(node.value) (hex
for bytes); enter_edit swaps Static for an Input pre-filled with
the current value. Enter commits via parse_for_kind -> commit;
Esc cancels. Parse failures and FormTree validate-first rejections
both record on last_error so FieldRow can surface the helper line.

8 unit tests: idle-string, idle-int, enter_edit-swaps-to-Input,
commit-on-enter, esc-cancels, parse-failure-sets-last_error,
validate-failure-sets-last_error, bytes-renders-and-parses-hex.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: BoolCell

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/cells/bool_cell.py`
- Test: `tests/unit/test_tui_v2_cell_bool.py`

BoolCell renders `[ off ]` or `[ on  ]` (fixed-width 7-char chips for alignment). Space (or Enter) toggles the value immediately via `commit(not current)`. No edit mode — no Input widget, no enter/exit cycle. The cell IS the toggle.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_cell_bool.py`:

```python
"""Unit tests for BoolCell — Space/Enter toggles the value immediately."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.cells.bool_cell import BoolCell


class _Schema(BaseModel):
    debug: bool = False


class _Host(App):
    def __init__(self, cell: BoolCell) -> None:
        super().__init__()
        self._cell = cell

    def compose(self):
        yield self._cell


def _make_cell(initial: bool):
    tree = build_form_tree(_Schema)
    tree.set_value("debug", initial)
    node = tree.root.find("debug")
    assert node is not None
    return tree, BoolCell(node=node, path="debug", form_tree=tree)


@pytest.mark.asyncio
async def test_bool_cell_idle_false_renders_off_chip() -> None:
    _, cell = _make_cell(False)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "[ off ]"


@pytest.mark.asyncio
async def test_bool_cell_idle_true_renders_on_chip() -> None:
    _, cell = _make_cell(True)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "[ on  ]"


@pytest.mark.asyncio
async def test_bool_cell_toggle_flips_false_to_true() -> None:
    tree, cell = _make_cell(False)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.toggle()
        await pilot.pause()
        assert tree.root.find("debug").value is True
        assert cell.value_text == "[ on  ]"


@pytest.mark.asyncio
async def test_bool_cell_toggle_flips_true_to_false() -> None:
    tree, cell = _make_cell(True)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.toggle()
        await pilot.pause()
        assert tree.root.find("debug").value is False
        assert cell.value_text == "[ off ]"


@pytest.mark.asyncio
async def test_bool_cell_toggle_from_none_treats_as_false() -> None:
    """If value is None (never set), toggle commits True."""
    tree = build_form_tree(_Schema)
    node = tree.root.find("debug")
    cell = BoolCell(node=node, path="debug", form_tree=tree)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.toggle()
        await pilot.pause()
        assert tree.root.find("debug").value is True


@pytest.mark.asyncio
async def test_bool_cell_does_not_enter_edit_mode() -> None:
    """BoolCell has no inline-input edit cycle."""
    _, cell = _make_cell(False)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # toggle should NOT trigger the edit lifecycle.
        cell.toggle()
        await pilot.pause()
        assert cell.editing is False
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_cell_bool.py -v
```

Expected: 6 FAILs.

- [ ] **Step 3: Implement BoolCell**

Create `src/pydantic_studio/renderers/textual_/widgets/cells/bool_cell.py`:

```python
"""BoolCell — Space/Enter toggles the value immediately.

No edit mode, no inline Input widget. The cell IS the toggle. Idle
rendering uses fixed-width 7-char chips (``[ off ]`` and ``[ on  ]``)
so the value column doesn't jitter when the user flips the state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell

if TYPE_CHECKING:
    from textual.app import ComposeResult


_OFF = "[ off ]"
_ON = "[ on  ]"


class BoolCell(Cell):
    """Inline toggle for BoolNode."""

    DEFAULT_CSS = ""

    @property
    def value_text(self) -> str:
        v = bool(getattr(self._node, "value", False) or False)
        return _ON if v else _OFF

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value")

    def toggle(self) -> None:
        """Flip the boolean and commit. No edit mode."""
        current = bool(getattr(self._node, "value", False) or False)
        self.commit(not current)
        # Re-render the static.
        try:
            static = self.query_one(Static)
        except Exception:
            return
        static.update(self.value_text)
```

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_cell_bool.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Verify ruff**

```
./.venv/Scripts/python.exe -m ruff check src/pydantic_studio/renderers/textual_/widgets/cells/bool_cell.py tests/unit/test_tui_v2_cell_bool.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/cells/bool_cell.py tests/unit/test_tui_v2_cell_bool.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): BoolCell with immediate toggle (M2 T4)

BoolCell(Cell) renders fixed-width chips ([ off ] / [ on  ], both
7 chars so the value column does not jitter). toggle() commits
not(current) immediately via Cell.commit; no edit-mode cycle. A
None initial value is treated as False so the first toggle commits
True.

6 unit tests: idle-false-chip, idle-true-chip, toggle-flips-each-way,
toggle-from-None-commits-True, does-not-enter-edit-mode.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: ChoiceCell + ChooserScreen

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/cells/choice_cell.py`
- Modify: `src/pydantic_studio/renderers/textual_/screens.py` (append `ChooserScreen` class)
- Test: `tests/unit/test_tui_v2_cell_choice.py`

ChoiceCell handles enum and literal node kinds. ≤7 choices → renders `‹ value ›` and cycles in place on Tab / ←/→. >7 choices → renders the value with a `>` drill marker; Enter pushes `ChooserScreen` for selection.

`ChooserScreen(node, path, form_tree)` is a tiny screen that shows one row per option, lets the user navigate up/down, and commits on Enter (then pops back).

Both small and large modes call `commit(chosen_value)` — the cell stays an idle widget; no Cell edit-lifecycle for the small case.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_cell_choice.py`:

```python
"""Unit tests for ChoiceCell (enum + literal) and ChooserScreen for
the >7 choices case.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

import pytest
from pydantic import BaseModel
from textual.app import App

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.cells.choice_cell import ChoiceCell


class _Level(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"


class _Small(BaseModel):
    level: _Level = _Level.INFO


class _Literal(BaseModel):
    color: Literal["red", "green", "blue"] = "green"


class _BigEnum(str, Enum):
    A = "a"
    B = "b"
    C = "c"
    D = "d"
    E = "e"
    F = "f"
    G = "g"
    H = "h"


class _Large(BaseModel):
    letter: _BigEnum = _BigEnum.A


class _Host(App):
    def __init__(self, cell: ChoiceCell) -> None:
        super().__init__()
        self._cell = cell

    def compose(self):
        yield self._cell


def _make_cell(schema_class: type[BaseModel], field: str, initial):
    tree = build_form_tree(schema_class)
    tree.set_value(field, initial)
    node = tree.root.find(field)
    assert node is not None
    return tree, ChoiceCell(node=node, path=field, form_tree=tree)


@pytest.mark.asyncio
async def test_choice_cell_small_renders_chevron_chip() -> None:
    _, cell = _make_cell(_Small, "level", _Level.INFO)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # Small (3 choices) renders the inline-cycle chrome.
        assert cell.value_text.startswith("‹") and cell.value_text.endswith("›")
        assert "info" in cell.value_text


@pytest.mark.asyncio
async def test_choice_cell_small_cycle_next() -> None:
    tree, cell = _make_cell(_Small, "level", _Level.INFO)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.cycle_next()
        await pilot.pause()
        # info -> warn (third in DEBUG, INFO, WARN order)
        assert tree.root.find("level").value == _Level.WARN


@pytest.mark.asyncio
async def test_choice_cell_small_cycle_prev() -> None:
    tree, cell = _make_cell(_Small, "level", _Level.INFO)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.cycle_prev()
        await pilot.pause()
        # info -> debug
        assert tree.root.find("level").value == _Level.DEBUG


@pytest.mark.asyncio
async def test_choice_cell_small_cycle_wraps() -> None:
    tree, cell = _make_cell(_Small, "level", _Level.WARN)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.cycle_next()
        await pilot.pause()
        # warn -> debug (wraps)
        assert tree.root.find("level").value == _Level.DEBUG


@pytest.mark.asyncio
async def test_choice_cell_literal_works_like_enum() -> None:
    tree, cell = _make_cell(_Literal, "color", "green")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.cycle_next()
        await pilot.pause()
        assert tree.root.find("color").value == "blue"


@pytest.mark.asyncio
async def test_choice_cell_large_renders_drill_chip() -> None:
    _, cell = _make_cell(_Large, "letter", _BigEnum.A)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        # >7 choices: no chevron, just the value (drill marker is on FieldRow).
        assert cell.value_text == "a"
        assert cell.large_choice is True


@pytest.mark.asyncio
async def test_choice_cell_large_open_chooser_screen() -> None:
    """When ChoiceCell.open_chooser() is called for a large-choice
    field, a ChooserScreen is pushed onto the app's screen stack."""
    from pydantic_studio.renderers.textual_.screens import ChooserScreen

    tree, cell = _make_cell(_Large, "letter", _BigEnum.A)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.open_chooser()
        await pilot.pause()
        assert isinstance(cell.app.screen, ChooserScreen)


@pytest.mark.asyncio
async def test_chooser_screen_lists_all_options_and_commits_on_select() -> None:
    """The ChooserScreen exposes a list of options; calling its
    select(idx) commits the choice and pops the screen."""
    from pydantic_studio.renderers.textual_.screens import ChooserScreen

    tree = build_form_tree(_Large)
    tree.set_value("letter", _BigEnum.A)
    node = tree.root.find("letter")
    screen = ChooserScreen(node=node, path="letter", form_tree=tree)

    class _AppHost(App):
        def on_mount(self) -> None:
            self.push_screen(screen)

    async with _AppHost().run_test() as pilot:
        await pilot.pause()
        # 8 options for _BigEnum.
        assert len(screen.options) == 8
        # Pick the 5th option (E).
        screen.select(4)
        await pilot.pause()
        assert tree.root.find("letter").value == _BigEnum.E
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_cell_choice.py -v
```

Expected: 8 FAILs.

- [ ] **Step 3: Implement ChoiceCell**

Create `src/pydantic_studio/renderers/textual_/widgets/cells/choice_cell.py`:

```python
"""ChoiceCell — covers enum + literal node kinds.

Up to 7 choices renders ``‹ value ›`` and cycles in place on Tab /
left / right. More than 7 renders just the value (the FieldRow's
drill marker tells the user to press Enter); Enter pushes ChooserScreen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.widgets import Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell

if TYPE_CHECKING:
    from textual.app import ComposeResult


_SMALL_THRESHOLD = 7


class ChoiceCell(Cell):
    """Inline cycle (small) or drill-to-screen (large) for enum + literal."""

    DEFAULT_CSS = ""

    @property
    def _choices(self) -> list[tuple[str, Any]]:
        """Return [(label, value)] for the node's choices.

        EnumNode.choices is list[tuple[str, member]]; LiteralNode.choices
        is list[Any]. Normalize to (label_str, raw_value).
        """
        node = self._node
        if node.kind == "enum":
            return list(node.choices)
        # literal: each choice is the literal value itself.
        return [(str(c), c) for c in node.choices]

    @property
    def large_choice(self) -> bool:
        return len(self._choices) > _SMALL_THRESHOLD

    @property
    def value_text(self) -> str:
        v = getattr(self._node, "value", None)
        label = self._label_for(v)
        if self.large_choice:
            return label
        return f"‹ {label} ›"  # noqa: RUF001

    def _label_for(self, value: Any) -> str:
        if value is None:
            return ""
        for label, raw in self._choices:
            if raw == value:
                return label
        return str(value)

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value")

    def cycle_next(self) -> None:
        self._cycle(+1)

    def cycle_prev(self) -> None:
        self._cycle(-1)

    def _cycle(self, delta: int) -> None:
        if self.large_choice:
            return
        choices = self._choices
        if not choices:
            return
        current = getattr(self._node, "value", None)
        idx = 0
        for i, (_, raw) in enumerate(choices):
            if raw == current:
                idx = i
                break
        new_idx = (idx + delta) % len(choices)
        new_value = choices[new_idx][1]
        result = self.commit(new_value)
        if not result.ok:
            return
        try:
            static = self.query_one(Static)
        except Exception:
            return
        static.update(self.value_text)

    def open_chooser(self) -> None:
        """Push the ChooserScreen for large-choice fields."""
        from pydantic_studio.renderers.textual_.screens import ChooserScreen

        if not self.large_choice:
            return
        self.app.push_screen(
            ChooserScreen(node=self._node, path=self._path, form_tree=self._form_tree)
        )
```

Append `ChooserScreen` to `src/pydantic_studio/renderers/textual_/screens.py`. Add the imports first (Container, ListView, ListItem, Label) and `AnyNode`/`FormTree` in TYPE_CHECKING:

```python
class ChooserScreen(Screen):
    """Push-screen presenter for ChoiceCell large-choice fields.

    Lists all options; up/down to navigate, Enter to commit + pop.
    """

    CSS_PATH = "theme.tcss"

    def __init__(
        self,
        node: AnyNode,
        path: str,
        form_tree: FormTree,
    ) -> None:
        super().__init__()
        self._node = node
        self._path = path
        self._form_tree = form_tree

    @property
    def options(self) -> list[tuple[str, Any]]:
        if self._node.kind == "enum":
            return list(self._node.choices)
        return [(str(c), c) for c in self._node.choices]

    def select(self, idx: int) -> None:
        if not (0 <= idx < len(self.options)):
            return
        _, value = self.options[idx]
        self._form_tree.set_value(self._path, value)
        self.app.pop_screen()

    def compose(self) -> ComposeResult:
        from textual.widgets import Label, ListItem, ListView

        with ListView(id="chooser-list"):
            for label, _ in self.options:
                yield ListItem(Label(label))
```

Add to the TYPE_CHECKING block at the top of screens.py if not already present:

```python
if TYPE_CHECKING:
    from typing import Any
    from pydantic_studio.tree.nodes import AnyNode, FormTree
```

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_cell_choice.py -v
```

Expected: 8 PASS.

- [ ] **Step 5: Verify ruff**

```
./.venv/Scripts/python.exe -m ruff check src/pydantic_studio/renderers/textual_/widgets/cells/choice_cell.py src/pydantic_studio/renderers/textual_/screens.py tests/unit/test_tui_v2_cell_choice.py
```

Expected: clean. The chevron `‹` U+2039 / `›` U+203A in `value_text` is `# noqa: RUF001`d at the source.

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/cells/choice_cell.py src/pydantic_studio/renderers/textual_/screens.py tests/unit/test_tui_v2_cell_choice.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): ChoiceCell + ChooserScreen for enum/literal (M2 T5)

ChoiceCell(Cell) covers enum + literal node kinds.

Up to 7 choices: renders inline chevron chip ‹ value ›;
cycle_next()/cycle_prev() commit the next/prev choice in place
(wraps at the ends).

More than 7 choices: renders the bare value (FieldRow's drill
marker indicates the action). open_chooser() pushes a new
ChooserScreen onto the app stack; the screen lists all options,
select(idx) commits and pops.

ChooserScreen lives in screens.py next to ConfigScreen; it uses
Textual's ListView for the option list. The screen reuses
theme.tcss.

8 unit tests covering small-render, cycle-next/prev, wrap,
literal-works-like-enum, large-render, large-opens-chooser,
chooser-options-and-select.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: SecretCell

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/widgets/cells/secret_cell.py`
- Test: `tests/unit/test_tui_v2_cell_secret.py`

SecretCell renders `**********` regardless of the underlying value (never reveal in display mode). On `enter_edit()`, it opens a Textual `Input(password=True)` so keystrokes show as bullets while the user types. Commit flow is identical to TextCell minus the parse step (secrets are stored as plain strings or bytes; node.validate_value handles the actual type).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tui_v2_cell_secret.py`:

```python
"""Unit tests for SecretCell — masked display + password Input on edit."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, SecretStr
from textual.app import App
from textual.widgets import Input, Static

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.cells.secret_cell import SecretCell


class _Schema(BaseModel):
    api_key: SecretStr = SecretStr("")


class _Host(App):
    def __init__(self, cell: SecretCell) -> None:
        super().__init__()
        self._cell = cell

    def compose(self):
        yield self._cell


def _make_cell(initial: str | None):
    tree = build_form_tree(_Schema)
    if initial is not None:
        tree.set_value("api_key", initial)
    node = tree.root.find("api_key")
    assert node is not None
    return tree, SecretCell(node=node, path="api_key", form_tree=tree)


@pytest.mark.asyncio
async def test_secret_cell_idle_renders_mask_even_with_value() -> None:
    _, cell = _make_cell("super-secret-value")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "**********"


@pytest.mark.asyncio
async def test_secret_cell_idle_renders_empty_for_none() -> None:
    _, cell = _make_cell(None)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == ""


@pytest.mark.asyncio
async def test_secret_cell_enter_edit_uses_password_input() -> None:
    _, cell = _make_cell("hunter2")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        input_widget = cell.query_one(Input)
        assert input_widget.password is True
        # Pre-fills with the actual value (NOT the mask).
        assert input_widget.value == "hunter2"


@pytest.mark.asyncio
async def test_secret_cell_commit_via_enter() -> None:
    tree, cell = _make_cell("old")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        input_widget = cell.query_one(Input)
        input_widget.value = "new-secret"
        await input_widget.action_submit()
        await pilot.pause()
        node = tree.root.find("api_key")
        # SecretStr's underlying value is the committed string.
        assert node.value == "new-secret" or (
            hasattr(node.value, "get_secret_value")
            and node.value.get_secret_value() == "new-secret"
        )
        assert cell.editing is False
        # Idle back to mask.
        assert cell.value_text == "**********"


@pytest.mark.asyncio
async def test_secret_cell_esc_cancels() -> None:
    tree, cell = _make_cell("hunter2")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        cell.cancel_edit()
        await pilot.pause()
        assert cell.editing is False
        # Value unchanged.
        node = tree.root.find("api_key")
        assert (
            node.value == "hunter2"
            or (
                hasattr(node.value, "get_secret_value")
                and node.value.get_secret_value() == "hunter2"
            )
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_cell_secret.py -v
```

Expected: 5 FAILs.

- [ ] **Step 3: Implement SecretCell**

Create `src/pydantic_studio/renderers/textual_/widgets/cells/secret_cell.py`:

```python
"""SecretCell — masked display + password Input on edit.

Idle always renders ``**********`` (never reveal in display mode).
Editing swaps to a Textual Input with ``password=True`` so the
keystrokes show as bullets while the user types. Empty value shows
as empty (no mask) so the user knows the field is unset.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Input, Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell

if TYPE_CHECKING:
    from textual.app import ComposeResult


_MASK = "**********"


class SecretCell(Cell):
    """Masked editor for SecretNode."""

    DEFAULT_CSS = ""

    @property
    def _underlying_value(self) -> str:
        """Read node.value, unwrapping SecretStr if needed.

        The form tree stores either a plain str/bytes or a Pydantic
        SecretStr/SecretBytes depending on schema annotation. We need
        the plaintext for pre-filling the edit Input.
        """
        v = getattr(self._node, "value", None)
        if v is None:
            return ""
        if hasattr(v, "get_secret_value"):
            inner = v.get_secret_value()
            if isinstance(inner, bytes):
                return inner.decode("utf-8", errors="replace")
            return str(inner)
        if isinstance(v, bytes):
            return v.decode("utf-8", errors="replace")
        return str(v)

    @property
    def value_text(self) -> str:
        # Never show the actual value at idle.
        return _MASK if self._underlying_value else ""

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value")

    def enter_edit(self) -> None:
        if self.editing:
            return
        super().enter_edit()
        try:
            static = self.query_one(Static)
        except Exception:
            static = None
        new_input = Input(
            value=self._underlying_value,
            password=True,
            classes="field-row--value",
        )
        self.mount(new_input)
        if static is not None:
            static.remove()
        new_input.focus()

    def cancel_edit(self) -> None:
        if not self.editing:
            return
        self._exit_to_idle()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.commit(event.value)
        self._exit_to_idle()

    def _exit_to_idle(self) -> None:
        try:
            input_widget = self.query_one(Input)
        except Exception:
            input_widget = None
        new_static = Static(self.value_text, classes="field-row--value")
        self.mount(new_static)
        if input_widget is not None:
            input_widget.remove()
        super().exit_edit()
```

- [ ] **Step 4: Run tests to verify they pass**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_cell_secret.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Verify ruff**

```
./.venv/Scripts/python.exe -m ruff check src/pydantic_studio/renderers/textual_/widgets/cells/secret_cell.py tests/unit/test_tui_v2_cell_secret.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/cells/secret_cell.py tests/unit/test_tui_v2_cell_secret.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): SecretCell with masked display + password edit (M2 T6)

SecretCell(Cell) renders ********** at idle regardless of the
underlying value (or empty if value is None / unset). enter_edit
opens a Textual Input(password=True) pre-filled with the plaintext
so the user can revise; bullet display masks the keystrokes.
Commit on Enter, Esc cancels. SecretStr / SecretBytes underlying
values are unwrapped via get_secret_value().

5 unit tests: idle-renders-mask, idle-renders-empty-for-none,
enter_edit-uses-password-input, commit-via-enter, esc-cancels.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: FieldRow dispatch + ConfigScreen footer wiring

**Files:**
- Modify: `src/pydantic_studio/renderers/textual_/widgets/cells/__init__.py` (add `make_cell` factory)
- Modify: `src/pydantic_studio/renderers/textual_/widgets/field_row.py` (replace PlaceholderCell dispatch with make_cell)
- Modify: `src/pydantic_studio/renderers/textual_/widgets/__init__.py` (drop PlaceholderCell export)
- Modify: `src/pydantic_studio/renderers/textual_/screens.py` (ConfigScreen handlers for EditModeEntered/Exited)
- Test: `tests/unit/test_tui_v2_field_row.py` (update — PlaceholderCell tests die, kind-dispatch tests added)

This is the integration task: now that all four cell classes exist, FieldRow dispatches to the right one based on `node.kind`. PlaceholderCell is deleted from field_row.py. ConfigScreen listens for EditModeEntered/Exited messages and flips FooterHints between `idle` and `editing` modes.

- [ ] **Step 1: Add `make_cell` factory**

Open `src/pydantic_studio/renderers/textual_/widgets/cells/__init__.py` and replace its body:

```python
"""Per-kind editor cells for the TUI v2 FieldRow.

Each cell handles one logical group of node kinds (text/numeric leaves,
bool, enum/literal choice, secret). FieldRow dispatches to the right
cell via ``make_cell(node, path, form_tree)`` from this package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_studio.renderers.textual_.widgets.cells.base import (
    Cell,
    EditModeEntered,
    EditModeExited,
)
from pydantic_studio.renderers.textual_.widgets.cells.bool_cell import BoolCell
from pydantic_studio.renderers.textual_.widgets.cells.choice_cell import ChoiceCell
from pydantic_studio.renderers.textual_.widgets.cells.secret_cell import SecretCell
from pydantic_studio.renderers.textual_.widgets.cells.text_cell import TextCell

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree


_TEXT_KINDS = {
    "string", "int", "float", "decimal",
    "datetime", "date", "time", "timedelta",
    "ip_address", "ip_network", "url", "email",
    "path", "uuid", "pattern", "bytes",
}


def make_cell(node: AnyNode, path: str, form_tree: FormTree) -> Cell:
    """Dispatch a node to its concrete Cell subclass.

    Containers (group/sequence/mapping/union) are not handled here yet —
    they get a ContainerCell stub in M3. For M2, they fall through to a
    TextCell rendering ``str(node.value)`` which approximates the legacy
    PlaceholderCell behavior.
    """
    kind = node.kind
    if kind in _TEXT_KINDS:
        return TextCell(node=node, path=path, form_tree=form_tree)
    if kind == "bool":
        return BoolCell(node=node, path=path, form_tree=form_tree)
    if kind in ("enum", "literal"):
        return ChoiceCell(node=node, path=path, form_tree=form_tree)
    if kind == "secret":
        return SecretCell(node=node, path=path, form_tree=form_tree)
    # group / sequence / mapping / union / any: M3+ adds ContainerCell.
    return TextCell(node=node, path=path, form_tree=form_tree)


__all__ = [
    "BoolCell",
    "Cell",
    "ChoiceCell",
    "EditModeEntered",
    "EditModeExited",
    "SecretCell",
    "TextCell",
    "make_cell",
]
```

- [ ] **Step 2: Rewrite the FieldRow tests for the new dispatch**

Open `tests/unit/test_tui_v2_field_row.py`. Replace the two PlaceholderCell tests with kind-dispatch tests. (Keep the row-shell tests: label/marker/focus/drill marker/error helper — those don't change.)

The replacement test bodies:

```python
# delete: test_placeholder_cell_renders_str_value
# delete: test_placeholder_cell_renders_empty_when_value_none
# add the two below:


@pytest.mark.asyncio
async def test_field_row_dispatches_string_to_text_cell() -> None:
    from pydantic_studio.renderers.textual_.widgets.cells import TextCell

    row = FieldRow(node=_node("name"), path="name", focused=False, form_tree=_tree_for("name"))
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert isinstance(row.query_one(TextCell), TextCell)


@pytest.mark.asyncio
async def test_field_row_dispatches_bool_to_bool_cell() -> None:
    from pydantic import BaseModel
    from pydantic_studio.renderers.textual_.widgets.cells import BoolCell

    class _BS(BaseModel):
        debug: bool = False

    tree = build_form_tree(_BS)
    tree.set_value("debug", True)
    node = tree.root.find("debug")
    row = FieldRow(node=node, path="debug", focused=False, form_tree=tree)
    async with _Host(row).run_test() as pilot:
        await pilot.pause()
        assert isinstance(row.query_one(BoolCell), BoolCell)
```

Also amend the `_node()` helper to additionally return the tree:

```python
def _tree_for(field_name: str):
    """Return a tree seeded with the field's default value."""
    tree = build_form_tree(_Schema)
    n = tree.root.find(field_name)
    assert n is not None
    if n.default is not None:
        tree.set_value(field_name, n.default)
    return tree
```

And update existing FieldRow constructor calls in the test file to pass `form_tree`:

```python
row = FieldRow(node=_node("name"), path="name", focused=False, form_tree=tree)
```

(The other tests need this too. Run them after the FieldRow change to see what breaks.)

- [ ] **Step 3: Run the updated tests to verify they fail (new ones) or break (constructor)**

```
./.venv/Scripts/python.exe -m pytest tests/unit/test_tui_v2_field_row.py -v
```

Expected: most tests now fail with `TypeError: FieldRow.__init__() got an unexpected keyword argument 'form_tree'` or similar. The two new dispatch tests fail with `NoMatches` or similar.

- [ ] **Step 4: Update FieldRow**

Open `src/pydantic_studio/renderers/textual_/widgets/field_row.py`. Replace its body:

```python
"""FieldRow — per-field row chrome with per-kind cell dispatch.

Composes focus marker + label + dotted leader + value cell + drill
marker, plus an optional error helper line below. The value cell is
selected by ``make_cell(node, path, form_tree)`` from the cells
package. ``PlaceholderCell`` is gone — TextCell/BoolCell/ChoiceCell/
SecretCell cover M2's editable surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

from pydantic_studio.renderers.textual_.widgets.cells import make_cell

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import AnyNode, FormTree


_FOCUS_MARKER = "▸"  # noqa: RUF001
_LEADER = " " + ("· " * 5)
_DRILLABLE_KINDS = {"group", "sequence", "mapping", "union"}


class FieldRow(Widget):
    """One row in FieldListView. Dispatches to a per-kind Cell."""

    DEFAULT_CSS = ""

    def __init__(
        self,
        node: AnyNode,
        path: str,
        form_tree: FormTree,
        focused: bool = False,
    ) -> None:
        super().__init__()
        self._node = node
        self._path = path
        self._form_tree = form_tree
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
        try:
            marker = self.query_one(".field-row--marker", Static)
            marker.update(self.marker_text)
        except Exception:
            return

    def set_error(self, message: str | None) -> None:
        self._error = message
        if message is None:
            self.remove_class("-error")
        else:
            self.add_class("-error")
        try:
            helper = self.query_one(".field-row--helper", Static)
            helper.update(self.helper_text)
        except Exception:
            return

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal():
                yield Static(self.marker_text, classes="field-row--marker")
                yield Static(self.label_text, classes="field-row--label")
                yield Static(_LEADER, classes="field-row--leader")
                yield make_cell(self._node, self._path, self._form_tree)
                yield Static(self.drill_marker_text, classes="field-row--drill")
            yield Static(self.helper_text, classes="field-row--helper")
```

Also update `FieldListView` in `src/pydantic_studio/renderers/textual_/widgets/field_list.py` to pass `form_tree` into each `FieldRow`. The `FieldListView.__init__` already has `group` and `base_path` — add a `form_tree` parameter. Update `compose()` to thread it through.

```python
class FieldListView(VerticalScroll):
    def __init__(
        self,
        group: GroupNode,
        form_tree: FormTree,
        base_path: str = "",
    ) -> None:
        super().__init__()
        self._group = group
        self._form_tree = form_tree
        self._base_path = base_path
        self._cursor: int = 0

    def compose(self) -> ComposeResult:
        for idx, child in enumerate(self._group.fields):
            path = (
                f"{self._base_path}.{child.name}" if self._base_path else child.name
            )
            yield FieldRow(
                node=child,
                path=path,
                form_tree=self._form_tree,
                focused=(idx == 0),
            )
```

And update `ConfigScreen.compose()` in `screens.py` to pass `form_tree`:

```python
def compose(self) -> ComposeResult:
    yield Breadcrumb(parts=self._breadcrumb_parts)
    yield FieldListView(
        group=self._group, form_tree=self._form_tree, base_path=""
    )
    yield FooterHints(mode="idle")
```

`ConfigScreen.__init__` needs a `form_tree` parameter too:

```python
def __init__(
    self,
    group: GroupNode,
    form_tree: FormTree,
    breadcrumb_parts: list[str],
) -> None:
    super().__init__()
    self._group = group
    self._form_tree = form_tree
    self._breadcrumb_parts = breadcrumb_parts
```

And add the EditMode message handlers + footer wiring:

```python
def on_edit_mode_entered(self, event) -> None:  # EditModeEntered
    """Flip footer to editing mode when a cell starts editing."""
    try:
        footer = self.query_one(FooterHints)
        footer.set_mode("editing")
    except Exception:
        return

def on_edit_mode_exited(self, event) -> None:  # EditModeExited
    """Flip footer back to idle when the cell exits edit."""
    try:
        footer = self.query_one(FooterHints)
        footer.set_mode("idle")
    except Exception:
        return
```

The `EditModeEntered` / `EditModeExited` types are imported at the top of `screens.py`:

```python
from pydantic_studio.renderers.textual_.widgets.cells import (
    EditModeEntered,  # noqa: F401 (referenced by handler dispatch)
    EditModeExited,   # noqa: F401
)
```

And the handler signatures use the imported types:

```python
def on_edit_mode_entered(self, event: EditModeEntered) -> None:
    ...
def on_edit_mode_exited(self, event: EditModeExited) -> None:
    ...
```

Update `StudioApp.on_mount` in `app.py` to pass `form_tree`:

```python
self.push_screen(
    ConfigScreen(
        group=self.tree.root,
        form_tree=self.tree,
        breadcrumb_parts=[short_name],
    )
)
```

Drop PlaceholderCell from `src/pydantic_studio/renderers/textual_/widgets/__init__.py`:

```python
from pydantic_studio.renderers.textual_.widgets.breadcrumb import Breadcrumb
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow
from pydantic_studio.renderers.textual_.widgets.footer_hints import FooterHints

__all__ = ["Breadcrumb", "FieldListView", "FieldRow", "FooterHints"]
```

Also update `tests/unit/test_tui_v2_field_list.py` and `tests/unit/test_tui_v2_config_screen.py` and `tests/unit/test_tui_v2_dispatch.py` to pass `form_tree` to FieldListView and ConfigScreen constructors. Read each test file, find the constructor calls, and add the `form_tree=tree` argument.

- [ ] **Step 5: Run the full unit suite**

```
./.venv/Scripts/python.exe -m pytest tests/unit -p no:playwright -q
```

Expected: all green. Test count should be roughly: 552 prior + 23 (parse) + 6 (cell base) + 8 (text) + 6 (bool) + 8 (choice) + 5 (secret) - 2 (deleted PlaceholderCell tests) + 2 (new dispatch tests) = ~608 tests.

- [ ] **Step 6: Verify ruff**

```
./.venv/Scripts/python.exe -m ruff check src/pydantic_studio/renderers/textual_/ tests/unit/test_tui_v2_*.py
```

Expected: clean.

- [ ] **Step 7: Commit**

```
git add src/pydantic_studio/renderers/textual_/widgets/cells/__init__.py src/pydantic_studio/renderers/textual_/widgets/field_row.py src/pydantic_studio/renderers/textual_/widgets/field_list.py src/pydantic_studio/renderers/textual_/widgets/__init__.py src/pydantic_studio/renderers/textual_/screens.py src/pydantic_studio/renderers/textual_/app.py tests/unit/test_tui_v2_field_row.py tests/unit/test_tui_v2_field_list.py tests/unit/test_tui_v2_config_screen.py tests/unit/test_tui_v2_dispatch.py
git commit -m "$(cat <<'EOF'
feat(tui-v2): FieldRow dispatch + footer mode wiring (M2 T7)

Replace PlaceholderCell with kind-based dispatch via make_cell(node,
path, form_tree). FieldRow grows a form_tree constructor parameter
(plumbed through FieldListView and ConfigScreen). The cells package
__init__ exports the four concrete cells + the factory.

ConfigScreen now handles EditModeEntered / EditModeExited messages
posted by cells and flips FooterHints between idle and editing.
This is the runtime feedback that tells the user when they are in
edit mode vs nav mode.

PlaceholderCell deleted from field_row.py and dropped from the
widgets package __init__. The two PlaceholderCell tests in
test_tui_v2_field_row.py are replaced with two kind-dispatch tests
(string -> TextCell, bool -> BoolCell). All other M1 chrome tests
keep working with the form_tree constructor parameter added.

Test count: 552 -> ~608 (+56 from M2 cells, -2 from deleted
PlaceholderCell tests, +2 from new dispatch tests).

M2 complete: TextCell, BoolCell, ChoiceCell (+ ChooserScreen),
SecretCell, FieldRow dispatch, footer mode switching. Editing
works for all leaf kinds. Save/Cancel (Ctrl+S / Ctrl+Q) land in
M3 along with container drill-down.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final review (run after all 7 tasks land)

- [ ] **Run the full test suite**

```
./.venv/Scripts/python.exe -m pytest tests/unit -p no:playwright -q
```

Expected: all green, ~608 tests passing.

- [ ] **Run ruff across all M2 files**

```
./.venv/Scripts/python.exe -m ruff check src/pydantic_studio/renderers/textual_/ tests/unit/test_tui_v2_*.py
```

Expected: `All checks passed!`

- [ ] **Manual smoke** (after all 7 tasks land)

```
python examples/01_basic_settings.py tui
```

Verify:
- ConfigScreen mounts (no env var needed — cutover is done).
- Focus on `name`. Up/down moves between rows.
- Press Enter on `name` — Input appears with current value pre-filled. Footer line 1 swaps to "Type to edit · Enter commit · Esc cancel".
- Type a new value and press Enter — value updates in place. Footer reverts to idle.
- Press Esc on a different row's Input — change discarded.
- Press Space on `debug` — `[ off ]` flips to `[ on  ]` and back.
- If the schema has an enum/literal with ≤7 choices, focus it and press Tab — value cycles through the options inline.
- Ctrl+C exits.

What still does NOT work (M3+ scope):
- Ctrl+S to save / Ctrl+Q to cancel.
- Drilling into a Group / Sequence / Mapping (Enter on those rows does nothing yet).
- ErrorsScreen on a save-time validation failure.

- [ ] **Tag and merge**

```
git tag v0.3.2-tui-v2-m2
git checkout main
git merge --no-ff feat/tui-v2-m2-leaf-cells -m "merge: feat/tui-v2-m2-leaf-cells - leaf cell editing (M2)"
git branch -d feat/tui-v2-m2-leaf-cells
```

---

## Out of scope for M2 (deferred to M3+)

- `Ctrl+S` save flow (validate, save_yaml, exit)
- `Ctrl+Q` cancel flow (set app.cancelled, exit)
- Container drill-down on Enter for Group / Sequence / Mapping / Union (M3 / M4)
- ErrorsScreen for save-time validation failures (M5)
- ContainerCell rendering the right summary per kind (M3)
- Sequence add/remove, Mapping rename, Union variant cycle (M4 / M5)
- AnyValueNode → TextCell with JSON-string mode (M3 housekeeping)
- Consolidate the duplicated `parse_for_kind` logic in `routes.py` (post-M2 housekeeping)

---

## Definition of done

- All 7 tasks committed in order on `feat/tui-v2-m2-leaf-cells`.
- ~56 new unit tests pass (23 parse + 6 cell base + 8 text + 6 bool + 8 choice + 5 secret); the 2 PlaceholderCell tests are deleted; 2 new dispatch tests pass.
- Full unit suite passes; ruff clean.
- Manual smoke confirms editing works for string, int, bool, and at least one enum/literal field.
- Tagged `v0.3.2-tui-v2-m2`; merged `--no-ff` to main; branch deleted.
- M3 plan to be drafted after M2 lands.
