# pydantic-studio — Phase 3: Type Coverage Round 2 + Minimal CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the type registry to cover datetime / network / special types (13 new node classes), close 4 small Phase-2 follow-up gaps, and ship a minimal `pydantic-studio show <module:Class>` CLI for schema introspection.

**Architecture:** Same NodeBuilder + Registry pattern from Phase 2. Each new type family lives in its own module under `src/pydantic_studio/types/` (`temporal.py`, `network.py`, `special.py`). Nodes proliferate one per UI-shape category — consistent with Phase 2's choice of a class per primitive type rather than a unified TypedScalarNode. The CLI is a thin typer entry point that imports a user-supplied schema module and pretty-prints the resulting FormTree using rich.

**Tech Stack:** Python 3.11+, Pydantic v2 (≥2.7), typer (≥0.12) + rich (transitive via typer extras), `email-validator` as an optional dependency for `EmailStr` support.

**Scope note:** YAML I/O (load + smart write with comments) is intentionally *not* in this plan — it ships as Plan 4. The minimal CLI here can introspect a schema (`show`) but cannot read or write config files; that is acceptable because schema introspection is independently useful (debugging, schema-design feedback).

**Out-of-scope (deferred to v0.x):**
- TOML / JSON I/O writers (Plan 4 / Phase 6)
- Encrypted draft persistence for SecretStr (security-hardening pass; Plan 3 uses plaintext drafts and documents the caveat)
- `pydantic.NameEmail`, `pydantic.ByteSize`, DSN classes (Postgres/MySQL/etc.) — UrlNode + EmailNode cover the canonical cases; specialty subclasses can be added per-request later
- Full-blown `edit` / `check` / `render` CLI subcommands (Plan 4 once YAML lands)

---

## File Structure

**New files (8):**
- `src/pydantic_studio/types/temporal.py` — DatetimeBuilder, DateBuilder, TimeBuilder, TimedeltaBuilder
- `src/pydantic_studio/types/network.py` — IpAddressBuilder, IpNetworkBuilder, UrlBuilder, EmailBuilder
- `src/pydantic_studio/types/special.py` — PathBuilder, UuidBuilder, SecretBuilder, PatternBuilder, BytesBuilder
- `src/pydantic_studio/cli.py` — typer entry point (`pydantic-studio show`)
- `tests/unit/test_temporal.py` — coverage for the 4 temporal builders + nodes
- `tests/unit/test_network.py` — coverage for the 4 network builders + nodes
- `tests/unit/test_special.py` — coverage for the 5 special-type builders + nodes
- `tests/unit/test_cli.py` — CLI behavior under typer's CliRunner
- `tests/unit/test_starter_items.py` — regression tests for the 4 Phase-2 starter fixes

**Modified files:**
- `src/pydantic_studio/tree/nodes.py` — add 13 new node classes + extend AnyNode discriminated union + extend `set_value` to traverse sequence/mapping items (Phase-2 starter #4)
- `src/pydantic_studio/tree/builder.py` — register the 13 new builders
- `src/pydantic_studio/types/sequences.py` — `_build_items` isinstance guard (Phase-2 starter #3)
- `src/pydantic_studio/types/unions.py` — `model_validate` pre-select for BaseModel variants (Phase-2 starter #2)
- `src/pydantic_studio/__init__.py` — export the 13 new node names + ensure `cli` is importable
- `pyproject.toml` — add typer dep + `email-validator` optional extra + `pydantic-studio` console script
- `README.md` — Phase 3 example covering datetime/url/path/secret + CLI demo
- `tests/fixtures/schemas.py` — kitchen-sink schema extension (`Phase3Sink` covering all new types)

**Why split type families across three modules:** keeps each module under ~200 lines and matches the spec's `types/` layout (§ 6.1, line 125 of `2026-05-05-pydantic-studio-design.md`). Phase 2 grouped by behavior (primitives.py, choices.py, sequences.py, mapping.py); Plan 3 follows the same grain — temporal types share datetime-module imports, network types share ipaddress/Pydantic-network imports, special types are heterogeneous loners.

**Why typer + rich (not argparse + plain print):** the spec mandates typer (line 404 of the design doc — "CLI built with `typer` (already canonical in the pydantic ecosystem)"). Rich comes transitively via typer's `[all]` extra and gives us free Tree rendering for the FormTree.

---

## Branch Convention

Work happens on `feature/phase-3-type-coverage-round-2` branched from `master`. Each task commits its tests and implementation together (TDD discipline) and pushes to the feature branch. The final task merges to `master` with `--no-ff`.

User standing instruction: **commit and merge only — DO NOT push to origin.** Tag at the final feature commit before merging.

---

### Task 1: Branch setup + Phase-3 reference doc

**Files:**
- Modify: (no source files — git operations only)

- [ ] **Step 1: Create feature branch from master**

```bash
git checkout master
git status  # Expected: clean
git checkout -b feature/phase-3-type-coverage-round-2
```

Expected: Switched to a new branch.

- [ ] **Step 2: Verify Phase-2 baseline tests pass**

```bash
uv run pytest -q
```

Expected: 183 passed (Phase-2 ending count). If anything fails, stop and report — Plan 3 cannot start on a broken baseline.

- [ ] **Step 3: Verify ruff is clean**

```bash
uv run ruff check
```

Expected: `All checks passed!`

- [ ] **Step 4: Commit a no-op marker (optional — only if you want a branch-start commit)**

Skip this step. The first real commit will be Task 2.

---

### Task 2: Phase-2 starter fix #1 — hoist resolve calls above `_push_snapshot`

**Why:** In `add_item`, `insert_item`, `add_entry`, and `select_variant`, `_push_snapshot` is called *before* `_resolve_type_name(...)` — but resolve can raise (when the target module isn't in `sys.modules`). On failure, an unused snapshot has already been pushed, polluting undo history. `set_value` already does this correctly (validate first, then snapshot, then mutate); the four mutation methods should follow the same order.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py:688-708` (add_item), `nodes.py:726-754` (insert_item), `nodes.py:806-829` (add_entry), `nodes.py:925-954` (select_variant)
- Test: `tests/unit/test_starter_items.py` (NEW)

- [ ] **Step 1: Write failing tests for snapshot-ordering invariant**

Create `tests/unit/test_starter_items.py`:

```python
"""Regression tests for the four Phase-2 follow-up fixes shipped in Plan 3."""

from __future__ import annotations

import pytest

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import WithList, WithDict, WithUnion


class TestSnapshotOrderingHoist:
    """When resolve fails, no spurious snapshot should be pushed."""

    def test_add_item_with_unresolvable_item_type(self, monkeypatch) -> None:
        tree = build_form_tree(WithList)
        # Corrupt the SequenceNode's stored item-type name so resolve raises.
        tags = tree.root.find("tags")
        assert tags is not None
        tags.item_type_name = "nosuch.module.Type"

        snapshots_before = len(tree.snapshots)
        with pytest.raises(ValueError, match="not in sys.modules"):
            tree.add_item("tags", "x")
        assert len(tree.snapshots) == snapshots_before, (
            "snapshot pushed even though resolve raised — undo state is now polluted"
        )

    def test_insert_item_with_unresolvable_item_type(self) -> None:
        tree = build_form_tree(WithList)
        tags = tree.root.find("tags")
        assert tags is not None
        tags.item_type_name = "nosuch.module.Type"
        snapshots_before = len(tree.snapshots)
        with pytest.raises(ValueError, match="not in sys.modules"):
            tree.insert_item("tags", 0, "x")
        assert len(tree.snapshots) == snapshots_before

    def test_add_entry_with_unresolvable_key_type(self) -> None:
        tree = build_form_tree(WithDict)
        settings = tree.root.find("settings")
        assert settings is not None
        settings.key_type_name = "nosuch.module.Type"
        snapshots_before = len(tree.snapshots)
        with pytest.raises(ValueError, match="not in sys.modules"):
            tree.add_entry("settings", "k", 1)
        assert len(tree.snapshots) == snapshots_before

    def test_select_variant_with_unresolvable_variant(self) -> None:
        tree = build_form_tree(WithUnion)
        value_node = tree.root.find("value")
        assert value_node is not None
        # WithUnion is `int | str`, which is demoted to int via UnionBuilder
        # because Pydantic's smart-union narrows it. We need an actual
        # multi-variant union for this test — build one inline.
        from pydantic import BaseModel
        from tests.fixtures.schemas import Address

        class TwoVariants(BaseModel):
            v: Address | int = 0

        t2 = build_form_tree(TwoVariants)
        union = t2.root.find("v")
        assert union is not None
        # Corrupt the second variant so resolve raises.
        union.variant_type_names = [union.variant_type_names[0], "nosuch.module.Type"]
        snapshots_before = len(t2.snapshots)
        with pytest.raises(ValueError, match="not in sys.modules"):
            t2.select_variant("v", 1)
        assert len(t2.snapshots) == snapshots_before
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_starter_items.py::TestSnapshotOrderingHoist -v`

Expected: 4 FAIL — each assertion finds `len(tree.snapshots) == snapshots_before + 1` (snapshot was pushed before resolve raised).

- [ ] **Step 3: Hoist resolve calls in `add_item`**

In `src/pydantic_studio/tree/nodes.py`, modify `add_item` (around line 688). The current order is `_push_snapshot → _resolve_type_name → builder.find → builder.build`. New order: resolve+find+build first, snapshot only after they all succeed.

Replace the body of `add_item` (everything after `seq = self._walk_to_sequence(path)`) with:

```python
        seq = self._walk_to_sequence(path)
        if seq.origin == "tuple_fixed":
            return ValidationResult.fail(["cannot add to a fixed-length tuple"])
        if seq.item_type_name is None:
            return ValidationResult.fail(["sequence has no item_type_name"])
        # Resolve + build BEFORE snapshotting — failure here must not pollute
        # the undo history (mirrors the validate-first contract of set_value).
        item_type = _resolve_type_name(seq.item_type_name)
        builder = default_registry().find(item_type)
        child = builder.build(item_type, FieldInfo(annotation=item_type), value)
        child.name = str(len(seq.items))
        self._push_snapshot(_snap.take(self.root))
        seq.items = [*seq.items, child]
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()
```

- [ ] **Step 4: Hoist resolve calls in `insert_item`**

Same shape — find the lines that read:

```python
        self._push_snapshot(_snap.take(self.root))
        item_type = _resolve_type_name(seq.item_type_name)
        builder = default_registry().find(item_type)
        child = builder.build(item_type, FieldInfo(annotation=item_type), value)
```

and reorder so `_push_snapshot` runs *after* the build call:

```python
        item_type = _resolve_type_name(seq.item_type_name)
        builder = default_registry().find(item_type)
        child = builder.build(item_type, FieldInfo(annotation=item_type), value)
        self._push_snapshot(_snap.take(self.root))
```

- [ ] **Step 5: Hoist resolve calls in `add_entry`**

Find:

```python
        self._push_snapshot(_snap.take(self.root))
        key_type = _resolve_type_name(mp.key_type_name)
        value_type = _resolve_type_name(mp.value_type_name)
        reg = default_registry()
        k_builder = reg.find(key_type)
        v_builder = reg.find(value_type)
        k_node = k_builder.build(...)
        v_node = v_builder.build(...)
```

Reorder so the four resolve+build calls run before `_push_snapshot`:

```python
        key_type = _resolve_type_name(mp.key_type_name)
        value_type = _resolve_type_name(mp.value_type_name)
        reg = default_registry()
        k_builder = reg.find(key_type)
        v_builder = reg.find(value_type)
        k_node = k_builder.build(key_type, FieldInfo(annotation=key_type), key)
        v_node = v_builder.build(value_type, FieldInfo(annotation=value_type), value)
        k_node.name = "key"
        v_node.name = "value"
        self._push_snapshot(_snap.take(self.root))
        mp.entries = [*mp.entries, (k_node, v_node)]
```

- [ ] **Step 6: Hoist resolve calls in `select_variant`**

Find:

```python
        self._push_snapshot(_snap.take(self.root))
        v_type = _resolve_type_name(union.variant_type_names[variant_index])
        builder = default_registry().find(v_type)
        new_selected = builder.build(v_type, FieldInfo(annotation=v_type), seed)
```

Reorder:

```python
        v_type = _resolve_type_name(union.variant_type_names[variant_index])
        builder = default_registry().find(v_type)
        new_selected = builder.build(v_type, FieldInfo(annotation=v_type), seed)
        self._push_snapshot(_snap.take(self.root))
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_starter_items.py::TestSnapshotOrderingHoist -v`

Expected: 4 PASS.

- [ ] **Step 8: Run full test suite to verify no regressions**

Run: `uv run pytest -q`

Expected: 187 passed (183 baseline + 4 new). If any Phase-2 test fails, the hoist broke an invariant — investigate.

- [ ] **Step 9: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py tests/unit/test_starter_items.py
git commit -m "fix(tree): hoist resolve+build above _push_snapshot to keep undo history clean"
```

---

### Task 3: Phase-2 starter fix #2 — Union pre-select via `model_validate` for BaseModel variants

**Why:** `UnionBuilder.build` currently uses `isinstance(existing, v_type)` to pick a variant. For a union like `Address | int` with `existing={"street": "123 Elm", "city": "Springfield"}`, isinstance returns False (a dict isn't an Address) — the variant goes unselected even though Pydantic could `Address.model_validate(existing)` cleanly. Fix: when the variant is a BaseModel subclass and the simple isinstance check fails, attempt `model_validate` and pre-select on success.

**Files:**
- Modify: `src/pydantic_studio/types/unions.py:42-91` (the `existing` and `default` pre-select loops)
- Test: `tests/unit/test_starter_items.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_starter_items.py`:

```python
class TestUnionPreSelectViaModelValidate:
    """When a union has a BaseModel variant and existing is a dict that
    matches its schema, the variant should be pre-selected — not left blank."""

    def test_dict_matches_basemodel_variant(self) -> None:
        from pydantic import BaseModel
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import Address

        class HasUnion(BaseModel):
            target: Address | int = 0

        # Pass a dict that validly populates Address; UnionBuilder should
        # detect this via model_validate and pre-select the Address variant.
        tree = build_form_tree(HasUnion, existing={"target": {"street": "X", "city": "Y"}})
        union = tree.root.find("target")
        assert union is not None
        assert union.selected_index == 0, (
            f"expected Address variant (index 0) pre-selected, got {union.selected_index}"
        )
        assert union.selected is not None
        assert union.selected.kind == "group"

    def test_int_still_picks_int_variant(self) -> None:
        from pydantic import BaseModel
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import Address

        class HasUnion(BaseModel):
            target: Address | int = 0

        tree = build_form_tree(HasUnion, existing={"target": 42})
        union = tree.root.find("target")
        assert union is not None
        assert union.selected_index == 1, "expected int variant (index 1)"
        assert union.selected is not None
        assert union.selected.kind == "int"
        assert union.selected.value == 42
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_starter_items.py::TestUnionPreSelectViaModelValidate -v`

Expected: `test_dict_matches_basemodel_variant` FAILS (`union.selected_index is None` because dict isn't Address). `test_int_still_picks_int_variant` PASSES (regression baseline).

- [ ] **Step 3: Implement model_validate fallback in `unions.py`**

In `src/pydantic_studio/types/unions.py`, replace the existing pre-select loop with one that tries `model_validate` for BaseModel variants when isinstance fails. The full new `build` method:

```python
    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic import BaseModel
        from pydantic.fields import FieldInfo as _FI

        unwrapped = strip_annotated(type_)
        non_none_args = tuple(
            t for t in get_union_args(unwrapped) if t is not type(None)
        )

        # Optional[T] with a single non-None variant → just the inner builder
        # with required=False.
        if is_optional_type(unwrapped) and len(non_none_args) == 1:
            inner_type = non_none_args[0]
            inner_builder = self._registry.find(inner_type)
            inner = inner_builder.build(inner_type, field_info, existing)
            inner.required = False  # Optional implies not required
            return inner

        variants = list(non_none_args)
        selected_index, selected = self._preselect(variants, existing)

        if selected is None:
            default = field_info.get_default(call_default_factory=True)
            if default is PydanticUndefined:
                default = None
            if default is not None:
                selected_index, selected = self._preselect(variants, default)

        return UnionNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            variant_type_names=[_fq(v) for v in variants],
            selected_index=selected_index,
            selected=selected,
        )

    def _preselect(
        self, variants: list[Any], candidate: Any
    ) -> tuple[int | None, Any]:
        """Find the first variant that ``candidate`` belongs to.

        Strategy: isinstance first (fast path for already-built instances);
        for BaseModel variants where isinstance fails, try model_validate
        (covers dict→model coercion). Build the variant node on success.
        """
        from pydantic import BaseModel
        from pydantic.fields import FieldInfo as _FI

        if candidate is None:
            return None, None
        for i, v_type in enumerate(variants):
            try:
                if isinstance(candidate, v_type):
                    v_builder = self._registry.find(v_type)
                    selected = v_builder.build(
                        v_type, _FI(annotation=v_type), candidate
                    )
                    return i, selected
            except TypeError:
                # Some types (Annotated, generics) reject isinstance; skip.
                pass
            # Dict→BaseModel coercion: when isinstance fails for a BaseModel
            # variant, see whether Pydantic could validate the candidate.
            if isinstance(v_type, type) and issubclass(v_type, BaseModel):
                if isinstance(candidate, dict):
                    try:
                        v_type.model_validate(candidate)
                    except Exception:
                        continue
                    v_builder = self._registry.find(v_type)
                    selected = v_builder.build(
                        v_type, _FI(annotation=v_type), candidate
                    )
                    return i, selected
        return None, None
```

Note: the `from pydantic import BaseModel` and `from pydantic.fields import FieldInfo as _FI` imports stay inside the method to avoid the runtime/TYPE_CHECKING dance — they're cheap because the modules are already loaded.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_starter_items.py::TestUnionPreSelectViaModelValidate -v`

Expected: 2 PASS.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -q`

Expected: 189 passed (187 + 2 new).

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/types/unions.py tests/unit/test_starter_items.py
git commit -m "fix(unions): pre-select BaseModel variant via model_validate when isinstance fails"
```

---

### Task 4: Phase-2 starter fix #3 — `_build_items` isinstance guard

**Why:** `_build_items` in `sequences.py` iterates `existing` directly via `for i, v in enumerate(existing)`. If a caller passes a non-iterable (e.g., `existing=42`) or a string (which IS iterable but yields chars), the iteration produces garbage. Add an explicit isinstance guard that accepts `list`/`tuple`/`set`/`frozenset` (the canonical Python sequence container types) and rejects everything else with a clear error — including strings, since iterating a string into a list of chars is almost never intended.

**Files:**
- Modify: `src/pydantic_studio/types/sequences.py:22-44` (`_build_items` function)
- Test: `tests/unit/test_starter_items.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_starter_items.py`:

```python
class TestBuildItemsIsinstanceGuard:
    """`_build_items` should reject non-sequence existing values cleanly."""

    def test_string_existing_is_rejected(self) -> None:
        """A bare string is iterable but iterating yields chars — almost
        always a user mistake. Reject loudly."""
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import WithList

        with pytest.raises(TypeError, match="expected list/tuple/set"):
            build_form_tree(WithList, existing={"tags": "abc"})

    def test_int_existing_is_rejected(self) -> None:
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import WithList

        with pytest.raises(TypeError, match="expected list/tuple/set"):
            build_form_tree(WithList, existing={"tags": 42})

    def test_dict_existing_is_rejected(self) -> None:
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import WithList

        with pytest.raises(TypeError, match="expected list/tuple/set"):
            build_form_tree(WithList, existing={"tags": {"a": 1}})

    def test_list_existing_accepted(self) -> None:
        """Regression: valid input must still work after the guard lands."""
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import WithList

        tree = build_form_tree(WithList, existing={"tags": ["a", "b"]})
        tags = tree.root.find("tags")
        assert tags is not None
        assert len(tags.items) == 2

    def test_set_existing_accepted(self) -> None:
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import WithSet

        tree = build_form_tree(WithSet, existing={"flags": {"a", "b"}})
        flags = tree.root.find("flags")
        assert flags is not None
        assert len(flags.items) == 2
```

- [ ] **Step 2: Run tests to verify the rejection cases fail**

Run: `uv run pytest tests/unit/test_starter_items.py::TestBuildItemsIsinstanceGuard -v`

Expected: 3 FAIL (string/int/dict all silently produce bad children today). 2 PASS (list and set baselines work).

- [ ] **Step 3: Add isinstance guard in `_build_items`**

In `src/pydantic_studio/types/sequences.py`, modify `_build_items` (line 22) to validate the type of `existing` before iterating:

```python
def _build_items(
    registry: Registry,
    item_type: Any,
    existing: Any,
    parent_field_info: FieldInfo,
) -> list[Any]:
    """Build a child node for each value in ``existing``.

    Each child gets a synthetic FieldInfo carrying the item annotation —
    the parent's FieldInfo describes the *container*, not the items.
    """
    from pydantic.fields import FieldInfo

    if existing is None:
        return []
    if not isinstance(existing, (list, tuple, set, frozenset)):
        msg = (
            f"expected list/tuple/set for sequence value, got "
            f"{type(existing).__name__}"
        )
        raise TypeError(msg)
    item_finfo = FieldInfo(annotation=item_type)
    item_builder = registry.find(item_type)
    items: list[Any] = []
    for i, v in enumerate(existing):
        child = item_builder.build(item_type, item_finfo, v)
        child.name = str(i)
        items.append(child)
    return items
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_starter_items.py::TestBuildItemsIsinstanceGuard -v`

Expected: 5 PASS.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -q`

Expected: 194 passed (189 + 5 new).

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/types/sequences.py tests/unit/test_starter_items.py
git commit -m "fix(sequences): guard _build_items against non-sequence existing values"
```

---

### Task 5: Phase-2 starter fix #4 — implement item-level `set_value`

**Why:** `paths.py` documents `replicas[2]` and `database.replicas[2].host` syntax, but `FormTree.set_value` only walks GroupNode children (str segments). Calling `tree.set_value("tags[0]", "new")` raises `KeyError`. Either narrow the docs (cheap) or implement (useful). We implement because (a) renderers need item-level set_value to wire input fields per element, and (b) Plan 4's CLI `--set tags[0]=new` syntax depends on this.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` — `set_value` (line 608) extended for sequence/mapping traversal
- Test: `tests/unit/test_starter_items.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_starter_items.py`:

```python
class TestItemLevelSetValue:
    """set_value should accept paths into sequence items and mapping entries."""

    def test_set_list_item_by_index(self) -> None:
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import WithList

        tree = build_form_tree(WithList, existing={"tags": ["alpha", "beta"]})
        result = tree.set_value("tags[0]", "ALPHA")
        assert result.ok, f"expected ok, got errors {result.errors}"
        tags = tree.root.find("tags")
        assert tags is not None
        assert tags.items[0].value == "ALPHA"
        assert tags.items[1].value == "beta"

    def test_set_list_item_validation_failure_keeps_old_value(self) -> None:
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import WithList

        tree = build_form_tree(WithList, existing={"tags": ["alpha"]})
        result = tree.set_value("tags[0]", 123)  # int into string slot
        assert not result.ok
        tags = tree.root.find("tags")
        assert tags is not None
        assert tags.items[0].value == "alpha", "old value must survive failed set"

    def test_set_list_item_out_of_range(self) -> None:
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import WithList

        tree = build_form_tree(WithList, existing={"tags": ["x"]})
        with pytest.raises(KeyError, match="index 5"):
            tree.set_value("tags[5]", "y")

    def test_set_nested_list_item(self) -> None:
        from pydantic import BaseModel
        from pydantic_studio import build_form_tree

        class Server(BaseModel):
            host: str = "localhost"
            port: int = 8080

        class Cluster(BaseModel):
            replicas: list[Server] = []

        tree = build_form_tree(
            Cluster, existing={"replicas": [{"host": "h1"}, {"host": "h2"}]}
        )
        result = tree.set_value("replicas[1].host", "newhost")
        assert result.ok
        replicas = tree.root.find("replicas")
        assert replicas is not None
        # replicas[1] is a GroupNode; navigate to find its host child.
        server_1 = replicas.items[1]
        from pydantic_studio import GroupNode
        assert isinstance(server_1, GroupNode)
        host = server_1.find("host")
        assert host is not None
        assert host.value == "newhost"

    def test_set_mapping_value_by_key_index(self) -> None:
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import WithDict

        tree = build_form_tree(WithDict, existing={"settings": {"port": 80, "rps": 100}})
        # MappingNode entries use integer indices — entry [0] is ("port", 80),
        # [1] is ("rps", 100). set_value targets the value side.
        result = tree.set_value("settings[1]", 200)
        assert result.ok
        settings = tree.root.find("settings")
        assert settings is not None
        _k, v_node = settings.entries[1]
        assert v_node.value == 200

    def test_set_value_pushes_snapshot_for_undo(self) -> None:
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import WithList

        tree = build_form_tree(WithList, existing={"tags": ["a"]})
        snapshots_before = len(tree.snapshots)
        tree.set_value("tags[0]", "A")
        assert len(tree.snapshots) == snapshots_before + 1
        # Undo restores previous value.
        assert tree.undo()
        tags_after_undo = tree.root.find("tags")
        assert tags_after_undo is not None
        assert tags_after_undo.items[0].value == "a"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_starter_items.py::TestItemLevelSetValue -v`

Expected: 6 FAIL — most with `KeyError: cannot navigate segment 0 (not a group)` because `set_value` rejects int segments.

- [ ] **Step 3: Extend `set_value` to traverse sequence/mapping items**

In `src/pydantic_studio/tree/nodes.py`, replace the `set_value` method (line 608-662) with a version that handles all three node types during path traversal:

```python
    def set_value(self, path: str, value: Any) -> ValidationResult:
        """Set ``value`` at the given path; runs node-local validation.

        Path segments may be field names (str) — for navigating into
        GroupNode children — or integer indices — for SequenceNode items
        and MappingNode entries (where the index targets the *value* side
        of the (key, value) pair). The terminal segment identifies the
        node whose ``value`` field is mutated.

        On success: push a snapshot, write the value to the target node,
        clear ``target.error``, and return ``ValidationResult.ok()``.

        On failure: leave ``target.value`` untouched (so the FormTree's
        typed fields stay type-correct and snapshots remain serializable),
        record the first error message on ``target.error`` for renderer
        display, and return ``ValidationResult.fail(...)``. Note that
        ``target.error`` carries only the primary message; the full list
        of errors lives in the returned ``ValidationResult``.

        Cross-field validation runs at submit time (``to_instance``).
        """
        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.paths import Path as _Path

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            msg = "cannot set value on the root group itself"
            raise ValueError(msg)

        # Walk all but the last segment, pivoting on the current node's type.
        node: Any = self.root
        for seg in path_obj.segments[:-1]:
            node = self._descend(node, seg)

        # Resolve the terminal segment to a target node.
        last = path_obj.segments[-1]
        target = self._descend(node, last)

        errors = target.validate_value(value)
        if errors:
            target.error = errors[0]
            return ValidationResult.fail(list(errors))

        self._push_snapshot(_snap.take(self.root))
        target.value = value
        target.error = None
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def _descend(self, node: Any, seg: Any) -> Any:
        """Navigate one path segment into ``node``.

        Pivots on ``node``'s type:
        - GroupNode + str → child by name
        - SequenceNode + int → items[seg]
        - MappingNode + int → entries[seg][1] (the value node)

        Raises KeyError on any mismatch (out-of-range index, unknown name,
        or type/segment mismatch).
        """
        if isinstance(node, GroupNode) and isinstance(seg, str):
            child = node.find(seg)
            if child is None:
                msg = f"no field named {seg!r} at this level"
                raise KeyError(msg)
            return child
        if isinstance(node, SequenceNode) and isinstance(seg, int):
            if not (0 <= seg < len(node.items)):
                msg = f"index {seg} out of range for sequence of length {len(node.items)}"
                raise KeyError(msg)
            return node.items[seg]
        if isinstance(node, MappingNode) and isinstance(seg, int):
            if not (0 <= seg < len(node.entries)):
                msg = f"index {seg} out of range for mapping of length {len(node.entries)}"
                raise KeyError(msg)
            # Index into mapping selects the value side of the pair —
            # rename_key handles the key side via its dedicated mutation.
            return node.entries[seg][1]
        msg = (
            f"cannot navigate segment {seg!r} into {type(node).__name__} "
            f"(no rule for ({type(node).__name__}, {type(seg).__name__}))"
        )
        raise KeyError(msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_starter_items.py::TestItemLevelSetValue -v`

Expected: 6 PASS.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -q`

Expected: 200 passed (194 + 6 new).

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py tests/unit/test_starter_items.py
git commit -m "feat(tree): set_value traverses sequence items + mapping entries via index segments"
```

---

### Task 6: Datetime/Date/Time nodes + builders

**Why:** Datetime/date/time are ubiquitous in config (timestamps, scheduled dates, time-of-day cron-ish hints). Pydantic v2 round-trips them as ISO 8601 strings out of the box, so node fields can use the proper types directly.

**Design choice — three node classes (not one with a discriminator):** Each type has distinct UI semantics — datetime needs date+time pickers, date needs only date, time needs only time. Rendering code reads `node.kind` to dispatch to the right widget. Sharing a single class via discriminator would force every renderer to branch on `node.temporal_kind`, defeating the discriminated-union ergonomics Pydantic provides.

**Files:**
- Create: `src/pydantic_studio/types/temporal.py`
- Modify: `src/pydantic_studio/tree/nodes.py` — add DatetimeNode, DateNode, TimeNode + extend AnyNode
- Modify: `src/pydantic_studio/tree/builder.py` — register the three builders
- Test: `tests/unit/test_temporal.py` (NEW)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_temporal.py`:

```python
"""Tests for the temporal type family — datetime/date/time."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest
from pydantic import BaseModel

from pydantic_studio import (
    DatetimeNode,
    DateNode,
    TimeNode,
    build_form_tree,
)


class WithTemporal(BaseModel):
    when: datetime = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    on: date = date(2026, 1, 1)
    at: time = time(9, 30)


class TestDatetimeNode:
    def test_build_uses_datetime_node(self) -> None:
        tree = build_form_tree(WithTemporal)
        when = tree.root.find("when")
        assert isinstance(when, DatetimeNode)
        assert when.value == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def test_validate_accepts_datetime(self) -> None:
        node = DatetimeNode(name="x", value=None)
        assert node.validate_value(datetime(2026, 5, 6)) == ()

    def test_validate_rejects_str(self) -> None:
        """The renderer is responsible for parsing user input strings into
        datetime instances before calling set_value. Validation expects the
        already-parsed type."""
        node = DatetimeNode(name="x", value=None)
        errors = node.validate_value("2026-05-06T12:00:00")
        assert errors  # non-empty
        assert "expected datetime" in errors[0]

    def test_validate_rejects_date_and_time_subtypes(self) -> None:
        """date is not a datetime even though datetime IS a date subclass."""
        node = DatetimeNode(name="x", value=None)
        # date is the parent — pass a pure date and we should reject.
        errors = node.validate_value(date(2026, 5, 6))
        assert errors
        assert "expected datetime" in errors[0]

    def test_required_none_fails(self) -> None:
        node = DatetimeNode(name="x", required=True, value=None)
        errors = node.validate_value(None)
        assert errors == ("value is required",)

    def test_optional_none_ok(self) -> None:
        node = DatetimeNode(name="x", required=False, value=None)
        assert node.validate_value(None) == ()

    def test_to_python_returns_value(self) -> None:
        d = datetime(2026, 5, 6, 12, 0)
        node = DatetimeNode(name="x", value=d)
        assert node.to_python() == d

    def test_snapshot_round_trip(self) -> None:
        """Pydantic emits ISO strings + parses them back on validate."""
        node = DatetimeNode(name="x", value=datetime(2026, 5, 6, 12, 0, tzinfo=UTC))
        raw = node.model_dump_json()
        restored = DatetimeNode.model_validate_json(raw)
        assert restored.value == node.value


class TestDateNode:
    def test_build_uses_date_node(self) -> None:
        tree = build_form_tree(WithTemporal)
        on = tree.root.find("on")
        assert isinstance(on, DateNode)
        assert on.value == date(2026, 1, 1)

    def test_validate_accepts_date(self) -> None:
        node = DateNode(name="x", value=None)
        assert node.validate_value(date(2026, 5, 6)) == ()

    def test_validate_rejects_datetime(self) -> None:
        """A datetime is technically a date subclass in Python, but a date
        field cannot accept a datetime — the time component would be lost.
        Reject explicitly."""
        node = DateNode(name="x", value=None)
        errors = node.validate_value(datetime(2026, 5, 6))
        assert errors
        assert "expected date" in errors[0]

    def test_validate_rejects_str(self) -> None:
        node = DateNode(name="x", value=None)
        errors = node.validate_value("2026-05-06")
        assert errors

    def test_snapshot_round_trip(self) -> None:
        node = DateNode(name="x", value=date(2026, 5, 6))
        raw = node.model_dump_json()
        restored = DateNode.model_validate_json(raw)
        assert restored.value == node.value


class TestTimeNode:
    def test_build_uses_time_node(self) -> None:
        tree = build_form_tree(WithTemporal)
        at = tree.root.find("at")
        assert isinstance(at, TimeNode)
        assert at.value == time(9, 30)

    def test_validate_accepts_time(self) -> None:
        node = TimeNode(name="x", value=None)
        assert node.validate_value(time(12, 0)) == ()

    def test_validate_rejects_str(self) -> None:
        node = TimeNode(name="x", value=None)
        errors = node.validate_value("12:00:00")
        assert errors

    def test_snapshot_round_trip(self) -> None:
        node = TimeNode(name="x", value=time(12, 0, 30))
        raw = node.model_dump_json()
        restored = TimeNode.model_validate_json(raw)
        assert restored.value == node.value


class TestEndToEnd:
    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithTemporal)
        instance = tree.to_instance()
        assert isinstance(instance, WithTemporal)
        assert instance.when == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        assert instance.on == date(2026, 1, 1)
        assert instance.at == time(9, 30)

    def test_set_value_then_submit(self) -> None:
        tree = build_form_tree(WithTemporal)
        new_when = datetime(2027, 6, 15, 8, 0, tzinfo=UTC)
        result = tree.set_value("when", new_when)
        assert result.ok
        instance = tree.to_instance()
        assert instance.when == new_when
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_temporal.py -v`

Expected: ALL FAIL — `ImportError: cannot import name 'DatetimeNode' from 'pydantic_studio'`.

- [ ] **Step 3: Add the three node classes to `nodes.py`**

In `src/pydantic_studio/tree/nodes.py`, add the imports near the top (just below the existing `from datetime import datetime`):

```python
from datetime import date, datetime, time, timedelta
```

(Replacing the existing single-import line. `timedelta` is added now to support Task 7.)

Then add three new node classes (place them in the natural alphabetical/topical position — right after `DecimalNode`, before `EnumNode`):

```python
class DatetimeNode(FormNode):
    """Holds a timezone-aware-or-naive ``datetime.datetime`` value.

    Pydantic emits ISO 8601 strings on ``model_dump_json`` and parses them
    back on ``model_validate_json``, so no custom serializer is needed.
    """

    kind: Literal["datetime"] = "datetime"
    value: datetime | None = None
    default: datetime | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Reject date/time subclasses explicitly — datetime IS-A date in Python,
        # but a date field cannot take a datetime and vice versa. We need an
        # exact-type check.
        if type(value) is not datetime:
            return (f"expected datetime, got {type(value).__name__}",)
        return ()

    def to_python(self) -> datetime | None:
        return self.value


class DateNode(FormNode):
    """Holds a ``datetime.date`` value (no time component)."""

    kind: Literal["date"] = "date"
    value: date | None = None
    default: date | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if type(value) is not date:  # exact-type: rejects datetime subclass
            return (f"expected date, got {type(value).__name__}",)
        return ()

    def to_python(self) -> date | None:
        return self.value


class TimeNode(FormNode):
    """Holds a ``datetime.time`` value (no date component)."""

    kind: Literal["time"] = "time"
    value: time | None = None
    default: time | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if type(value) is not time:
            return (f"expected time, got {type(value).__name__}",)
        return ()

    def to_python(self) -> time | None:
        return self.value
```

Then extend the AnyNode discriminated union (line 532-545) by adding the three new node names:

```python
AnyNode = Annotated[
    StringNode
    | IntNode
    | FloatNode
    | BoolNode
    | DecimalNode
    | DatetimeNode
    | DateNode
    | TimeNode
    | EnumNode
    | LiteralNode
    | SequenceNode
    | MappingNode
    | UnionNode
    | GroupNode,
    Discriminator("kind"),
]
```

- [ ] **Step 4: Create `temporal.py` with three builders**

Create `src/pydantic_studio/types/temporal.py`:

```python
"""Builders for ``datetime``, ``date``, ``time`` annotations.

Pydantic round-trips these via ISO 8601 strings, so the builders only need
to detect the annotation and bind a default. ``TimedeltaBuilder`` is in
this module too (Task 7) — durations share the temporal-module imports.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import DateNode, DatetimeNode, TimeNode
from pydantic_studio.types.annotated import strip_annotated

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def _default(field_info: FieldInfo) -> Any:
    d = field_info.get_default(call_default_factory=True)
    return None if d is PydanticUndefined else d


class DatetimeBuilder:
    """Matches ``datetime.datetime`` annotations."""

    def matches(self, type_: type) -> bool:
        return strip_annotated(type_) is datetime

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> DatetimeNode:
        default = _default(field_info)
        return DatetimeNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )


class DateBuilder:
    """Matches ``datetime.date`` annotations.

    Note: this must come *after* DatetimeBuilder in the registry's match
    order if we ever check `issubclass(t, date)` — but ``strip_annotated(t)
    is date`` is identity-based, so order doesn't matter here.
    """

    def matches(self, type_: type) -> bool:
        return strip_annotated(type_) is date

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> DateNode:
        default = _default(field_info)
        return DateNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )


class TimeBuilder:
    """Matches ``datetime.time`` annotations."""

    def matches(self, type_: type) -> bool:
        return strip_annotated(type_) is time

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> TimeNode:
        default = _default(field_info)
        return TimeNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )
```

- [ ] **Step 5: Register the three builders in the default registry**

In `src/pydantic_studio/tree/builder.py`, add the imports near the top:

```python
from pydantic_studio.types.temporal import (
    DateBuilder,
    DatetimeBuilder,
    TimeBuilder,
)
```

Then in `default_registry()` (line 41), register the three builders right before the LiteralBuilder line. Order matters only when two builders could match the same type — datetime/date/time are mutually exclusive, so any position works:

```python
        reg.register(DatetimeBuilder())
        reg.register(DateBuilder())
        reg.register(TimeBuilder())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_temporal.py -v`

Expected: All tests pass (15-ish). If `test_validate_rejects_datetime` (DateNode) fails, double-check the `type(value) is not date` exact-type check is in place — `isinstance(value, date)` returns True for datetime instances and would pass through.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`

Expected: ~218 passed.

- [ ] **Step 8: Verify ruff is clean**

Run: `uv run ruff check`

Expected: All checks passed.

- [ ] **Step 9: Commit**

```bash
git add src/pydantic_studio/types/temporal.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py tests/unit/test_temporal.py
git commit -m "feat(types): DatetimeNode + DateNode + TimeNode + builders"
```

---

### Task 7: TimedeltaNode + TimedeltaBuilder

**Why:** Durations (retry intervals, timeouts, TTLs) are common in config. Pydantic accepts ISO 8601 duration strings (`PT1H30M`), seconds (as int/float), or `timedelta` instances; on dump it emits ISO 8601. Round-trip works free.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` — add TimedeltaNode + extend AnyNode
- Modify: `src/pydantic_studio/types/temporal.py` — add TimedeltaBuilder
- Modify: `src/pydantic_studio/tree/builder.py` — register
- Test: `tests/unit/test_temporal.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_temporal.py`:

```python
from datetime import timedelta

from pydantic_studio import TimedeltaNode


class WithTimedelta(BaseModel):
    interval: timedelta = timedelta(seconds=30)
    timeout: timedelta = timedelta(minutes=5)


class TestTimedeltaNode:
    def test_build_uses_timedelta_node(self) -> None:
        tree = build_form_tree(WithTimedelta)
        interval = tree.root.find("interval")
        assert isinstance(interval, TimedeltaNode)
        assert interval.value == timedelta(seconds=30)

    def test_validate_accepts_timedelta(self) -> None:
        node = TimedeltaNode(name="x", value=None)
        assert node.validate_value(timedelta(hours=1)) == ()

    def test_validate_rejects_int(self) -> None:
        """Pydantic accepts int as seconds during JSON parse, but at the
        validate_value level (post-renderer-coerce) we expect the actual
        type. The renderer converts `30` from a number input into
        timedelta(seconds=30) before calling set_value."""
        node = TimedeltaNode(name="x", value=None)
        errors = node.validate_value(30)
        assert errors
        assert "expected timedelta" in errors[0]

    def test_validate_rejects_str(self) -> None:
        node = TimedeltaNode(name="x", value=None)
        errors = node.validate_value("PT1H")
        assert errors

    def test_required_none_fails(self) -> None:
        node = TimedeltaNode(name="x", required=True, value=None)
        assert node.validate_value(None) == ("value is required",)

    def test_to_python_returns_value(self) -> None:
        d = timedelta(hours=2, minutes=30)
        node = TimedeltaNode(name="x", value=d)
        assert node.to_python() == d

    def test_snapshot_round_trip(self) -> None:
        node = TimedeltaNode(name="x", value=timedelta(hours=1, minutes=30))
        raw = node.model_dump_json()
        restored = TimedeltaNode.model_validate_json(raw)
        assert restored.value == node.value

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithTimedelta)
        result = tree.set_value("interval", timedelta(minutes=10))
        assert result.ok
        instance = tree.to_instance()
        assert instance.interval == timedelta(minutes=10)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_temporal.py::TestTimedeltaNode -v`

Expected: All FAIL — `ImportError: cannot import name 'TimedeltaNode'`.

- [ ] **Step 3: Add TimedeltaNode**

In `src/pydantic_studio/tree/nodes.py`, after `TimeNode`, add:

```python
class TimedeltaNode(FormNode):
    """Holds a ``datetime.timedelta`` value (a duration).

    Pydantic emits ISO 8601 duration strings (``PT1H30M``) on JSON dump
    and parses them back on load — round-trip works without a custom
    serializer.
    """

    kind: Literal["timedelta"] = "timedelta"
    value: timedelta | None = None
    default: timedelta | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, timedelta):
            return (f"expected timedelta, got {type(value).__name__}",)
        return ()

    def to_python(self) -> timedelta | None:
        return self.value
```

Extend the AnyNode union — add `| TimedeltaNode` after `| TimeNode`:

```python
    | TimeNode
    | TimedeltaNode
```

- [ ] **Step 4: Add TimedeltaBuilder to `temporal.py`**

In `src/pydantic_studio/types/temporal.py`, add the import and builder:

```python
from datetime import date, datetime, time, timedelta
```

(Replace the existing import line.)

Also add the import at the top:

```python
from pydantic_studio.tree.nodes import DateNode, DatetimeNode, TimedeltaNode, TimeNode
```

Then append the new builder class:

```python
class TimedeltaBuilder:
    """Matches ``datetime.timedelta`` annotations."""

    def matches(self, type_: type) -> bool:
        return strip_annotated(type_) is timedelta

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> TimedeltaNode:
        default = _default(field_info)
        return TimedeltaNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )
```

- [ ] **Step 5: Register TimedeltaBuilder**

In `src/pydantic_studio/tree/builder.py`, update the import:

```python
from pydantic_studio.types.temporal import (
    DateBuilder,
    DatetimeBuilder,
    TimedeltaBuilder,
    TimeBuilder,
)
```

And in `default_registry()`, after the three temporal registrations, add:

```python
        reg.register(TimedeltaBuilder())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_temporal.py::TestTimedeltaNode -v`

Expected: All 8 PASS.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`

Expected: ~226 passed.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/temporal.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py tests/unit/test_temporal.py
git commit -m "feat(types): TimedeltaNode + TimedeltaBuilder"
```

---

### Task 8: IpAddressNode + IpNetworkNode + builders

**Why:** IP addresses and networks are common in service configs (bind addresses, allowed CIDR ranges). Python's `ipaddress` module + Pydantic round-trip them as strings. We use a single node per category (address vs. network) with a `version` discriminator field — IPv4Address and IPv6Address render the same way in any UI (text input + format-aware validation).

**Design choice — store as `str | None`, not as `IPv4Address | IPv6Address | None`:** Pydantic's union handling for `IPv4Address | IPv6Address` is brittle (depends on Pydantic version); storing as a string and coercing via `ipaddress.ip_address(s)` at `to_python` time is robust and zero-cost. Validation calls `ipaddress.ip_address(value)` and catches `ValueError`.

**Files:**
- Create: `src/pydantic_studio/types/network.py`
- Modify: `src/pydantic_studio/tree/nodes.py` — add IpAddressNode, IpNetworkNode + extend AnyNode
- Modify: `src/pydantic_studio/tree/builder.py` — register builders
- Test: `tests/unit/test_network.py` (NEW)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_network.py`:

```python
"""Tests for the network type family — IP / URL / Email."""

from __future__ import annotations

from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
)

import pytest
from pydantic import BaseModel

from pydantic_studio import IpAddressNode, IpNetworkNode, build_form_tree


class WithIp(BaseModel):
    bind_v4: IPv4Address = IPv4Address("127.0.0.1")
    bind_v6: IPv6Address = IPv6Address("::1")
    allow_v4: IPv4Network = IPv4Network("10.0.0.0/8")
    allow_v6: IPv6Network = IPv6Network("fe80::/64")


class TestIpAddressNode:
    def test_build_v4_uses_ip_node_with_version_4(self) -> None:
        tree = build_form_tree(WithIp)
        bind = tree.root.find("bind_v4")
        assert isinstance(bind, IpAddressNode)
        assert bind.version == 4
        assert bind.value == "127.0.0.1"

    def test_build_v6_uses_ip_node_with_version_6(self) -> None:
        tree = build_form_tree(WithIp)
        bind = tree.root.find("bind_v6")
        assert isinstance(bind, IpAddressNode)
        assert bind.version == 6
        assert bind.value == "::1"

    def test_validate_accepts_string_form(self) -> None:
        node = IpAddressNode(name="x", version=4, value=None)
        assert node.validate_value("192.168.1.1") == ()

    def test_validate_accepts_ipvX_instance(self) -> None:
        node = IpAddressNode(name="x", version=4, value=None)
        assert node.validate_value(IPv4Address("192.168.1.1")) == ()

    def test_validate_rejects_wrong_version(self) -> None:
        node = IpAddressNode(name="x", version=4, value=None)
        errors = node.validate_value("::1")
        assert errors
        assert "expected IPv4" in errors[0]

    def test_validate_rejects_garbage(self) -> None:
        node = IpAddressNode(name="x", version=4, value=None)
        errors = node.validate_value("not.an.ip")
        assert errors
        assert "invalid" in errors[0].lower()

    def test_to_python_coerces_to_instance(self) -> None:
        node = IpAddressNode(name="x", version=4, value="10.0.0.1")
        assert node.to_python() == IPv4Address("10.0.0.1")

    def test_to_python_v6(self) -> None:
        node = IpAddressNode(name="x", version=6, value="2001:db8::1")
        assert node.to_python() == IPv6Address("2001:db8::1")

    def test_snapshot_round_trip(self) -> None:
        node = IpAddressNode(name="x", version=4, value="10.0.0.1")
        raw = node.model_dump_json()
        restored = IpAddressNode.model_validate_json(raw)
        assert restored.value == "10.0.0.1"
        assert restored.version == 4


class TestIpNetworkNode:
    def test_build_v4_network(self) -> None:
        tree = build_form_tree(WithIp)
        allow = tree.root.find("allow_v4")
        assert isinstance(allow, IpNetworkNode)
        assert allow.version == 4
        assert allow.value == "10.0.0.0/8"

    def test_build_v6_network(self) -> None:
        tree = build_form_tree(WithIp)
        allow = tree.root.find("allow_v6")
        assert isinstance(allow, IpNetworkNode)
        assert allow.version == 6
        assert allow.value == "fe80::/64"

    def test_validate_accepts_cidr(self) -> None:
        node = IpNetworkNode(name="x", version=4, value=None)
        assert node.validate_value("192.168.0.0/16") == ()

    def test_validate_rejects_address_without_prefix(self) -> None:
        """Pydantic's IPvX_Network treats `192.168.1.1` as a /32 — accept it."""
        node = IpNetworkNode(name="x", version=4, value=None)
        # ipaddress.IPv4Network accepts bare addresses (defaults to /32),
        # so this MUST validate as a network.
        assert node.validate_value("192.168.1.1") == ()

    def test_validate_rejects_garbage(self) -> None:
        node = IpNetworkNode(name="x", version=4, value=None)
        errors = node.validate_value("not.a.cidr")
        assert errors

    def test_to_python_coerces(self) -> None:
        node = IpNetworkNode(name="x", version=4, value="10.0.0.0/8")
        assert node.to_python() == IPv4Network("10.0.0.0/8")

    def test_snapshot_round_trip(self) -> None:
        node = IpNetworkNode(name="x", version=6, value="fe80::/64")
        raw = node.model_dump_json()
        restored = IpNetworkNode.model_validate_json(raw)
        assert restored.value == "fe80::/64"
        assert restored.version == 6


class TestEndToEnd:
    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithIp)
        instance = tree.to_instance()
        assert instance.bind_v4 == IPv4Address("127.0.0.1")
        assert instance.bind_v6 == IPv6Address("::1")
        assert instance.allow_v4 == IPv4Network("10.0.0.0/8")
        assert instance.allow_v6 == IPv6Network("fe80::/64")

    def test_set_value_via_string_round_trips(self) -> None:
        tree = build_form_tree(WithIp)
        result = tree.set_value("bind_v4", "192.168.1.1")
        assert result.ok
        instance = tree.to_instance()
        assert instance.bind_v4 == IPv4Address("192.168.1.1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_network.py -v`

Expected: All FAIL — `ImportError: cannot import name 'IpAddressNode'`.

- [ ] **Step 3: Add IpAddressNode and IpNetworkNode**

In `src/pydantic_studio/tree/nodes.py`, add the new node classes. Place them after `TimedeltaNode`:

```python
class IpAddressNode(FormNode):
    """Holds an IPv4 or IPv6 address as a string.

    The ``version`` field discriminates 4 vs 6 — set by the builder from
    the field annotation (IPv4Address vs IPv6Address). Stored as a string
    rather than the ``IPv4Address``/``IPv6Address`` instance because:

    1. Pydantic's union handling for the two address classes is brittle.
    2. Strings are JSON-friendly without custom serializers.
    3. ``to_python`` coerces back via ``ipaddress.ip_address`` for the
       schema's validate step.
    """

    kind: Literal["ip_address"] = "ip_address"
    value: str | None = None
    default: str | None = None
    version: Literal[4, 6]

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from ipaddress import (
            AddressValueError,
            IPv4Address,
            IPv6Address,
        )

        if value is None:
            return () if not self.required else ("value is required",)
        # Accept already-parsed instances of the right version.
        if self.version == 4 and isinstance(value, IPv4Address):
            return ()
        if self.version == 6 and isinstance(value, IPv6Address):
            return ()
        if isinstance(value, str):
            cls = IPv4Address if self.version == 4 else IPv6Address
            try:
                cls(value)
            except (AddressValueError, ValueError):
                return (f"invalid IPv{self.version} address: {value!r}",)
            return ()
        return (f"expected IPv{self.version} address, got {type(value).__name__}",)

    def to_python(self) -> Any:
        from ipaddress import IPv4Address, IPv6Address

        if self.value is None:
            return None
        cls = IPv4Address if self.version == 4 else IPv6Address
        return cls(self.value)


class IpNetworkNode(FormNode):
    """Holds an IPv4 or IPv6 network in CIDR form, as a string."""

    kind: Literal["ip_network"] = "ip_network"
    value: str | None = None
    default: str | None = None
    version: Literal[4, 6]

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from ipaddress import IPv4Network, IPv6Network

        if value is None:
            return () if not self.required else ("value is required",)
        if self.version == 4 and isinstance(value, IPv4Network):
            return ()
        if self.version == 6 and isinstance(value, IPv6Network):
            return ()
        if isinstance(value, str):
            cls = IPv4Network if self.version == 4 else IPv6Network
            try:
                cls(value, strict=False)
            except ValueError:
                return (f"invalid IPv{self.version} network: {value!r}",)
            return ()
        return (f"expected IPv{self.version} network, got {type(value).__name__}",)

    def to_python(self) -> Any:
        from ipaddress import IPv4Network, IPv6Network

        if self.value is None:
            return None
        cls = IPv4Network if self.version == 4 else IPv6Network
        return cls(self.value, strict=False)
```

Extend AnyNode by adding the two new node names:

```python
    | TimedeltaNode
    | IpAddressNode
    | IpNetworkNode
```

- [ ] **Step 4: Create `network.py` with builders**

Create `src/pydantic_studio/types/network.py`:

```python
"""Builders for IP / URL / Email annotations."""

from __future__ import annotations

from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
)
from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import IpAddressNode, IpNetworkNode
from pydantic_studio.types.annotated import strip_annotated

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def _default(field_info: FieldInfo) -> Any:
    d = field_info.get_default(call_default_factory=True)
    return None if d is PydanticUndefined else d


def _coerce_existing_to_str(existing: Any) -> str | None:
    """The IpXxxNode stores values as strings. Accept either an instance
    or a string from the caller."""
    if existing is None:
        return None
    if isinstance(existing, str):
        return existing
    return str(existing)


class IpAddressBuilder:
    """Matches ``ipaddress.IPv4Address`` and ``ipaddress.IPv6Address``."""

    def matches(self, type_: type) -> bool:
        unwrapped = strip_annotated(type_)
        return unwrapped is IPv4Address or unwrapped is IPv6Address

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> IpAddressNode:
        unwrapped = strip_annotated(type_)
        version: int = 4 if unwrapped is IPv4Address else 6
        default = _coerce_existing_to_str(_default(field_info))
        return IpAddressNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            version=version,
            value=_coerce_existing_to_str(existing) if existing is not None else default,
            default=default,
        )


class IpNetworkBuilder:
    """Matches ``ipaddress.IPv4Network`` and ``ipaddress.IPv6Network``."""

    def matches(self, type_: type) -> bool:
        unwrapped = strip_annotated(type_)
        return unwrapped is IPv4Network or unwrapped is IPv6Network

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> IpNetworkNode:
        unwrapped = strip_annotated(type_)
        version: int = 4 if unwrapped is IPv4Network else 6
        default = _coerce_existing_to_str(_default(field_info))
        return IpNetworkNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            version=version,
            value=_coerce_existing_to_str(existing) if existing is not None else default,
            default=default,
        )
```

- [ ] **Step 5: Register the two builders**

In `src/pydantic_studio/tree/builder.py`, add the import:

```python
from pydantic_studio.types.network import IpAddressBuilder, IpNetworkBuilder
```

And in `default_registry()`, after the temporal registrations, add:

```python
        reg.register(IpAddressBuilder())
        reg.register(IpNetworkBuilder())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_network.py -v`

Expected: All 18-ish tests PASS.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`

Expected: ~244 passed.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/network.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py tests/unit/test_network.py
git commit -m "feat(types): IpAddressNode + IpNetworkNode + builders for IPv4/IPv6"
```

---

### Task 9: UrlNode + UrlBuilder

**Why:** Pydantic exposes a family of URL classes (`AnyUrl`, `AnyHttpUrl`, `HttpUrl`, `FileUrl`, `WebsocketUrl`, plus DSN classes like `PostgresDsn`). They share a single UI shape (URL textbox), so one `UrlNode` keyed by the source type's FQ name covers them all.

**Design choice — store as `str | None`, recoerce via TypeAdapter at `to_python`:** Pydantic's URL types validate on construction. Storing the raw URL string and re-coercing through the original type at `to_python` time gives us correct round-trip semantics without the pain of finding a Pydantic-friendly union of all URL classes.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` — add UrlNode + extend AnyNode
- Modify: `src/pydantic_studio/types/network.py` — add UrlBuilder
- Modify: `src/pydantic_studio/tree/builder.py` — register
- Test: `tests/unit/test_network.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_network.py`:

```python
from pydantic import AnyHttpUrl, AnyUrl, FileUrl, HttpUrl
from pydantic_studio import UrlNode


class WithUrls(BaseModel):
    api: HttpUrl = HttpUrl("https://api.example.com/v1")
    fallback: AnyUrl = AnyUrl("ftp://files.example.com")
    asset: FileUrl = FileUrl("file:///srv/assets/logo.png")
    redirect: AnyHttpUrl = AnyHttpUrl("https://redirect.example.com")


class TestUrlNode:
    def test_build_uses_url_node(self) -> None:
        tree = build_form_tree(WithUrls)
        api = tree.root.find("api")
        assert isinstance(api, UrlNode)
        assert api.value == "https://api.example.com/v1"
        # The target_type_name records the original Pydantic type for
        # round-trip via TypeAdapter.
        assert "HttpUrl" in api.target_type_name

    def test_validate_accepts_string(self) -> None:
        node = UrlNode(name="x", value=None, target_type_name="pydantic.HttpUrl")
        assert node.validate_value("https://example.com") == ()

    def test_validate_rejects_garbage_string(self) -> None:
        node = UrlNode(name="x", value=None, target_type_name="pydantic.HttpUrl")
        errors = node.validate_value("not a url at all")
        assert errors

    def test_validate_rejects_non_string(self) -> None:
        node = UrlNode(name="x", value=None, target_type_name="pydantic.AnyUrl")
        errors = node.validate_value(42)
        assert errors
        assert "expected str" in errors[0]

    def test_to_python_coerces_via_target_type(self) -> None:
        from pydantic import HttpUrl

        node = UrlNode(
            name="x",
            value="https://example.com/",
            target_type_name=f"{HttpUrl.__module__}.HttpUrl",
        )
        result = node.to_python()
        # to_python returns whatever Pydantic's TypeAdapter produces — for
        # HttpUrl that's a Url instance.
        assert str(result).rstrip("/") == "https://example.com"

    def test_snapshot_round_trip(self) -> None:
        node = UrlNode(
            name="x",
            value="https://example.com",
            target_type_name="pydantic.HttpUrl",
        )
        raw = node.model_dump_json()
        restored = UrlNode.model_validate_json(raw)
        assert restored.value == node.value
        assert restored.target_type_name == node.target_type_name

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithUrls)
        instance = tree.to_instance()
        assert str(instance.api).startswith("https://api.example.com")

    def test_set_value_validates_url_format(self) -> None:
        tree = build_form_tree(WithUrls)
        result = tree.set_value("api", "not a url")
        assert not result.ok

    def test_set_value_accepts_valid_url(self) -> None:
        tree = build_form_tree(WithUrls)
        result = tree.set_value("api", "https://newapi.example.com/v2")
        assert result.ok
        instance = tree.to_instance()
        assert "newapi.example.com" in str(instance.api)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_network.py::TestUrlNode -v`

Expected: All FAIL — no UrlNode.

- [ ] **Step 3: Add UrlNode**

In `src/pydantic_studio/tree/nodes.py`, after `IpNetworkNode`, add:

```python
class UrlNode(FormNode):
    """Holds a URL as a string, with the original Pydantic URL type
    recorded in ``target_type_name`` for round-trip coercion.

    Covers ``AnyUrl``, ``AnyHttpUrl``, ``HttpUrl``, ``FileUrl``,
    ``WebsocketUrl``, and any other ``Annotated[Url, UrlConstraints(...)]``
    variant exposed by Pydantic. ``validate_value`` and ``to_python``
    delegate to a ``TypeAdapter`` built from ``target_type_name`` so
    each URL subtype's specific constraints (scheme set, default port,
    etc.) are enforced.
    """

    kind: Literal["url"] = "url"
    value: str | None = None
    default: str | None = None
    target_type_name: str  # e.g., "pydantic.HttpUrl"

    def _adapter(self) -> Any:
        """Build (and cache) a TypeAdapter for this URL's target type.

        Cached as an instance attribute via ``object.__setattr__`` to bypass
        Pydantic's own attribute machinery — TypeAdapters aren't Pydantic
        fields and shouldn't be model_dumped.
        """
        cached = getattr(self, "__url_adapter__", None)
        if cached is not None:
            return cached
        from pydantic import TypeAdapter

        target = _resolve_type_name(self.target_type_name)
        adapter = TypeAdapter(target)
        object.__setattr__(self, "__url_adapter__", adapter)
        return adapter

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from pydantic import ValidationError

        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, str):
            return (f"expected str URL, got {type(value).__name__}",)
        try:
            self._adapter().validate_python(value)
        except ValidationError as e:
            first = e.errors()[0]
            return (first.get("msg", "invalid URL"),)
        return ()

    def to_python(self) -> Any:
        if self.value is None:
            return None
        return self._adapter().validate_python(self.value)
```

Extend AnyNode:

```python
    | IpNetworkNode
    | UrlNode
```

- [ ] **Step 4: Add UrlBuilder to `network.py`**

Append to `src/pydantic_studio/types/network.py`:

```python
def _is_pydantic_url_type(type_: Any) -> bool:
    """Detect Pydantic's URL types.

    Pydantic v2 unifies URL classes via Annotated[Url, UrlConstraints(...)].
    The simplest detector is: strip Annotated, check whether the type's
    module is ``pydantic`` (or ``pydantic.networks``) AND its name ends in
    "Url" or is the bare ``Url`` class. This excludes our own ``UrlNode``
    (which lives in pydantic_studio.*) and handles the full URL family
    without enumerating every subclass.
    """
    unwrapped = strip_annotated(type_)
    if not isinstance(unwrapped, type):
        # Annotated[X, ...] strip returns a type — but PydanticUrl is
        # actually an Annotated alias. Look through one more level.
        from typing import get_args, get_origin

        origin = get_origin(unwrapped) or unwrapped
        if isinstance(origin, type):
            unwrapped = origin
        else:
            return False
    module = getattr(unwrapped, "__module__", "")
    if not (module == "pydantic" or module.startswith("pydantic.networks")):
        return False
    name = getattr(unwrapped, "__name__", "")
    return name == "Url" or name.endswith("Url")


class UrlBuilder:
    """Matches Pydantic's URL family (``AnyUrl``, ``HttpUrl``, etc.)."""

    def matches(self, type_: type) -> bool:
        return _is_pydantic_url_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic_studio.tree.nodes import UrlNode as _UrlNode

        unwrapped = strip_annotated(type_)
        # Resolve to the underlying URL class for the FQ name.
        from typing import get_origin

        url_cls = get_origin(unwrapped) or unwrapped
        target_type_name = f"{url_cls.__module__}.{url_cls.__name__}"
        default = _default(field_info)
        default_str = str(default) if default is not None else None
        existing_str = str(existing) if existing is not None else None
        return _UrlNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing_str if existing_str is not None else default_str,
            default=default_str,
            target_type_name=target_type_name,
        )
```

- [ ] **Step 5: Register UrlBuilder**

In `src/pydantic_studio/tree/builder.py`, update the import:

```python
from pydantic_studio.types.network import IpAddressBuilder, IpNetworkBuilder, UrlBuilder
```

And in `default_registry()`, add after IpNetworkBuilder:

```python
        reg.register(UrlBuilder())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_network.py::TestUrlNode -v`

Expected: All 9 PASS.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`

Expected: ~253 passed.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/network.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py tests/unit/test_network.py
git commit -m "feat(types): UrlNode + UrlBuilder covering AnyUrl/HttpUrl/FileUrl family"
```

---

### Task 10: EmailNode + EmailBuilder (with optional `email-validator` dep)

**Why:** `pydantic.EmailStr` is the canonical email field type. It requires the `email-validator` package as a runtime dependency — but only when the schema actually has an EmailStr field. We expose it via a separate optional extra so users who don't need email don't pay the install cost.

**Design choice — separate node class (not bolted onto UrlNode):** Email and URL are different formats; UI renders them with different keyboard hints (mobile email keyboard vs URL keyboard). Validation also differs (no scheme prefix). One node per format.

**Files:**
- Modify: `pyproject.toml` — add `email-validator` as an optional extra
- Modify: `src/pydantic_studio/tree/nodes.py` — add EmailNode + extend AnyNode
- Modify: `src/pydantic_studio/types/network.py` — add EmailBuilder
- Modify: `src/pydantic_studio/tree/builder.py` — register
- Test: `tests/unit/test_network.py` (extend)

- [ ] **Step 1: Add the optional dependency + dev-group entry**

Two edits to `pyproject.toml`:

1. Add a `[project.optional-dependencies]` block (just below the `dependencies` block) so library users can opt in:

```toml
[project.optional-dependencies]
email = ["email-validator>=2"]
```

2. Also add `email-validator` to the `dev` dependency group so the test suite always has it. Modify the existing `[dependency-groups]` block:

```toml
[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "pytest-cov",
  "email-validator>=2",
]
```

**Why both:** the optional extra is for library consumers who want EmailStr support without being forced to install `email-validator`. The dev-group entry guarantees that *our* tests always have it — without it, a later `uv sync` (without `--extra email`) would strip the package and break `tests/fixtures/schemas.py` at import time.

- [ ] **Step 2: Install the updated deps**

Run: `uv sync`

Expected: email-validator is installed (via the dev group).

- [ ] **Step 3: Write failing tests**

Append to `tests/unit/test_network.py`:

```python
from pydantic import EmailStr
from pydantic_studio import EmailNode


class WithEmail(BaseModel):
    contact: EmailStr = "ops@example.com"
    fallback: EmailStr | None = None


class TestEmailNode:
    def test_build_uses_email_node(self) -> None:
        tree = build_form_tree(WithEmail)
        contact = tree.root.find("contact")
        assert isinstance(contact, EmailNode)
        assert contact.value == "ops@example.com"

    def test_validate_accepts_well_formed_email(self) -> None:
        node = EmailNode(name="x", value=None)
        assert node.validate_value("user@example.com") == ()

    def test_validate_rejects_no_at_sign(self) -> None:
        node = EmailNode(name="x", value=None)
        errors = node.validate_value("not-an-email")
        assert errors

    def test_validate_rejects_non_string(self) -> None:
        node = EmailNode(name="x", value=None)
        errors = node.validate_value(123)
        assert errors
        assert "expected str" in errors[0]

    def test_required_none_fails(self) -> None:
        node = EmailNode(name="x", required=True, value=None)
        assert node.validate_value(None) == ("value is required",)

    def test_optional_none_ok(self) -> None:
        tree = build_form_tree(WithEmail)
        fallback = tree.root.find("fallback")
        assert isinstance(fallback, EmailNode)
        assert fallback.required is False
        assert fallback.value is None

    def test_to_python_returns_string(self) -> None:
        node = EmailNode(name="x", value="user@example.com")
        assert node.to_python() == "user@example.com"

    def test_snapshot_round_trip(self) -> None:
        node = EmailNode(name="x", value="ops@example.com")
        raw = node.model_dump_json()
        restored = EmailNode.model_validate_json(raw)
        assert restored.value == node.value

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithEmail)
        instance = tree.to_instance()
        assert instance.contact == "ops@example.com"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_network.py::TestEmailNode -v`

Expected: All FAIL — no EmailNode.

- [ ] **Step 5: Add EmailNode**

In `src/pydantic_studio/tree/nodes.py`, after `UrlNode`:

```python
class EmailNode(FormNode):
    """Holds an email address as a string, validated via Pydantic's
    ``EmailStr`` (which depends on ``email-validator``).
    """

    kind: Literal["email"] = "email"
    value: str | None = None
    default: str | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, str):
            return (f"expected str email, got {type(value).__name__}",)
        # Lazy import: email-validator is an optional dep; if missing, fall
        # back to a permissive '@'-presence check so EmailNode still works
        # in environments that haven't installed the extra.
        try:
            from email_validator import EmailNotValidError, validate_email
        except ImportError:
            if "@" not in value or value.startswith("@") or value.endswith("@"):
                return (f"invalid email: {value!r}",)
            return ()
        try:
            validate_email(value, check_deliverability=False)
        except EmailNotValidError as e:
            return (str(e),)
        return ()

    def to_python(self) -> str | None:
        return self.value
```

Extend AnyNode:

```python
    | UrlNode
    | EmailNode
```

- [ ] **Step 6: Add EmailBuilder to `network.py`**

Append to `src/pydantic_studio/types/network.py`:

```python
def _is_email_str(type_: Any) -> bool:
    """Detect ``pydantic.EmailStr`` regardless of how it was annotated.

    EmailStr in Pydantic v2 is ``Annotated[str, ...]`` with a marker; the
    simplest detection is name + module check after stripping Annotated.
    """
    unwrapped = strip_annotated(type_)
    name = getattr(unwrapped, "__name__", "")
    module = getattr(unwrapped, "__module__", "")
    return name == "EmailStr" and module.startswith("pydantic")


class EmailBuilder:
    """Matches ``pydantic.EmailStr``."""

    def matches(self, type_: type) -> bool:
        return _is_email_str(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic_studio.tree.nodes import EmailNode as _EmailNode

        default = _default(field_info)
        return _EmailNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )
```

- [ ] **Step 7: Register EmailBuilder**

In `src/pydantic_studio/tree/builder.py`, update the import:

```python
from pydantic_studio.types.network import (
    EmailBuilder,
    IpAddressBuilder,
    IpNetworkBuilder,
    UrlBuilder,
)
```

And in `default_registry()`, add after UrlBuilder:

```python
        reg.register(EmailBuilder())
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_network.py::TestEmailNode -v`

Expected: All 9 PASS. (Tests assume `email-validator` is installed via Step 2; a CI matrix test for the no-extra path is left for v0.x.)

- [ ] **Step 9: Run full test suite**

Run: `uv run pytest -q`

Expected: ~262 passed.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml src/pydantic_studio/types/network.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py tests/unit/test_network.py
git commit -m "feat(types): EmailNode + EmailBuilder with optional email-validator dep"
```

---

### Task 11: PathNode + PathBuilder

**Why:** `pathlib.Path` is the standard way to represent filesystem paths in Pydantic schemas. We store the path as a string for cross-OS round-trip safety (a `Path("/etc/x")` saved on Linux and loaded on Windows would otherwise become a `WindowsPath`, breaking equality).

**Files:**
- Create: `src/pydantic_studio/types/special.py`
- Modify: `src/pydantic_studio/tree/nodes.py` — add PathNode + extend AnyNode
- Modify: `src/pydantic_studio/tree/builder.py` — register
- Test: `tests/unit/test_special.py` (NEW)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_special.py`:

```python
"""Tests for the special-types family — Path, UUID, SecretStr, Pattern, bytes."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from pydantic_studio import PathNode, build_form_tree


class WithPath(BaseModel):
    home: Path = Path("/home/user")
    workdir: Path = Path("/tmp/work")


class TestPathNode:
    def test_build_uses_path_node(self) -> None:
        tree = build_form_tree(WithPath)
        home = tree.root.find("home")
        assert isinstance(home, PathNode)
        # Stored as a string for cross-OS portability.
        assert home.value == str(Path("/home/user"))

    def test_validate_accepts_string(self) -> None:
        node = PathNode(name="x", value=None)
        assert node.validate_value("/etc/config.yaml") == ()

    def test_validate_accepts_path_instance(self) -> None:
        node = PathNode(name="x", value=None)
        assert node.validate_value(Path("/etc/config.yaml")) == ()

    def test_validate_rejects_non_path(self) -> None:
        node = PathNode(name="x", value=None)
        errors = node.validate_value(42)
        assert errors
        assert "expected str or Path" in errors[0]

    def test_required_none_fails(self) -> None:
        node = PathNode(name="x", required=True, value=None)
        assert node.validate_value(None) == ("value is required",)

    def test_to_python_coerces_to_path(self) -> None:
        node = PathNode(name="x", value="/etc/config.yaml")
        result = node.to_python()
        assert isinstance(result, Path)
        assert str(result) == str(Path("/etc/config.yaml"))

    def test_snapshot_round_trip(self) -> None:
        node = PathNode(name="x", value="/var/log/app.log")
        raw = node.model_dump_json()
        restored = PathNode.model_validate_json(raw)
        assert restored.value == node.value

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithPath)
        instance = tree.to_instance()
        assert instance.home == Path("/home/user")

    def test_set_value_with_string(self) -> None:
        tree = build_form_tree(WithPath)
        result = tree.set_value("home", "/new/home")
        assert result.ok
        instance = tree.to_instance()
        assert instance.home == Path("/new/home")

    def test_set_value_with_path_instance(self) -> None:
        tree = build_form_tree(WithPath)
        result = tree.set_value("home", Path("/another/home"))
        assert result.ok
        # PathNode stores as string regardless of input form.
        home = tree.root.find("home")
        assert isinstance(home.value, str)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_special.py::TestPathNode -v`

Expected: All FAIL — no PathNode.

- [ ] **Step 3: Add PathNode**

In `src/pydantic_studio/tree/nodes.py`, add the PathNode class (after `EmailNode`):

```python
class PathNode(FormNode):
    """Holds a filesystem path as a string.

    Stored as a string (not a ``Path`` instance) so JSON round-trip is
    OS-portable — `Path("/etc/x")` becomes `WindowsPath` on Windows, which
    breaks equality on round-trip across platforms. ``set_value`` accepts
    either a string or a ``Path`` instance and normalizes to ``str``.
    """

    kind: Literal["path"] = "path"
    value: str | None = None
    default: str | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from pathlib import PurePath

        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, (str, PurePath)):
            return (f"expected str or Path, got {type(value).__name__}",)
        return ()

    def to_python(self) -> Any:
        from pathlib import Path as _Path

        if self.value is None:
            return None
        return _Path(self.value)
```

Extend AnyNode:

```python
    | EmailNode
    | PathNode
```

Also: in `set_value`, the target node's `target.value = value` line (after validation) needs to coerce `Path → str` for PathNode. Since PathNode inherits the default `set_value` flow, we handle this via an override hook.

The cleanest fix is to override `value` *normalization* in PathNode by adding a small helper. Update PathNode with a normalization step on assignment. We do this via a `field_validator` mode='before':

```python
    @field_validator("value", "default", mode="before")
    @classmethod
    def _normalize_path(cls, v: Any) -> Any:
        from pathlib import PurePath

        if isinstance(v, PurePath):
            return str(v)
        return v
```

Add this method to the PathNode class body.

Note: this means `set_value("home", Path("/x"))` → validate succeeds (Path is allowed), then `target.value = Path("/x")` triggers Pydantic's value validator which converts to str. The test `test_set_value_with_path_instance` exercises this.

- [ ] **Step 4: Create `special.py` with PathBuilder**

Create `src/pydantic_studio/types/special.py`:

```python
"""Builders for ``pathlib.Path``, ``uuid.UUID``, ``pydantic.SecretStr``,
``re.Pattern``, and ``bytes`` annotations.
"""

from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import PathNode
from pydantic_studio.types.annotated import strip_annotated

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def _default(field_info: FieldInfo) -> Any:
    d = field_info.get_default(call_default_factory=True)
    return None if d is PydanticUndefined else d


def _path_to_str(value: Any) -> Any:
    """Coerce a Path/PurePath to its string form; pass everything else through."""
    if isinstance(value, PurePath):
        return str(value)
    return value


class PathBuilder:
    """Matches any ``pathlib.PurePath`` subclass (Path, PurePosixPath, etc.)."""

    def matches(self, type_: type) -> bool:
        unwrapped = strip_annotated(type_)
        if not isinstance(unwrapped, type):
            return False
        return issubclass(unwrapped, PurePath)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic_studio.tree.nodes import PathNode as _PathNode

        default = _path_to_str(_default(field_info))
        existing_v = _path_to_str(existing)
        return _PathNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing_v if existing_v is not None else default,
            default=default,
        )
```

- [ ] **Step 5: Register PathBuilder**

In `src/pydantic_studio/tree/builder.py`, add:

```python
from pydantic_studio.types.special import PathBuilder
```

And in `default_registry()`, after EmailBuilder:

```python
        reg.register(PathBuilder())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_special.py::TestPathNode -v`

Expected: All 10 PASS.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`

Expected: ~272 passed.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/special.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py tests/unit/test_special.py
git commit -m "feat(types): PathNode + PathBuilder for pathlib.Path"
```

---

### Task 12: UuidNode + UuidBuilder

**Why:** `uuid.UUID` is common for IDs in service config. Pydantic round-trips UUIDs as strings in JSON, so we can use the proper field type directly.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` — add UuidNode + extend AnyNode
- Modify: `src/pydantic_studio/types/special.py` — add UuidBuilder
- Modify: `src/pydantic_studio/tree/builder.py` — register
- Test: `tests/unit/test_special.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_special.py`:

```python
from uuid import UUID, uuid4
from pydantic_studio import UuidNode


class WithUuid(BaseModel):
    request_id: UUID = UUID("00000000-0000-0000-0000-000000000000")
    session_id: UUID = UUID("11111111-1111-1111-1111-111111111111")


class TestUuidNode:
    def test_build_uses_uuid_node(self) -> None:
        tree = build_form_tree(WithUuid)
        rid = tree.root.find("request_id")
        assert isinstance(rid, UuidNode)
        assert rid.value == UUID("00000000-0000-0000-0000-000000000000")

    def test_validate_accepts_uuid(self) -> None:
        node = UuidNode(name="x", value=None)
        assert node.validate_value(uuid4()) == ()

    def test_validate_rejects_string(self) -> None:
        """The renderer parses user-input strings into UUIDs before
        calling set_value. validate_value expects already-parsed UUIDs."""
        node = UuidNode(name="x", value=None)
        errors = node.validate_value("00000000-0000-0000-0000-000000000000")
        assert errors
        assert "expected UUID" in errors[0]

    def test_required_none_fails(self) -> None:
        node = UuidNode(name="x", required=True, value=None)
        assert node.validate_value(None) == ("value is required",)

    def test_to_python_returns_uuid(self) -> None:
        u = uuid4()
        node = UuidNode(name="x", value=u)
        assert node.to_python() == u

    def test_snapshot_round_trip(self) -> None:
        u = uuid4()
        node = UuidNode(name="x", value=u)
        raw = node.model_dump_json()
        restored = UuidNode.model_validate_json(raw)
        assert restored.value == u

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithUuid)
        instance = tree.to_instance()
        assert instance.request_id == UUID("00000000-0000-0000-0000-000000000000")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_special.py::TestUuidNode -v`

Expected: All FAIL — no UuidNode.

- [ ] **Step 3: Add UuidNode**

In `src/pydantic_studio/tree/nodes.py`:

```python
from uuid import UUID
```

(Add to the existing imports near the top.)

After `PathNode`, add:

```python
class UuidNode(FormNode):
    """Holds a ``uuid.UUID`` value.

    Pydantic round-trips UUIDs as strings via JSON, so the proper field
    type works directly with no custom serializer.
    """

    kind: Literal["uuid"] = "uuid"
    value: UUID | None = None
    default: UUID | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, UUID):
            return (f"expected UUID, got {type(value).__name__}",)
        return ()

    def to_python(self) -> UUID | None:
        return self.value
```

Extend AnyNode:

```python
    | PathNode
    | UuidNode
```

- [ ] **Step 4: Add UuidBuilder to `special.py`**

Append to `src/pydantic_studio/types/special.py`:

```python
def _is_uuid_type(type_: Any) -> bool:
    from uuid import UUID

    unwrapped = strip_annotated(type_)
    return unwrapped is UUID


class UuidBuilder:
    """Matches ``uuid.UUID``."""

    def matches(self, type_: type) -> bool:
        return _is_uuid_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic_studio.tree.nodes import UuidNode as _UuidNode

        default = _default(field_info)
        return _UuidNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )
```

- [ ] **Step 5: Register UuidBuilder**

In `src/pydantic_studio/tree/builder.py`:

```python
from pydantic_studio.types.special import PathBuilder, UuidBuilder
```

And register:

```python
        reg.register(UuidBuilder())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_special.py::TestUuidNode -v`

Expected: All 7 PASS.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`

Expected: ~279 passed.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/special.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py tests/unit/test_special.py
git commit -m "feat(types): UuidNode + UuidBuilder for uuid.UUID"
```

---

### Task 13: SecretNode + SecretBuilder (SecretStr / SecretBytes)

**Why:** `pydantic.SecretStr` and `pydantic.SecretBytes` mark sensitive fields. UI needs to render them masked (e.g., `••••••••`). The renderer can read `node.kind == "secret"` to switch widgets.

**Security caveat (documented in docstring):** `SecretNode` stores the secret value in plaintext both in the in-memory snapshot ring AND in `draft_save` JSON on disk. This is a known v0.0.3 limitation; v0.x will add encrypted draft persistence and/or exclude secrets from on-disk drafts.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` — add SecretNode + extend AnyNode
- Modify: `src/pydantic_studio/types/special.py` — add SecretBuilder
- Modify: `src/pydantic_studio/tree/builder.py` — register
- Test: `tests/unit/test_special.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_special.py`:

```python
from pydantic import SecretBytes, SecretStr
from pydantic_studio import SecretNode


class WithSecret(BaseModel):
    api_key: SecretStr = SecretStr("default-key")
    token: SecretBytes = SecretBytes(b"default-token")


class TestSecretNode:
    def test_build_str_uses_secret_node_kind_str(self) -> None:
        tree = build_form_tree(WithSecret)
        api = tree.root.find("api_key")
        assert isinstance(api, SecretNode)
        assert api.secret_kind == "str"
        assert api.value == "default-key"

    def test_build_bytes_uses_secret_node_kind_bytes(self) -> None:
        tree = build_form_tree(WithSecret)
        token = tree.root.find("token")
        assert isinstance(token, SecretNode)
        assert token.secret_kind == "bytes"
        assert token.value == b"default-token"

    def test_validate_str_accepts_string(self) -> None:
        node = SecretNode(name="x", secret_kind="str", value=None)
        assert node.validate_value("password") == ()

    def test_validate_str_rejects_bytes(self) -> None:
        node = SecretNode(name="x", secret_kind="str", value=None)
        errors = node.validate_value(b"password")
        assert errors

    def test_validate_bytes_accepts_bytes(self) -> None:
        node = SecretNode(name="x", secret_kind="bytes", value=None)
        assert node.validate_value(b"token") == ()

    def test_validate_bytes_rejects_str(self) -> None:
        node = SecretNode(name="x", secret_kind="bytes", value=None)
        errors = node.validate_value("token")
        assert errors

    def test_to_python_str_wraps_secret(self) -> None:
        node = SecretNode(name="x", secret_kind="str", value="password")
        result = node.to_python()
        assert isinstance(result, SecretStr)
        assert result.get_secret_value() == "password"

    def test_to_python_bytes_wraps_secret(self) -> None:
        node = SecretNode(name="x", secret_kind="bytes", value=b"token")
        result = node.to_python()
        assert isinstance(result, SecretBytes)
        assert result.get_secret_value() == b"token"

    def test_snapshot_round_trip_str(self) -> None:
        node = SecretNode(name="x", secret_kind="str", value="password")
        raw = node.model_dump_json()
        restored = SecretNode.model_validate_json(raw)
        assert restored.value == "password"
        assert restored.secret_kind == "str"

    def test_snapshot_round_trip_bytes(self) -> None:
        """Pydantic encodes bytes as base64 in JSON; round-trip recovers them."""
        node = SecretNode(name="x", secret_kind="bytes", value=b"token")
        raw = node.model_dump_json()
        restored = SecretNode.model_validate_json(raw)
        assert restored.value == b"token"
        assert restored.secret_kind == "bytes"

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithSecret)
        instance = tree.to_instance()
        assert instance.api_key.get_secret_value() == "default-key"
        assert instance.token.get_secret_value() == b"default-token"

    def test_set_value_replaces_secret(self) -> None:
        tree = build_form_tree(WithSecret)
        result = tree.set_value("api_key", "new-secret")
        assert result.ok
        instance = tree.to_instance()
        assert instance.api_key.get_secret_value() == "new-secret"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_special.py::TestSecretNode -v`

Expected: All FAIL.

- [ ] **Step 3: Add SecretNode**

In `src/pydantic_studio/tree/nodes.py`, after `UuidNode`:

```python
class SecretNode(FormNode):
    """Holds the plaintext value of a ``pydantic.SecretStr`` or
    ``pydantic.SecretBytes`` field.

    The ``secret_kind`` field discriminates str vs bytes so renderers can
    pick the correct widget. ``to_python`` wraps the stored value in the
    appropriate Pydantic Secret type so model validation passes.

    Security caveat: in v0.0.3, secret values are stored in plaintext in
    snapshots (in-memory) and in ``draft_save`` JSON (on disk). Don't use
    drafts on shared storage for sensitive deployments. v0.x will offer
    encrypted drafts or a "skip secrets in drafts" mode.
    """

    kind: Literal["secret"] = "secret"
    value: str | bytes | None = None
    default: str | bytes | None = None
    secret_kind: Literal["str", "bytes"]

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if self.secret_kind == "str" and not isinstance(value, str):
            return (f"expected str (SecretStr value), got {type(value).__name__}",)
        if self.secret_kind == "bytes" and not isinstance(value, (bytes, bytearray)):
            return (f"expected bytes (SecretBytes value), got {type(value).__name__}",)
        return ()

    def to_python(self) -> Any:
        from pydantic import SecretBytes, SecretStr

        if self.value is None:
            return None
        if self.secret_kind == "str":
            return SecretStr(self.value)
        return SecretBytes(self.value)
```

Extend AnyNode:

```python
    | UuidNode
    | SecretNode
```

- [ ] **Step 4: Add SecretBuilder to `special.py`**

Append to `src/pydantic_studio/types/special.py`:

```python
def _secret_kind(type_: Any) -> str | None:
    """Detect SecretStr / SecretBytes; return ``"str"``, ``"bytes"``, or None."""
    unwrapped = strip_annotated(type_)
    name = getattr(unwrapped, "__name__", "")
    module = getattr(unwrapped, "__module__", "")
    if not module.startswith("pydantic"):
        return None
    if name == "SecretStr":
        return "str"
    if name == "SecretBytes":
        return "bytes"
    return None


def _coerce_secret_existing(existing: Any) -> Any:
    """Unwrap a SecretStr/SecretBytes instance into its raw value, leaving
    str/bytes/None unchanged. The build path receives both forms because
    callers can pass either a Pydantic Secret instance (round-trip) or a
    raw string (programmatic seed)."""
    from pydantic import SecretBytes, SecretStr

    if isinstance(existing, (SecretStr, SecretBytes)):
        return existing.get_secret_value()
    return existing


class SecretBuilder:
    """Matches ``pydantic.SecretStr`` and ``pydantic.SecretBytes``."""

    def matches(self, type_: type) -> bool:
        return _secret_kind(type_) is not None

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic_studio.tree.nodes import SecretNode as _SecretNode

        kind = _secret_kind(type_)
        # _secret_kind returned non-None (matches() checked) — narrow the type.
        assert kind is not None
        default = _coerce_secret_existing(_default(field_info))
        existing_v = _coerce_secret_existing(existing)
        return _SecretNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            secret_kind=kind,  # type: ignore[arg-type]
            value=existing_v if existing_v is not None else default,
            default=default,
        )
```

- [ ] **Step 5: Register SecretBuilder**

In `src/pydantic_studio/tree/builder.py`:

```python
from pydantic_studio.types.special import PathBuilder, SecretBuilder, UuidBuilder
```

And register:

```python
        reg.register(SecretBuilder())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_special.py::TestSecretNode -v`

Expected: All 12 PASS.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`

Expected: ~291 passed.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/special.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py tests/unit/test_special.py
git commit -m "feat(types): SecretNode + SecretBuilder for SecretStr/SecretBytes (with security note)"
```

---

### Task 14: PatternNode + PatternBuilder

**Why:** `re.Pattern` fields are common for input-validation regex sources in config. We store the pattern source as a string + the flags as an int; `to_python` recompiles via `re.compile(source, flags)`.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` — add PatternNode + extend AnyNode
- Modify: `src/pydantic_studio/types/special.py` — add PatternBuilder
- Modify: `src/pydantic_studio/tree/builder.py` — register
- Test: `tests/unit/test_special.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_special.py`:

```python
import re
from pydantic_studio import PatternNode


class WithPattern(BaseModel):
    name_re: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9_]*$")
    flag_re: re.Pattern[str] = re.compile(r"hello", re.IGNORECASE)


class TestPatternNode:
    def test_build_uses_pattern_node(self) -> None:
        tree = build_form_tree(WithPattern)
        name_re = tree.root.find("name_re")
        assert isinstance(name_re, PatternNode)
        assert name_re.value == r"^[a-z][a-z0-9_]*$"
        assert name_re.flags == 0

    def test_build_preserves_flags(self) -> None:
        tree = build_form_tree(WithPattern)
        flag_re = tree.root.find("flag_re")
        assert isinstance(flag_re, PatternNode)
        assert flag_re.flags & re.IGNORECASE

    def test_validate_accepts_string(self) -> None:
        node = PatternNode(name="x", value=None)
        assert node.validate_value(r"^abc$") == ()

    def test_validate_rejects_invalid_regex(self) -> None:
        node = PatternNode(name="x", value=None)
        errors = node.validate_value(r"[unclosed")
        assert errors
        assert "regex" in errors[0].lower()

    def test_validate_rejects_non_string(self) -> None:
        node = PatternNode(name="x", value=None)
        errors = node.validate_value(42)
        assert errors

    def test_to_python_compiles(self) -> None:
        node = PatternNode(name="x", value=r"^[a-z]+$", flags=0)
        result = node.to_python()
        assert isinstance(result, re.Pattern)
        assert result.match("abc")
        assert not result.match("ABC")

    def test_to_python_applies_flags(self) -> None:
        node = PatternNode(name="x", value=r"hello", flags=re.IGNORECASE)
        result = node.to_python()
        assert result.match("HELLO")

    def test_snapshot_round_trip(self) -> None:
        node = PatternNode(name="x", value=r"^foo$", flags=re.IGNORECASE)
        raw = node.model_dump_json()
        restored = PatternNode.model_validate_json(raw)
        assert restored.value == r"^foo$"
        assert restored.flags == re.IGNORECASE

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithPattern)
        instance = tree.to_instance()
        assert instance.name_re.match("hello")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_special.py::TestPatternNode -v`

Expected: All FAIL.

- [ ] **Step 3: Add PatternNode**

In `src/pydantic_studio/tree/nodes.py`, after `SecretNode`:

```python
class PatternNode(FormNode):
    """Holds a regex pattern as its source string + flags.

    ``to_python`` recompiles via ``re.compile(value, flags)``.
    """

    kind: Literal["pattern"] = "pattern"
    value: str | None = None
    default: str | None = None
    flags: int = 0

    def validate_value(self, value: Any) -> tuple[str, ...]:
        import re as _re

        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, str):
            return (f"expected regex source string, got {type(value).__name__}",)
        try:
            _re.compile(value, self.flags)
        except _re.error as e:
            return (f"invalid regex: {e}",)
        return ()

    def to_python(self) -> Any:
        import re as _re

        if self.value is None:
            return None
        return _re.compile(self.value, self.flags)
```

Extend AnyNode:

```python
    | SecretNode
    | PatternNode
```

- [ ] **Step 4: Add PatternBuilder to `special.py`**

Append to `src/pydantic_studio/types/special.py`:

```python
def _is_pattern_type(type_: Any) -> bool:
    """Detect ``re.Pattern[str]`` and bare ``re.Pattern``.

    ``re.Pattern[str]`` is ``Pattern`` with a generic arg; ``get_origin``
    on it returns ``re.Pattern``. Bare ``re.Pattern`` has no origin —
    handle both.
    """
    import re
    from typing import get_origin

    unwrapped = strip_annotated(type_)
    return get_origin(unwrapped) is re.Pattern or unwrapped is re.Pattern


class PatternBuilder:
    """Matches ``re.Pattern`` and ``re.Pattern[str]``."""

    def matches(self, type_: type) -> bool:
        return _is_pattern_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        import re

        from pydantic_studio.tree.nodes import PatternNode as _PatternNode

        default = _default(field_info)
        # Normalize compiled-Pattern values to source + flags.
        if isinstance(default, re.Pattern):
            default_src: str | None = default.pattern
            default_flags = int(default.flags)
        else:
            default_src = default if isinstance(default, str) else None
            default_flags = 0
        if isinstance(existing, re.Pattern):
            existing_src: str | None = existing.pattern
            existing_flags: int = int(existing.flags)
        elif isinstance(existing, str):
            existing_src = existing
            existing_flags = default_flags
        else:
            existing_src = None
            existing_flags = default_flags
        return _PatternNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing_src if existing_src is not None else default_src,
            default=default_src,
            flags=existing_flags,
        )
```

- [ ] **Step 5: Register PatternBuilder**

```python
from pydantic_studio.types.special import (
    PathBuilder,
    PatternBuilder,
    SecretBuilder,
    UuidBuilder,
)
```

And register:

```python
        reg.register(PatternBuilder())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_special.py::TestPatternNode -v`

Expected: All 9 PASS.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`

Expected: ~300 passed.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/special.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py tests/unit/test_special.py
git commit -m "feat(types): PatternNode + PatternBuilder for re.Pattern with flag preservation"
```

---

### Task 15: BytesNode + BytesBuilder

**Why:** `bytes` fields appear in config when binary tokens or pre-shared keys are involved. Pydantic JSON-encodes bytes as base64 by default; the proper field type round-trips for free.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` — add BytesNode + extend AnyNode
- Modify: `src/pydantic_studio/types/special.py` — add BytesBuilder
- Modify: `src/pydantic_studio/tree/builder.py` — register
- Test: `tests/unit/test_special.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_special.py`:

```python
from pydantic_studio import BytesNode


class WithBytes(BaseModel):
    blob: bytes = b"\x00\x01\x02"
    nonce: bytes = b""


class TestBytesNode:
    def test_build_uses_bytes_node(self) -> None:
        tree = build_form_tree(WithBytes)
        blob = tree.root.find("blob")
        assert isinstance(blob, BytesNode)
        assert blob.value == b"\x00\x01\x02"

    def test_validate_accepts_bytes(self) -> None:
        node = BytesNode(name="x", value=None)
        assert node.validate_value(b"data") == ()

    def test_validate_accepts_bytearray(self) -> None:
        node = BytesNode(name="x", value=None)
        assert node.validate_value(bytearray(b"data")) == ()

    def test_validate_rejects_str(self) -> None:
        node = BytesNode(name="x", value=None)
        errors = node.validate_value("data")
        assert errors

    def test_to_python_returns_bytes(self) -> None:
        node = BytesNode(name="x", value=b"hello")
        assert node.to_python() == b"hello"

    def test_snapshot_round_trip(self) -> None:
        """Pydantic emits bytes as base64 in JSON; round-trip recovers them."""
        node = BytesNode(name="x", value=b"\x00\xff\x80")
        raw = node.model_dump_json()
        restored = BytesNode.model_validate_json(raw)
        assert restored.value == node.value

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithBytes)
        instance = tree.to_instance()
        assert instance.blob == b"\x00\x01\x02"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_special.py::TestBytesNode -v`

Expected: All FAIL.

- [ ] **Step 3: Add BytesNode**

In `src/pydantic_studio/tree/nodes.py`, after `PatternNode`:

```python
class BytesNode(FormNode):
    """Holds a ``bytes`` value (Pydantic JSON-encodes as base64)."""

    kind: Literal["bytes"] = "bytes"
    value: bytes | None = None
    default: bytes | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, (bytes, bytearray)):
            return (f"expected bytes, got {type(value).__name__}",)
        return ()

    def to_python(self) -> bytes | None:
        if self.value is None:
            return None
        return bytes(self.value)
```

Extend AnyNode (this is the last new node — verify the union now has all 24 entries):

```python
    | PatternNode
    | BytesNode
```

After this, the full AnyNode declaration should look like:

```python
AnyNode = Annotated[
    StringNode
    | IntNode
    | FloatNode
    | BoolNode
    | DecimalNode
    | DatetimeNode
    | DateNode
    | TimeNode
    | TimedeltaNode
    | IpAddressNode
    | IpNetworkNode
    | UrlNode
    | EmailNode
    | PathNode
    | UuidNode
    | SecretNode
    | PatternNode
    | BytesNode
    | EnumNode
    | LiteralNode
    | SequenceNode
    | MappingNode
    | UnionNode
    | GroupNode,
    Discriminator("kind"),
]
```

- [ ] **Step 4: Add BytesBuilder to `special.py`**

Append:

```python
class BytesBuilder:
    """Matches plain ``bytes``."""

    def matches(self, type_: type) -> bool:
        return strip_annotated(type_) is bytes

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic_studio.tree.nodes import BytesNode as _BytesNode

        default = _default(field_info)
        return _BytesNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )
```

- [ ] **Step 5: Register BytesBuilder**

```python
from pydantic_studio.types.special import (
    BytesBuilder,
    PathBuilder,
    PatternBuilder,
    SecretBuilder,
    UuidBuilder,
)
```

And register:

```python
        reg.register(BytesBuilder())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_special.py::TestBytesNode -v`

Expected: All 7 PASS.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`

Expected: ~307 passed.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/special.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py tests/unit/test_special.py
git commit -m "feat(types): BytesNode + BytesBuilder for bytes (base64 JSON round-trip)"
```

---

### Task 16: Update public API exports

**Why:** All 13 new node classes need to be importable from `pydantic_studio` directly so users can `from pydantic_studio import DatetimeNode` without reaching into internal modules.

**Files:**
- Modify: `src/pydantic_studio/__init__.py`
- Modify: `src/pydantic_studio/tree/nodes.py` — verify `model_rebuild()` is called on every container node that references AnyNode

- [ ] **Step 1: Confirm model_rebuild calls cover all forward refs**

Open `src/pydantic_studio/tree/nodes.py` and verify the bottom of the file. After all the new node classes were added, the existing model_rebuild block should still work because the new node classes don't have forward refs to AnyNode themselves (they're leaf nodes). However, the existing GroupNode/SequenceNode/MappingNode/UnionNode rebuilds need to re-run after the union has been re-defined with the new variants.

The existing block at line ~550:

```python
GroupNode.model_rebuild()
SequenceNode.model_rebuild()
MappingNode.model_rebuild()
UnionNode.model_rebuild()
```

Already covers what we need. The order matters — these rebuilds run AFTER the AnyNode definition.

- [ ] **Step 2: Update `__init__.py` to export the new node classes**

Replace the import-and-export block in `src/pydantic_studio/__init__.py`:

```python
from pydantic_studio.tree.nodes import (
    BoolNode,
    BytesNode,
    DateNode,
    DatetimeNode,
    DecimalNode,
    EmailNode,
    EnumNode,
    FloatNode,
    FormNode,
    FormTree,
    GroupNode,
    IntNode,
    IpAddressNode,
    IpNetworkNode,
    LiteralNode,
    MappingNode,
    PathNode,
    PatternNode,
    SecretNode,
    SequenceNode,
    StringNode,
    TimeNode,
    TimedeltaNode,
    UnionNode,
    UrlNode,
    UuidNode,
)
```

And update the `__all__` list (alphabetized to match Phase 2's convention):

```python
__all__ = [
    "BoolNode",
    "BytesNode",
    "CancelledByUser",
    "DateNode",
    "DatetimeNode",
    "DecimalNode",
    "EmailNode",
    "EnumNode",
    "FloatNode",
    "FormNode",
    "FormTree",
    "GroupNode",
    "IntNode",
    "IpAddressNode",
    "IpNetworkNode",
    "LiteralNode",
    "MappingNode",
    "NoBuilderError",
    "NodeBuilder",
    "PathNode",
    "PatternNode",
    "PydanticStudioError",
    "Registry",
    "SecretNode",
    "SequenceNode",
    "StringNode",
    "TimeNode",
    "TimedeltaNode",
    "UnionNode",
    "UrlNode",
    "UuidNode",
    "ValidationFailedError",
    "ValidationResult",
    "__version__",
    "build_form_tree",
    "register_builder",
    "reset_default_registry",
]
```

- [ ] **Step 3: Write a sanity test for public API surface**

Append to `tests/unit/test_special.py`:

```python
class TestPublicApi:
    """Smoke check: every new node class is importable from pydantic_studio."""

    def test_imports(self) -> None:
        from pydantic_studio import (
            BytesNode,
            DateNode,
            DatetimeNode,
            EmailNode,
            IpAddressNode,
            IpNetworkNode,
            PathNode,
            PatternNode,
            SecretNode,
            TimeNode,
            TimedeltaNode,
            UrlNode,
            UuidNode,
        )
        # Confirm they're all subclasses of FormNode.
        from pydantic_studio import FormNode

        for cls in (
            BytesNode, DateNode, DatetimeNode, EmailNode,
            IpAddressNode, IpNetworkNode, PathNode, PatternNode,
            SecretNode, TimeNode, TimedeltaNode, UrlNode, UuidNode,
        ):
            assert issubclass(cls, FormNode), cls.__name__
```

- [ ] **Step 4: Run the sanity test**

Run: `uv run pytest tests/unit/test_special.py::TestPublicApi -v`

Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -q`

Expected: ~308 passed (307 + 1 new).

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/__init__.py tests/unit/test_special.py
git commit -m "feat(api): export 13 new node classes from pydantic_studio"
```

---

### Task 17: Kitchen-sink schema extension + smoke test

**Why:** Phase 2 introduced a kitchen-sink test that exercised one field of each type. Plan 3 adds 13 new types — extend the kitchen-sink to exercise them end-to-end (build_form_tree → to_instance round-trip with default values), plus a "set_value on each field" smoke pass.

**Files:**
- Modify: `tests/fixtures/schemas.py` — add `Phase3Sink`
- Modify: `tests/unit/test_smoke.py` — extend coverage

- [ ] **Step 1: Add `Phase3Sink` schema to fixtures**

Append to `tests/fixtures/schemas.py`:

```python
from datetime import date, datetime, time, timedelta
from ipaddress import IPv4Address, IPv6Network
from pathlib import Path
from re import Pattern, compile as re_compile
from uuid import UUID

from pydantic import (
    EmailStr,
    HttpUrl,
    SecretBytes,
    SecretStr,
)


class Phase3Sink(BaseModel):
    """Kitchen-sink schema covering every Plan 3 type. Defaults exercise
    the build path; Phase-3 smoke tests mutate one field at a time and
    confirm round-trip through ``to_instance``."""

    # Temporal
    when: datetime = datetime(2026, 5, 6, 12, 0)
    on: date = date(2026, 5, 6)
    at: time = time(9, 30)
    interval: timedelta = timedelta(seconds=30)

    # Network
    bind: IPv4Address = IPv4Address("127.0.0.1")
    allow: IPv6Network = IPv6Network("fe80::/64")
    api: HttpUrl = HttpUrl("https://api.example.com")
    contact: EmailStr = "ops@example.com"

    # Special
    home: Path = Path("/home/user")
    request_id: UUID = UUID("00000000-0000-0000-0000-000000000000")
    api_key: SecretStr = SecretStr("default-key")
    token: SecretBytes = SecretBytes(b"default-token")
    name_re: Pattern[str] = re_compile(r"^[a-z]+$")
    blob: bytes = b"\x00\x01\x02"
```

- [ ] **Step 2: Add a smoke test that exercises the kitchen-sink**

Append a new test class to `tests/unit/test_smoke.py` (or create the file if it doesn't already include Phase 3 sections; check Phase-2 work first):

```python
class TestPhase3Sink:
    """End-to-end smoke for the 13 new Plan 3 type families."""

    def test_build_succeeds_for_all_phase3_types(self) -> None:
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import Phase3Sink

        tree = build_form_tree(Phase3Sink)
        # Confirm all 14 fields rendered as nodes.
        assert len(tree.root.fields) == 14

    def test_to_instance_round_trip_with_defaults(self) -> None:
        from datetime import date, datetime, time, timedelta
        from ipaddress import IPv4Address, IPv6Network
        from pathlib import Path
        from uuid import UUID

        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import Phase3Sink

        tree = build_form_tree(Phase3Sink)
        instance = tree.to_instance()
        assert instance.when == datetime(2026, 5, 6, 12, 0)
        assert instance.on == date(2026, 5, 6)
        assert instance.at == time(9, 30)
        assert instance.interval == timedelta(seconds=30)
        assert instance.bind == IPv4Address("127.0.0.1")
        assert instance.allow == IPv6Network("fe80::/64")
        assert "api.example.com" in str(instance.api)
        assert instance.contact == "ops@example.com"
        assert instance.home == Path("/home/user")
        assert instance.request_id == UUID(int=0)
        assert instance.api_key.get_secret_value() == "default-key"
        assert instance.token.get_secret_value() == b"default-token"
        assert instance.name_re.pattern == r"^[a-z]+$"
        assert instance.blob == b"\x00\x01\x02"

    def test_set_value_each_field(self) -> None:
        """One set_value per node type — proves the validate-first contract
        works for every new node."""
        from datetime import date, datetime, time, timedelta
        from ipaddress import IPv4Address, IPv6Network
        from pathlib import Path
        from re import IGNORECASE
        from uuid import UUID, uuid4

        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import Phase3Sink

        tree = build_form_tree(Phase3Sink)
        new_uuid = uuid4()
        mutations = [
            ("when", datetime(2027, 1, 1, 12, 0)),
            ("on", date(2027, 1, 1)),
            ("at", time(15, 45)),
            ("interval", timedelta(minutes=10)),
            ("bind", "192.168.1.1"),
            ("allow", "2001:db8::/32"),
            ("api", "https://newapi.example.com"),
            ("contact", "new@example.com"),
            ("home", "/srv/data"),
            ("request_id", new_uuid),
            ("api_key", "new-secret"),
            ("token", b"new-token"),
            ("name_re", r"^[A-Z]+$"),
            ("blob", b"\xff\xfe"),
        ]
        for path, value in mutations:
            result = tree.set_value(path, value)
            assert result.ok, f"set_value({path!r}, {value!r}) failed: {result.errors}"

        instance = tree.to_instance()
        assert instance.when == datetime(2027, 1, 1, 12, 0)
        assert instance.bind == IPv4Address("192.168.1.1")
        assert instance.contact == "new@example.com"
        assert instance.api_key.get_secret_value() == "new-secret"
        assert instance.token.get_secret_value() == b"new-token"

    def test_snapshot_round_trip(self) -> None:
        """Full FormTree.model_dump_json + model_validate_json round-trip
        must preserve every node type."""
        from pydantic_studio import build_form_tree
        from pydantic_studio.tree.nodes import FormTree
        from tests.fixtures.schemas import Phase3Sink

        tree = build_form_tree(Phase3Sink)
        raw = tree.model_dump_json(exclude={"schema_class"})
        restored = FormTree.model_validate_json(
            raw, context={"schema_class": Phase3Sink}
        )
        # The restored tree must be able to materialize the same instance.
        original_instance = tree.to_instance()
        restored_instance = restored.to_instance()
        assert original_instance == restored_instance
```

- [ ] **Step 3: Run the smoke test**

Run: `uv run pytest tests/unit/test_smoke.py::TestPhase3Sink -v`

Expected: All 4 PASS.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -q`

Expected: ~312 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/schemas.py tests/unit/test_smoke.py
git commit -m "test: Phase3Sink kitchen-sink schema + end-to-end smoke for 13 new types"
```

---

### Task 18: CLI MVP — `pydantic-studio show <module:Class>`

**Why:** Schema introspection is the smallest useful CLI subcommand that doesn't depend on YAML I/O (Plan 4). Engineers point the CLI at any Pydantic schema and see the FormTree structure pretty-printed — useful for schema-design feedback and for debugging custom NodeBuilder implementations.

**Design:** typer-based, single `show` subcommand. Accepts `module:Class` syntax (matching the spec's CLI conventions). Imports the module, looks up the class, runs `build_form_tree`, then walks the tree to a `rich.tree.Tree` for printing.

**Files:**
- Modify: `pyproject.toml` — add `typer[all]` (which brings rich) + console_scripts entry point
- Create: `src/pydantic_studio/cli.py`
- Create: `tests/unit/test_cli.py`

- [ ] **Step 1: Add typer dependency + console script**

In `pyproject.toml`, modify the `dependencies` block to include typer:

```toml
dependencies = [
  "pydantic>=2.7",
  "typer>=0.12",
  "rich>=13",
]
```

(typer's `[all]` extra would also work but we list explicit deps for transparency.)

Add a console script entry point. After the `[project]` block, add:

```toml
[project.scripts]
pydantic-studio = "pydantic_studio.cli:app"
```

- [ ] **Step 2: Sync deps**

Run: `uv sync`

Expected: typer + rich installed.

- [ ] **Step 3: Write failing tests**

Create `tests/unit/test_cli.py`:

```python
"""Tests for the minimal `pydantic-studio show` CLI."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from pydantic_studio.cli import app

runner = CliRunner()


class TestShow:
    def test_show_renders_simple_schema(self) -> None:
        result = runner.invoke(app, ["show", "tests.fixtures.schemas:Simple"])
        assert result.exit_code == 0
        # Field names must appear somewhere in the rich-rendered output.
        assert "name" in result.output
        assert "age" in result.output
        assert "balance" in result.output

    def test_show_renders_temporal_fields(self) -> None:
        result = runner.invoke(app, ["show", "tests.fixtures.schemas:Phase3Sink"])
        assert result.exit_code == 0
        assert "when" in result.output
        assert "datetime" in result.output  # node kind appears

    def test_show_unknown_module(self) -> None:
        result = runner.invoke(app, ["show", "nosuch.module:Foo"])
        assert result.exit_code != 0
        assert "could not import" in result.output.lower()

    def test_show_unknown_class(self) -> None:
        result = runner.invoke(app, ["show", "tests.fixtures.schemas:Nonexistent"])
        assert result.exit_code != 0
        assert "no such class" in result.output.lower()

    def test_show_not_a_basemodel(self) -> None:
        # Use the built-in `int` to trigger the "not a BaseModel" error path.
        result = runner.invoke(app, ["show", "builtins:int"])
        assert result.exit_code != 0
        assert "basemodel" in result.output.lower()

    def test_show_invalid_format(self) -> None:
        """Bare names without 'module:Class' are rejected."""
        result = runner.invoke(app, ["show", "no_colon_here"])
        assert result.exit_code != 0
        assert "module:class" in result.output.lower()
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_cli.py -v`

Expected: All FAIL — `pydantic_studio.cli` does not exist.

- [ ] **Step 5: Create the CLI module**

Create `src/pydantic_studio/cli.py`:

```python
"""Minimal CLI for pydantic-studio.

v0.0.3 ships only the ``show`` subcommand — schema introspection without
any I/O dependencies. ``edit`` / ``check`` / ``render`` join in Plan 4
once YAML round-trip support lands.
"""

from __future__ import annotations

import importlib
from typing import Any

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.tree import Tree

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import (
    AnyNode,
    GroupNode,
    MappingNode,
    SequenceNode,
    UnionNode,
)

app = typer.Typer(
    name="pydantic-studio",
    help="Interactive editor for Pydantic models. Run `pydantic-studio show` "
    "to introspect a schema's form-tree shape.",
    no_args_is_help=True,
)


def _load_schema(target: str) -> type[BaseModel]:
    """Resolve ``module:Class`` → BaseModel subclass.

    Raises typer.Exit with a friendly diagnostic on any failure.
    """
    if ":" not in target:
        typer.secho(
            f"Invalid target {target!r}: expected 'module:Class' format.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    module_name, class_name = target.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        typer.secho(
            f"Could not import module {module_name!r}: {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from e
    cls = getattr(module, class_name, None)
    if cls is None:
        typer.secho(
            f"No such class {class_name!r} in module {module_name!r}.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
        typer.secho(
            f"{target!r} is not a Pydantic BaseModel subclass.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    return cls


def _node_label(node: Any) -> str:
    """Compact one-line label for a node in the rich-rendered tree."""
    name = node.name or "?"
    kind = node.kind
    extra = ""
    value = getattr(node, "value", None)
    if value is not None:
        extra = f" = {value!r}"
        # Truncate long values so the tree stays readable.
        if len(extra) > 60:
            extra = extra[:57] + "...'"
    required = "" if node.required else " (optional)"
    return f"[bold]{name}[/bold] [dim]:: {kind}[/dim]{required}{extra}"


def _walk(node: Any, parent: Tree) -> None:
    """Recursively render a FormNode subtree under ``parent``."""
    branch = parent.add(_node_label(node))
    if isinstance(node, GroupNode):
        for child in node.fields:
            _walk(child, branch)
    elif isinstance(node, SequenceNode):
        for item in node.items:
            _walk(item, branch)
    elif isinstance(node, MappingNode):
        for k_node, v_node in node.entries:
            entry_branch = branch.add(f"[cyan]entry[/cyan] :: {k_node.value!r}")
            _walk(v_node, entry_branch)
    elif isinstance(node, UnionNode):
        if node.selected is not None:
            sel = branch.add(f"[magenta]selected[/magenta] (variant {node.selected_index})")
            _walk(node.selected, sel)
        else:
            branch.add("[dim]<no variant selected>[/dim]")
    # Leaf nodes have no children — _node_label already shows the value.


@app.command()
def show(target: str) -> None:
    """Introspect a Pydantic schema and print its form-tree shape.

    TARGET is of the form ``module.path:ClassName``, e.g.
    ``mypkg.config:AppSettings``.
    """
    schema = _load_schema(target)
    tree = build_form_tree(schema)
    console = Console()
    root = Tree(f"[bold green]{schema.__module__}.{schema.__name__}[/bold green]")
    for child in tree.root.fields:
        _walk(child, root)
    console.print(root)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_cli.py -v`

Expected: All 6 PASS.

If `test_show_invalid_format` fails because typer captures `module:class` differently, double-check the error message string — `"expected 'module:Class' format"` should match the regex `module:class` case-insensitively.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`

Expected: ~318 passed.

- [ ] **Step 8: Manual smoke check from the command line**

Run: `uv run pydantic-studio show tests.fixtures.schemas:Phase3Sink`

Expected: a colorful rich-rendered tree showing 14 child nodes with their kinds and default values.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml src/pydantic_studio/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): minimal `pydantic-studio show` for schema introspection"
```

---

### Task 19: README + version bump

**Why:** Plan 3 ships v0.0.3. Update the version string, mention the new types in the README, and demonstrate the CLI.

**Files:**
- Modify: `src/pydantic_studio/__init__.py` — version bump
- Modify: `pyproject.toml` — version bump
- Modify: `README.md`

- [ ] **Step 1: Bump versions**

In `pyproject.toml`:

```toml
version = "0.0.3"
```

In `src/pydantic_studio/__init__.py`:

```python
__version__ = "0.0.3"
```

- [ ] **Step 2: Update README — Phase 3 example**

Append a new section to `README.md` (after the existing Phase-2 example):

```markdown
## Type coverage (v0.0.3)

Pydantic Studio now models the following types out of the box:

**Primitives:** `str`, `int`, `float`, `bool`, `Decimal`
**Choices:** `Enum`, `Literal[...]`
**Containers:** `list[T]`, `set[T]`, `tuple[T, ...]`, `tuple[T1, T2, ...]`, `dict[K, V]`
**Unions:** `T | U`, `Optional[T]`
**Temporal:** `datetime`, `date`, `time`, `timedelta`
**Network:** `IPv4Address`, `IPv6Address`, `IPv4Network`, `IPv6Network`,
            `AnyUrl`, `HttpUrl`, `FileUrl` (any Pydantic URL class), `EmailStr`
**Special:** `pathlib.Path`, `uuid.UUID`, `SecretStr`, `SecretBytes`, `re.Pattern`, `bytes`

### Example

```python
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, HttpUrl, SecretStr

from pydantic_studio import build_form_tree


class AppConfig(BaseModel):
    api_url: HttpUrl = HttpUrl("https://api.example.com")
    api_key: SecretStr = SecretStr("default-key")
    home: Path = Path("/srv/app")
    started_at: datetime = datetime(2026, 5, 6, 12, 0)


tree = build_form_tree(AppConfig)
tree.set_value("api_url", "https://newapi.example.com")
config = tree.to_instance()
print(config.api_url)
# https://newapi.example.com/
```

### Schema introspection CLI

```bash
$ uv run pydantic-studio show mypkg.config:AppConfig
AppConfig
├── api_url :: url = 'https://api.example.com'
├── api_key :: secret = 'default-key'
├── home :: path = '/srv/app'
└── started_at :: datetime = datetime.datetime(2026, 5, 6, 12, 0)
```

The CLI is intentionally minimal in v0.0.3 — only `show` (schema introspection)
ships. `edit` / `check` / `render` arrive in v0.0.4 with YAML I/O.

### Optional: email-validator

`EmailStr` requires the `email-validator` package. Install with:

```bash
uv pip install 'pydantic-studio[email]'
```

Without the extra, EmailNode falls back to a permissive `'@'`-presence check.
```

- [ ] **Step 3: Run full test suite one more time**

Run: `uv run pytest -q && uv run ruff check`

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/pydantic_studio/__init__.py README.md
git commit -m "docs: README + version bump for v0.0.3"
```

---

### Task 20: Merge ceremony

**Why:** Same merge convention as Phase 2 — `--no-ff` merge to master, tag at the feature tip, do NOT push (per user's standing instruction).

- [ ] **Step 1: Verify clean state on feature branch**

```bash
git status
git log --oneline -5
```

Expected: clean working tree; recent commits include "feat(types): BytesNode...", "test: Phase3Sink...", "feat(cli): minimal pydantic-studio show...", "docs: README + version bump for v0.0.3".

- [ ] **Step 2: Tag the feature tip**

```bash
git tag v0.0.3-phase-3
```

- [ ] **Step 3: Merge to master with --no-ff**

```bash
git checkout master
git merge --no-ff feature/phase-3-type-coverage-round-2 -m "merge: Phase 3 — Type coverage round 2 + minimal CLI"
```

Expected: a merge commit on master.

- [ ] **Step 4: Verify final test suite on master**

```bash
uv run pytest -q
```

Expected: ~318 passed.

- [ ] **Step 5: Delete the feature branch (local only)**

```bash
git branch -d feature/phase-3-type-coverage-round-2
```

- [ ] **Step 6: Show final state**

```bash
git log --oneline -10
git tag --list 'v0.0.*'
```

Expected: tag `v0.0.3-phase-3` reachable via the merge commit's second parent. **Do not push.**

---

## Phase 3 — Self-Review Notes

The following spec requirements (from `2026-05-05-pydantic-studio-design.md`) are addressed by this plan:

| Spec § | Requirement | Task(s) |
|---|---|---|
| § 6.1 | `types/datetime.py` (date/time/datetime/timedelta/timezone) | T6, T7 (timezone deferred — Pydantic stores tz on datetime, not as a separate field) |
| § 6.1 | network types | T8, T9, T10 |
| § 6.1 | `path.py` etc. (special types) | T11–T15 |
| § 8 | typer CLI scaffold | T18 (`show` only; `fill`/`edit`/`run`/`check` deferred to Plan 4) |
| Phase 2 follow-ups | 4 starter items from Final Reviewer | T2, T3, T4, T5 |

Items intentionally deferred:
- YAML I/O round-trip (Plan 4)
- `pydantic.NameEmail`, DSN classes (Postgres/MySQL/etc.), `ByteSize` — UrlNode + EmailNode cover the canonical 95%; specialty subclasses can be added per-request later
- Encrypted draft persistence for SecretStr (security-hardening pass; v0.x)

If any task fails to land cleanly, the most likely culprits:
- **AnyNode discriminator collision**: each new node MUST have a unique `kind` literal. Check no two nodes share a kind string.
- **model_rebuild order**: if you add a node but forget to extend AnyNode, GroupNode/SequenceNode/MappingNode/UnionNode may reject it during schema rebuild. Always extend AnyNode in the same commit as the new node class.
- **TypeAdapter caching in UrlNode**: the cached adapter is set via `object.__setattr__` to bypass Pydantic's field machinery. If you remove the cache, validation works but is slower; if you cache via a regular field, Pydantic tries to model_dump the adapter and fails.

---

**End of Plan 3.**
