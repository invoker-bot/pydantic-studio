# Shadcn Web Redesign — Phase 1: JSON API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a JSON-only API (`/api/tree`, `/api/mutations`, `/api/submit`, `/api/cancel`, `/api/heartbeat`) to `StudioServer`, **alongside** the existing HTMX HTML routes. No frontend yet, no deletions. The Phase 2 plan scaffolds Vite/React on top of this.

**Architecture:** A new module `serialize.py` wraps `FormTree.model_dump(mode="json")` (with `schema_class` and `snapshots` excluded) into a JSON shape, and dispatches the 8 mutation ops from §3.2 of the design spec onto the existing `tree.set_value` / `add_item` / etc. methods. `routes.py` registers seven new routes prefixed with `/api/` that share the `StudioServer.tree` state but return `application/json` and never touch the Jinja templates.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pytest + `fastapi.testclient.TestClient`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-14-shadcn-web-redesign-design.md`. This plan implements only §8 Phase 1 of that spec.

---

## File Structure

**Create:**
- `src/pydantic_studio/renderers/html/serialize.py` — `tree_to_json()` + `dispatch_mutation()`. ~120 lines.
- `tests/unit/test_html_serialize.py` — unit tests for both serializer functions, independent of FastAPI. ~250 lines.
- `tests/unit/test_html_api_routes.py` — TestClient tests for every new JSON route. ~200 lines.

**Modify:**
- `src/pydantic_studio/renderers/html/routes.py` — append a `register_api(app, server)` call into the existing `register(...)` flow. Existing HTML route definitions stay untouched.

**Do not touch in this phase:**
- `templates/` (deleted in Phase 6)
- `static/htmx.min.js`, `static/studio.css` (deleted in Phase 6)
- `server.py` `run_html_app` print/exit flow (already wired)

---

## Task 1: Scaffold serialize.py with tree_to_json for primitives

**Files:**
- Create: `src/pydantic_studio/renderers/html/serialize.py`
- Create: `tests/unit/test_html_serialize.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_html_serialize.py`:

```python
"""Unit tests for the JSON API serializer."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html.serialize import tree_to_json


class _Primitive(BaseModel):
    name: str = Field(description="Service identifier")
    workers: int = 4


def test_tree_to_json_returns_schema_name_and_root() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 8})
    data = tree_to_json(tree)
    assert data["schema_name"].endswith("_Primitive")
    assert data["root"]["kind"] == "group"
    field_kinds = {f["name"]: f["kind"] for f in data["root"]["fields"]}
    assert field_kinds == {"name": "string", "workers": "int"}


def test_tree_to_json_excludes_schema_class_and_snapshots() -> None:
    tree = build_form_tree(_Primitive)
    # Seed a snapshot so we can verify it's stripped.
    tree.set_value("name", "after")
    data = tree_to_json(tree)
    assert "schema_class" not in data
    assert "snapshots" not in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'pydantic_studio.renderers.html.serialize'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/pydantic_studio/renderers/html/serialize.py`:

```python
"""JSON serialization + mutation dispatch for the HTML renderer's JSON API.

The browser SPA built in later phases consumes ``tree_to_json`` to render
the form, and ``dispatch_mutation`` to apply edits. Both functions are
pure (no I/O, no FastAPI imports) so they can be unit-tested in isolation
from the route layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree


# Fields on FormTree itself that should not ship over the wire:
# - schema_class: a Python class object, not JSON-serialisable
# - snapshots:    list[bytes] of prior tree states (undo ring); each
#                 snapshot is ~the size of the tree, so including it N
#                 times bloats every response by N×
_TREE_EXCLUDE: set[str] = {"schema_class", "snapshots"}


def tree_to_json(tree: FormTree) -> dict[str, Any]:
    """Serialize a FormTree to a JSON-ready dict.

    The output shape mirrors §5.1 of the design spec: ``schema_name``,
    ``root`` (the root GroupNode), and a top-level ``unsaved_count``
    (derived from the snapshot ring) for the header badge.
    """
    data = tree.model_dump(mode="json", exclude=_TREE_EXCLUDE)
    data["unsaved_count"] = len(tree.snapshots)
    return data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/html/serialize.py tests/unit/test_html_serialize.py
git commit -m "feat(html): scaffold serialize.tree_to_json for JSON API

Returns a JSON-ready dict for FormTree, excluding the non-serialisable
schema_class field and the snapshots field (which would bloat every
response by ~N×). First step of the Phase 1 JSON API for the shadcn
web redesign.
"
```

---

## Task 2: tree_to_json covers nested groups, sequences, mappings, unions

**Files:**
- Modify: `tests/unit/test_html_serialize.py` (add fixtures + tests)
- Modify: `src/pydantic_studio/renderers/html/serialize.py` (likely no change — Pydantic discriminated-union serialization should handle this; the tests verify the assumption)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_html_serialize.py`:

```python
from typing import Annotated, Literal


class _Inner(BaseModel):
    host: str
    port: int = 5432


class _Outer(BaseModel):
    primary: _Inner
    tags: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


def test_tree_to_json_nested_group_renders_as_group_node() -> None:
    tree = build_form_tree(
        _Outer,
        existing={"primary": {"host": "db.internal", "port": 5432}},
    )
    data = tree_to_json(tree)
    primary = next(f for f in data["root"]["fields"] if f["name"] == "primary")
    assert primary["kind"] == "group"
    host = next(f for f in primary["fields"] if f["name"] == "host")
    assert host["kind"] == "string"
    assert host["value"] == "db.internal"


def test_tree_to_json_sequence_renders_as_sequence_node_with_items() -> None:
    tree = build_form_tree(_Outer, existing={"primary": {"host": "x"}, "tags": ["a", "b"]})
    data = tree_to_json(tree)
    tags = next(f for f in data["root"]["fields"] if f["name"] == "tags")
    assert tags["kind"] == "sequence"
    assert [item["value"] for item in tags["items"]] == ["a", "b"]


def test_tree_to_json_mapping_renders_as_mapping_node_with_entries() -> None:
    tree = build_form_tree(
        _Outer,
        existing={"primary": {"host": "x"}, "env": {"TZ": "UTC", "LOG": "info"}},
    )
    data = tree_to_json(tree)
    env = next(f for f in data["root"]["fields"] if f["name"] == "env")
    assert env["kind"] == "mapping"
    pairs = [(k["value"], v["value"]) for k, v in env["entries"]]
    assert pairs == [("TZ", "UTC"), ("LOG", "info")]


class _EmailVariant(BaseModel):
    kind: Literal["email"] = "email"
    address: str


class _SlackVariant(BaseModel):
    kind: Literal["slack"] = "slack"
    channel: str


_Notifier = Annotated[_EmailVariant | _SlackVariant, Field(discriminator="kind")]


class _WithUnion(BaseModel):
    notifier: _Notifier


def test_tree_to_json_union_renders_with_selected_variant() -> None:
    tree = build_form_tree(
        _WithUnion,
        existing={"notifier": {"kind": "email", "address": "a@x"}},
    )
    data = tree_to_json(tree)
    notifier = next(f for f in data["root"]["fields"] if f["name"] == "notifier")
    assert notifier["kind"] == "union"
    assert notifier["selected_index"] == 0
    assert notifier["selected"]["kind"] == "group"
    address = next(f for f in notifier["selected"]["fields"] if f["name"] == "address")
    assert address["value"] == "a@x"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: all 6 pass. Pydantic's built-in discriminated-union serialization produces this shape: `MappingNode.entries` is `list[tuple[AnyNode, AnyNode]]` (`tree/nodes.py:897`) which JSON-encodes as a list of 2-element arrays — the test destructures accordingly. `UnionNode.selected_index: int | None` and `UnionNode.selected: AnyNode | None` (`tree/nodes.py:922-923`) round-trip directly.

- [ ] **Step 3: Implementation note**

No implementation change needed in this task — `tree_to_json` from Task 1 already produces the contract. These tests pin the JSON shape so future serializer refactors can't silently drift from what the TypeScript zod schemas (Phase 2) will expect.

- [ ] **Step 4: Run full serializer test file**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_html_serialize.py
git commit -m "test(html): confirm tree_to_json shape for nested + dynamic node kinds

Locks the JSON contract for nested groups, sequence items, mapping
entries (key/value pairs as two-tuples), and discriminated unions
(selected variant inlined). The TypeScript frontend's zod schemas will
mirror these shapes.
"
```

---

## Task 3: Validation envelope structure

**Files:**
- Modify: `src/pydantic_studio/renderers/html/serialize.py`
- Modify: `tests/unit/test_html_serialize.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_html_serialize.py`:

```python
from pydantic_studio.renderers.html.serialize import validation_envelope


def test_validation_envelope_ok_for_complete_tree() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 8})
    env = validation_envelope(tree)
    assert env == {"ok": True, "errors": []}


def test_validation_envelope_collects_per_field_errors() -> None:
    # Required field 'name' deliberately unset
    tree = build_form_tree(_Primitive)
    env = validation_envelope(tree)
    assert env["ok"] is False
    assert any("name" in e["path"] for e in env["errors"])
    for err in env["errors"]:
        assert set(err.keys()) >= {"path", "message"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: FAIL with `ImportError: cannot import name 'validation_envelope'`.

- [ ] **Step 3: Write the implementation**

Append to `src/pydantic_studio/renderers/html/serialize.py`:

```python
def validation_envelope(tree: FormTree) -> dict[str, Any]:
    """Aggregate the tree's current validation status as the API envelope.

    The envelope is returned alongside every tree-shaped response so the
    client can flag invalid fields without re-walking the tree. ``path``
    is the dotted form-tree path; ``message`` is the human-readable error.
    """
    from pydantic import ValidationError

    from pydantic_studio.exceptions import ValidationFailedError

    try:
        tree.to_instance()
    except ValidationFailedError as e:
        return {"ok": False, "errors": list(_iter_failed_errors(e))}
    except ValidationError as e:
        return {
            "ok": False,
            "errors": [
                {"path": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
                for err in e.errors()
            ],
        }
    return {"ok": True, "errors": []}


def _iter_failed_errors(e: Any) -> Any:
    """ValidationFailedError stores a list[str] of pre-formatted messages
    shaped ``"<path>: <message>"``. Split each back into structured form."""
    for raw in getattr(e, "errors", []) or []:
        text = str(raw)
        if ": " in text:
            path, _, message = text.partition(": ")
            yield {"path": path, "message": message}
        else:
            yield {"path": "", "message": text}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/html/serialize.py tests/unit/test_html_serialize.py
git commit -m "feat(html): add validation_envelope for JSON API responses

Wraps tree.to_instance() into the {ok, errors} envelope from spec §5.2.
Per-error shape is {path, message} — paths are dotted form-tree paths,
ready for the client's click-to-jump-to-field affordance.
"
```

---

## Task 4: dispatch_mutation — set_value

**Files:**
- Modify: `src/pydantic_studio/renderers/html/serialize.py`
- Modify: `tests/unit/test_html_serialize.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_html_serialize.py`:

```python
from pydantic_studio.renderers.html.serialize import dispatch_mutation


def test_dispatch_set_value_updates_tree_and_returns_ok() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "before", "workers": 4})
    result = dispatch_mutation(tree, {"op": "set_value", "path": "name", "value": "after"})
    assert result.ok is True
    assert tree.root.find("name").value == "after"


def test_dispatch_set_value_validation_failure_leaves_tree_untouched() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 4})
    # workers is int; setting a non-int should fail validation
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "workers", "value": "not-an-int"}
    )
    assert result.ok is False
    assert tree.root.find("workers").value == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: FAIL with `ImportError: cannot import name 'dispatch_mutation'`.

- [ ] **Step 3: Write the implementation**

Append to `src/pydantic_studio/renderers/html/serialize.py`:

```python
from pydantic_studio.tree.validation import ValidationResult


def dispatch_mutation(tree: FormTree, mutation: dict[str, Any]) -> ValidationResult:
    """Apply one mutation from the JSON API onto the FormTree.

    ``mutation`` is the parsed JSON body — exactly the discriminated union
    described in spec §3.2. This function only handles the ``set_value``
    op for now; sequence / mapping / union ops land in later tasks.
    Unknown ops return a failure ValidationResult without touching the
    tree.
    """
    op = mutation.get("op")
    path = mutation.get("path", "")
    if op == "set_value":
        return tree.set_value(path, mutation.get("value"))
    return ValidationResult.fail([f"unknown op: {op!r}"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/html/serialize.py tests/unit/test_html_serialize.py
git commit -m "feat(html): dispatch_mutation supports set_value op

First op of the mutation contract. Other ops land in follow-up commits.
Unknown ops return a fail-shaped ValidationResult so the API can surface
client bugs without crashing.
"
```

---

## Task 5: dispatch_mutation — sequence ops (add_item, remove_item, move_item)

**Files:**
- Modify: `src/pydantic_studio/renderers/html/serialize.py`
- Modify: `tests/unit/test_html_serialize.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_html_serialize.py`:

```python
class _WithList(BaseModel):
    tags: list[str] = Field(default_factory=list)


def test_dispatch_add_item_appends_to_sequence() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a"]})
    result = dispatch_mutation(tree, {"op": "add_item", "path": "tags"})
    assert result.ok is True
    assert len(tree.root.find("tags").items) == 2


def test_dispatch_remove_item_pops_indexed_entry() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a", "b", "c"]})
    result = dispatch_mutation(
        tree, {"op": "remove_item", "path": "tags", "index": 1}
    )
    assert result.ok is True
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["a", "c"]


def test_dispatch_move_item_reorders_sequence() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a", "b", "c"]})
    result = dispatch_mutation(
        tree, {"op": "move_item", "path": "tags", "from": 0, "to": 2}
    )
    assert result.ok is True
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["b", "c", "a"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q -k dispatch_add_item or dispatch_remove_item or dispatch_move_item`
Expected: 3 FAILs — `dispatch_mutation` returns `unknown op` for each.

- [ ] **Step 3: Write the implementation**

Replace `dispatch_mutation` in `serialize.py`:

```python
def dispatch_mutation(tree: FormTree, mutation: dict[str, Any]) -> ValidationResult:
    """Apply one mutation from the JSON API onto the FormTree."""
    op = mutation.get("op")
    path = mutation.get("path", "")
    if op == "set_value":
        return tree.set_value(path, mutation.get("value"))
    if op == "add_item":
        return tree.add_item(path)
    if op == "remove_item":
        return tree.remove_item(path, int(mutation["index"]))
    if op == "move_item":
        return tree.move_item(path, int(mutation["from"]), int(mutation["to"]))
    return ValidationResult.fail([f"unknown op: {op!r}"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/html/serialize.py tests/unit/test_html_serialize.py
git commit -m "feat(html): dispatch_mutation supports sequence ops

add_item appends; remove_item pops by index; move_item reorders. Maps
to FormTree.add_item / remove_item / move_item respectively (spec §3.2).
"
```

---

## Task 6: dispatch_mutation — mapping ops (add_entry, remove_entry, rename_key)

**Files:**
- Modify: `src/pydantic_studio/renderers/html/serialize.py`
- Modify: `tests/unit/test_html_serialize.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_html_serialize.py`:

```python
class _WithDict(BaseModel):
    env: dict[str, str] = Field(default_factory=dict)


def test_dispatch_add_entry_appends_new_key() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC"}})
    result = dispatch_mutation(
        tree, {"op": "add_entry", "path": "env", "key": "LOG"}
    )
    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("TZ", "UTC"), ("LOG", None)]


def test_dispatch_remove_entry_drops_indexed_pair() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC", "LOG": "info"}})
    result = dispatch_mutation(
        tree, {"op": "remove_entry", "path": "env", "index": 0}
    )
    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("LOG", "info")]


def test_dispatch_rename_key_changes_key_at_index() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC"}})
    result = dispatch_mutation(
        tree,
        {"op": "rename_key", "path": "env", "index": 0, "new_key": "TIMEZONE"},
    )
    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("TIMEZONE", "UTC")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q -k dispatch_add_entry or dispatch_remove_entry or dispatch_rename_key`
Expected: 3 FAILs.

- [ ] **Step 3: Write the implementation**

Replace `dispatch_mutation` in `serialize.py`:

```python
def dispatch_mutation(tree: FormTree, mutation: dict[str, Any]) -> ValidationResult:
    """Apply one mutation from the JSON API onto the FormTree."""
    op = mutation.get("op")
    path = mutation.get("path", "")
    if op == "set_value":
        return tree.set_value(path, mutation.get("value"))
    if op == "add_item":
        return tree.add_item(path)
    if op == "remove_item":
        return tree.remove_item(path, int(mutation["index"]))
    if op == "move_item":
        return tree.move_item(path, int(mutation["from"]), int(mutation["to"]))
    if op == "add_entry":
        return tree.add_entry(path, key=str(mutation["key"]))
    if op == "remove_entry":
        return tree.remove_entry(path, int(mutation["index"]))
    if op == "rename_key":
        return tree.rename_key(
            path, int(mutation["index"]), str(mutation["new_key"])
        )
    return ValidationResult.fail([f"unknown op: {op!r}"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: 16 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/html/serialize.py tests/unit/test_html_serialize.py
git commit -m "feat(html): dispatch_mutation supports mapping ops

add_entry takes a key; remove_entry takes an index (not a key) so the
client doesn't have to worry about uniqueness; rename_key swaps at index.
"
```

---

## Task 7: dispatch_mutation — union op (select_variant)

**Files:**
- Modify: `src/pydantic_studio/renderers/html/serialize.py`
- Modify: `tests/unit/test_html_serialize.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_html_serialize.py`:

```python
class _UnionHolder(BaseModel):
    value: int | str


def test_dispatch_select_variant_switches_to_indexed_branch() -> None:
    tree = build_form_tree(_UnionHolder, existing={"value": 42})
    # variant 0 is int; switch to str (variant 1)
    result = dispatch_mutation(
        tree, {"op": "select_variant", "path": "value", "variant_index": 1}
    )
    assert result.ok is True
    val = tree.root.find("value")
    assert val.selected_index == 1
    assert val.selected.kind == "string"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q -k dispatch_select_variant`
Expected: FAIL — `dispatch_mutation` returns `unknown op`.

- [ ] **Step 3: Write the implementation**

Add the `select_variant` branch to `dispatch_mutation`:

```python
    if op == "select_variant":
        return tree.select_variant(path, int(mutation["variant_index"]))
    return ValidationResult.fail([f"unknown op: {op!r}"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: 17 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/html/serialize.py tests/unit/test_html_serialize.py
git commit -m "feat(html): dispatch_mutation supports select_variant op

Completes the 8 ops from the spec mutation contract. The dispatcher now
covers every public mutation method on FormTree (insert_item is omitted
— move_item handles reordering and the UI doesn't have an insert affordance).
"
```

---

## Task 8: dispatch_mutation — error cases

**Files:**
- Modify: `tests/unit/test_html_serialize.py`

(The error-handling code already exists from prior tasks; this task hardens it with explicit tests.)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_html_serialize.py`:

```python
def test_dispatch_unknown_op_fails_without_mutating() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 4})
    result = dispatch_mutation(tree, {"op": "nuke", "path": "name"})
    assert result.ok is False
    assert any("nuke" in e for e in result.errors)
    assert tree.root.find("name").value == "alpha"


def test_dispatch_missing_op_fails_without_mutating() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha"})
    result = dispatch_mutation(tree, {"path": "name", "value": "x"})
    assert result.ok is False
    assert tree.root.find("name").value == "alpha"


def test_dispatch_bad_path_fails_without_mutating() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha"})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "nope.does.not.exist", "value": "x"}
    )
    assert result.ok is False
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q -k dispatch_unknown_op or dispatch_missing_op or dispatch_bad_path`
Expected: 3 passed. The dispatcher already returns `unknown op` for unknown / missing ops (Task 4); `tree.set_value` is contractually fail-soft on unresolvable paths (`tree/nodes.py:1182`). No implementation change needed in this task — the tests pin behavior that downstream tasks must not break.

- [ ] **Step 3: Verify full suite**

Run: `uv run python -m pytest tests/unit/test_html_serialize.py -q`
Expected: 20 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_html_serialize.py
git commit -m "test(html): cover dispatch_mutation error paths

Unknown op, missing op, and unresolvable path all return ok=False without
mutating the tree. Locks in the safety net before the route layer
exposes dispatch_mutation to network input.
"
```

---

## Task 9: Route — GET /api/tree

**Files:**
- Create: `tests/unit/test_html_api_routes.py`
- Modify: `src/pydantic_studio/renderers/html/routes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_html_api_routes.py`:

```python
"""Tests for the JSON API routes added in shadcn redesign Phase 1."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html import StudioServer


class _Demo(BaseModel):
    name: str = Field(description="Service identifier")
    workers: int = 4


def _client(existing: dict | None = None) -> TestClient:
    tree = build_form_tree(_Demo, existing=existing)
    server = StudioServer(tree=tree, save_path=None)
    return TestClient(server.app)


def test_api_tree_returns_json_with_schema_and_root() -> None:
    client = _client({"name": "alpha", "workers": 8})
    response = client.get("/api/tree")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["schema_name"].endswith("_Demo")
    assert body["root"]["kind"] == "group"
    names = {f["name"] for f in body["root"]["fields"]}
    assert {"name", "workers"} <= names


def test_api_tree_includes_unsaved_count() -> None:
    client = _client({"name": "alpha"})
    body = client.get("/api/tree").json()
    assert body["unsaved_count"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/test_html_api_routes.py -q`
Expected: FAIL — 404 from FastAPI for `/api/tree`.

- [ ] **Step 3: Write the implementation**

Modify `src/pydantic_studio/renderers/html/routes.py`. At the bottom of the `register(app, server)` function, before the closing brace of `def register`, add:

```python
    # ----- JSON API (Phase 1 of the shadcn web redesign) -----
    from fastapi.responses import JSONResponse

    from pydantic_studio.renderers.html.serialize import tree_to_json

    @app.get("/api/tree", response_class=JSONResponse)
    async def api_tree() -> JSONResponse:
        return JSONResponse(content=tree_to_json(server.tree))
```

(Keep all existing HTML routes intact above this block.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_api_routes.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_html_api_routes.py src/pydantic_studio/renderers/html/routes.py
git commit -m "feat(html): GET /api/tree returns FormTree as JSON

First route of the JSON API. Coexists with the existing HTML routes —
the SPA scaffolded in Phase 2 will consume this, while the Jinja
templates keep working until Phase 6.
"
```

---

## Task 10: Route — POST /api/mutations

**Files:**
- Modify: `src/pydantic_studio/renderers/html/routes.py`
- Modify: `tests/unit/test_html_api_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_html_api_routes.py`:

```python
def test_api_mutations_set_value_returns_updated_tree() -> None:
    client = _client({"name": "before", "workers": 4})
    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": "name", "value": "after"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["validation"] == {"ok": True, "errors": []}
    name_field = next(f for f in body["tree"]["root"]["fields"] if f["name"] == "name")
    assert name_field["value"] == "after"


def test_api_mutations_validation_failure_returns_unchanged_tree() -> None:
    client = _client({"name": "alpha", "workers": 4})
    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": "workers", "value": "not-an-int"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["ok"] is False
    workers_field = next(
        f for f in body["tree"]["root"]["fields"] if f["name"] == "workers"
    )
    assert workers_field["value"] == 4


def test_api_mutations_unknown_op_returns_400() -> None:
    client = _client({"name": "alpha"})
    response = client.post(
        "/api/mutations", json={"op": "nuke", "path": "name"}
    )
    assert response.status_code == 400
    body = response.json()
    assert "nuke" in body["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/test_html_api_routes.py -q -k api_mutations`
Expected: 3 FAILs — 404 for `/api/mutations`.

- [ ] **Step 3: Write the implementation**

Append inside the JSON-API block of `routes.py`:

```python
    from pydantic_studio.renderers.html.serialize import (
        dispatch_mutation,
        validation_envelope,
    )

    @app.post("/api/mutations", response_class=JSONResponse)
    async def api_mutations(request: Request) -> JSONResponse:
        mutation = await request.json()
        result = dispatch_mutation(server.tree, mutation)
        # Unknown / malformed op → 400 so the client knows it's a request
        # bug, not a state issue. Validation failures of valid ops keep
        # 200 (the tree is untouched, ``validation`` reports what failed).
        if not result.ok and any("unknown op" in err for err in result.errors):
            return JSONResponse(
                status_code=400, content={"detail": "; ".join(result.errors)}
            )
        return JSONResponse(
            content={
                "tree": tree_to_json(server.tree),
                "validation": validation_envelope(server.tree),
                "mutation_result": {"ok": result.ok, "errors": list(result.errors)},
            }
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_api_routes.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/html/routes.py tests/unit/test_html_api_routes.py
git commit -m "feat(html): POST /api/mutations applies a mutation and returns the tree

Response envelope: {tree, validation, mutation_result}. Validation
failures keep 200 (the tree is intact, validation reports per-field
errors). Unknown ops return 400 so the client knows it's a request bug.
"
```

---

## Task 11: Routes — POST /api/submit + POST /api/cancel

**Files:**
- Modify: `src/pydantic_studio/renderers/html/routes.py`
- Modify: `tests/unit/test_html_api_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_html_api_routes.py`:

```python
def test_api_submit_marks_server_submitted_and_returns_ok() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app)
    response = client.post("/api/submit")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert server.submitted is True


def test_api_submit_validation_failure_returns_400_with_errors() -> None:
    # Required field 'name' deliberately unset
    tree = build_form_tree(_Demo)
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app)
    response = client.post("/api/submit")
    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["errors"]
    assert server.submitted is False


def test_api_cancel_marks_server_cancelled() -> None:
    tree = build_form_tree(_Demo, existing={"name": "x"})
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app)
    response = client.post("/api/cancel")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert server.cancelled is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/test_html_api_routes.py -q -k api_submit or api_cancel`
Expected: 3 FAILs — 404.

- [ ] **Step 3: Write the implementation**

Append inside the JSON-API block of `routes.py`:

```python
    @app.post("/api/submit", response_class=JSONResponse)
    async def api_submit() -> JSONResponse:
        from pydantic import ValidationError

        from pydantic_studio import save_yaml
        from pydantic_studio.exceptions import ValidationFailedError

        try:
            server.tree.to_instance()
        except (ValidationError, ValidationFailedError):
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "errors": validation_envelope(server.tree)["errors"],
                },
            )
        if server.save_path is not None:
            save_yaml(server.tree, server.save_path)
        server.submitted = True
        return JSONResponse(content={"ok": True})

    @app.post("/api/cancel", response_class=JSONResponse)
    async def api_cancel() -> JSONResponse:
        server.cancelled = True
        return JSONResponse(content={"ok": True})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_api_routes.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/html/routes.py tests/unit/test_html_api_routes.py
git commit -m "feat(html): POST /api/submit and /api/cancel

JSON variants of the existing HTML submit/cancel routes. Submit fails
400 with a per-field error list when validation fails (the tree stays
unchanged; client can show field errors). Cancel always succeeds.
"
```

---

## Task 12: Route — GET /api/heartbeat (JSON variant)

**Files:**
- Modify: `src/pydantic_studio/renderers/html/routes.py`
- Modify: `tests/unit/test_html_api_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_html_api_routes.py`:

```python
import time as _time


def test_api_heartbeat_returns_ok_and_records_timestamp() -> None:
    tree = build_form_tree(_Demo, existing={"name": "x"})
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app)
    before = _time.time()
    response = client.get("/api/heartbeat")
    after = _time.time()
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert before <= server.last_heartbeat_ts <= after
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/test_html_api_routes.py -q -k api_heartbeat`
Expected: FAIL — 404.

- [ ] **Step 3: Write the implementation**

Append inside the JSON-API block of `routes.py`:

```python
    @app.get("/api/heartbeat", response_class=JSONResponse)
    async def api_heartbeat() -> JSONResponse:
        import time as _t

        server.last_heartbeat_ts = _t.time()
        return JSONResponse(content={"ok": True})
```

(The existing HTML `/heartbeat` route stays — Phase 6 removes it once the React SPA replaces the heartbeat poll on its own template.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/test_html_api_routes.py -q`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/html/routes.py tests/unit/test_html_api_routes.py
git commit -m "feat(html): GET /api/heartbeat — JSON variant

Same semantics as the existing /heartbeat HTML route. Phase 6 drops the
HTML route once the SPA's template polls the JSON one.
"
```

---

## Task 13: Verify no regression + ruff clean + final commit

**Files:**
- Run-only; no edits unless something breaks.

- [ ] **Step 1: Run the full Python test suite**

Run: `uv run python -m pytest tests/ -q --deselect tests/unit/test_docs_build.py`
Expected: every test passes. New tests: 9 (api_routes) + 20 (serialize) = 29 new. Existing tests should be unchanged.

If any existing HTML route test fails, investigate: the JSON routes shouldn't affect the HTML routes, but if they share state (`server.tree`) and a test was relying on a specific call order, surface that.

- [ ] **Step 2: Ruff lint the touched files**

Run:
```bash
uv run ruff check src/pydantic_studio/renderers/html/serialize.py src/pydantic_studio/renderers/html/routes.py tests/unit/test_html_serialize.py tests/unit/test_html_api_routes.py
```
Expected: `All checks passed!`

If ruff complains about unused imports or formatting, fix and re-run.

- [ ] **Step 3: Sanity-check the routes via the dev server (optional but recommended)**

Run a quick manual smoke from the repo root:

```bash
uv run python -c "
from pydantic import BaseModel
from pydantic_studio import build_form_tree, StudioServer
from fastapi.testclient import TestClient

class M(BaseModel):
    name: str
    workers: int = 4

server = StudioServer(tree=build_form_tree(M, existing={'name': 'x', 'workers': 8}))
client = TestClient(server.app)
print('GET /api/tree ->', client.get('/api/tree').json())
print('POST /api/mutations ->', client.post('/api/mutations', json={'op':'set_value','path':'name','value':'y'}).json())
"
```

Expected: prints a JSON tree, then a tree with `name.value` updated to `"y"`.

- [ ] **Step 4: Final wrap-up commit (only if Step 3 or any fix-up required changes)**

If steps 1–3 needed a follow-up edit, commit it. Otherwise skip this step.

```bash
git status                # should be clean if no fixes were needed
```

If there are uncommitted fix-ups:
```bash
git add -- <specific files>
git commit -m "chore(html): post-implementation cleanup after Phase 1 verification"
```

- [ ] **Step 5: Phase 1 done — handoff note**

The JSON API is now live alongside the HTML routes. No user-visible change yet. The Phase 2 plan (frontend scaffold) will consume these endpoints from a Vite-built React app. Recommended branch name: `feature/shadcn-redesign-phase-1-json-api`; merge with `--no-ff` per the codebase convention, and tag the tip as `v0.2.0-phase-1` before merging.

---

## Self-review checklist (already applied)

- ✅ Spec §5.1 (`GET /api/tree`): Task 9.
- ✅ Spec §5.2 (`POST /api/mutations` + envelope): Tasks 4–8 (dispatcher), Task 10 (route).
- ✅ Spec §5.3 (`POST /api/submit`, `/api/cancel`, `/api/heartbeat`): Tasks 11–12.
- ✅ Spec §3.2 (8-op mutation contract): Tasks 4–7.
- ✅ Spec §3.1 (server-authoritative, no optimistic state): the mutation route returns the full updated tree on every call. Task 10.
- ✅ No `TBD`/`TODO`/placeholder text in any step.
- ✅ Method signatures are consistent across tasks (`tree_to_json`, `validation_envelope`, `dispatch_mutation`).
- ✅ `insert_item` deliberately omitted (spec §3.2 doesn't list it; `move_item` covers reorder).
- ✅ All commit messages follow the codebase convention (`feat:` / `test:` / `chore:` prefixes; descriptive body).
