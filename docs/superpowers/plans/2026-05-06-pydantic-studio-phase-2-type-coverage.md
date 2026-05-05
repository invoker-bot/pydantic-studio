# pydantic-studio Implementation Plan — Phase 2: Type Coverage

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the type-system foundation (Annotated unwrapping, metadata extraction, recursive None filtering) and the spec's Phase 2 type families: Enum, Literal, Sequence (list / set / tuple), Mapping (dict), Union (incl. Optional). Resolve foundational concerns from Phase 1 review (`set_value` contract, registry test helper, `uv_build` upper bound).

**Architecture:** A new `types/` subpackage owns the dispatch layer: `registry`, `annotated` helpers, `metadata` extraction, plus one module per type family (`primitives`, `models`, `choices`, `sequences`, `mapping`, `unions`). `tree/` keeps FormTree state and the node hierarchy. `set_value` runs node-local validation and returns a `ValidationResult`. `GroupNode.to_python()` filters `None` recursively so Pydantic applies defaults at every depth. UnionNode stores fully-qualified variant type names; `select_variant` rebuilds the variant via the registry, reusing the same `module.ClassName` lookup pattern as `GroupNode.schema_class`.

**Tech Stack:** Python 3.11+, Pydantic 2.7+, `annotated_types` (transitive via Pydantic), pytest, uv (build + run), ruff (lint), pyright (type check).

**Spec reference:** `docs/superpowers/specs/2026-05-05-pydantic-studio-design.md`

---

## Plan series overview

This is **Plan 2 of 6** for `pydantic-studio` v0.1.

| # | Plan | Adds | Verifiable by |
|---|---|---|---|
| 1 | Form Tree core ✓ done | Primitives, groups, snapshots, undo/redo, draft, `to_instance` | Unit tests + programmatic API |
| **2** | **Type coverage (this plan)** | Foundation + Enum/Literal + container types (Sequence/Mapping/Union) | Unit tests on every type |
| 3 | Datetime/Network/Special types + YAML I/O + CLI MVP | datetime/timezone, IP/URL/DSN/Email, Path/UUID/SecretStr/Pattern; ruamel.yaml round-trip | E2E |
| 4 | Textual renderer | TUI app, sidebar/form/preview, key bindings | Pilot snapshot tests |
| 5 | HTML renderer | FastAPI + HTMX + Tailwind | Playwright E2E |
| 6 | TOML/JSON I/O + polish + docs | tomlkit, JSON, markdown descriptions, mkdocs | Manual demos |

**Scope note:** datetime / network / special types defer to Plan 3 (folded with YAML I/O). Pydantic v2's constrained types (`constr`, `conint`, `confloat`, `condecimal`) are **automatically supported once T5 lands** — they desugar to `Annotated[T, StringConstraints(...)]` / `Annotated[T, Interval(...)]`, which the metadata extractor handles. No separate "constrained" task is required.

---

## Files for Phase 2

```
pydantic-config/
├── pyproject.toml                                MODIFY (uv_build upper bound)
├── tests/
│   ├── conftest.py                               MODIFY (autouse registry reset)
│   ├── fixtures/
│   │   └── schemas.py                            MODIFY (add Color/Flag/ListSchema/...)
│   └── unit/
│       ├── test_annotated.py                     NEW
│       ├── test_metadata.py                      NEW
│       ├── test_to_python_filtering.py           NEW
│       ├── test_set_value.py                     NEW
│       ├── test_enum.py                          NEW
│       ├── test_literal.py                       NEW
│       ├── test_sequence.py                      NEW
│       ├── test_mapping.py                       NEW
│       ├── test_union.py                         NEW
│       └── test_smoke.py                         MODIFY (cover new types)
└── src/pydantic_studio/
    ├── __init__.py                               MODIFY (re-export new nodes/builders)
    ├── tree/
    │   ├── nodes.py                              MODIFY (recursive None filter, EnumNode, LiteralNode, SequenceNode, MappingNode, UnionNode, set_value→ValidationResult, sequence/mapping/union mutations)
    │   └── builder.py                            MODIFY (thin entry point; reset_default_registry helper; registry moves to types/)
    └── types/                                    NEW package
        ├── __init__.py                           NEW
        ├── registry.py                           NEW (moved from tree/builder.py)
        ├── annotated.py                          NEW (predicates + strip_annotated; vendored from promptantic)
        ├── metadata.py                           NEW (extract_constraints)
        ├── primitives.py                         NEW (StringBuilder/IntBuilder/...; moved + metadata-aware)
        ├── models.py                             NEW (GroupBuilder; moved)
        ├── choices.py                            NEW (EnumBuilder + LiteralBuilder)
        ├── sequences.py                          NEW (ListBuilder + SetBuilder + TupleBuilder)
        ├── mapping.py                            NEW (DictBuilder)
        └── unions.py                             NEW (UnionBuilder)
```

---

## Tasks

### Task 1: Housekeeping — `uv_build` pin, `reset_default_registry`, autouse reset fixture

**Why first:** Adding many builders in subsequent tasks risks test pollution (a builder registered in one test leaking into the next). Land the reset helper + autouse fixture before any new builder ships. The `uv_build<0.12` pin is a one-line correctness fix from Phase 1 review.

**Files:**
- Modify: `pyproject.toml:43-44` (`requires = ["uv_build>=0.8"]` → add upper bound)
- Modify: `src/pydantic_studio/tree/builder.py` (add `reset_default_registry`)
- Modify: `tests/conftest.py` (add autouse fixture)
- Create: `tests/unit/test_registry_reset.py`

- [ ] **Step 1: Pin `uv_build` upper bound**

In `pyproject.toml` change:

```toml
[build-system]
requires = ["uv_build>=0.8,<0.12"]
build-backend = "uv_build"
```

- [ ] **Step 2: Add `reset_default_registry` to `tree/builder.py`**

Append below `default_registry()` in `src/pydantic_studio/tree/builder.py`:

```python
def reset_default_registry() -> None:
    """Drop the cached default registry so the next ``default_registry()``
    call rebuilds it from scratch.

    Tests that mutate the registry (e.g., via ``register_builder``) must
    call this in teardown — otherwise registrations leak between tests.
    The autouse fixture in ``tests/conftest.py`` calls it for every test.
    """
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None
```

- [ ] **Step 3: Add autouse fixture to `tests/conftest.py`**

Replace the contents of `tests/conftest.py` with:

```python
"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from pydantic_studio.tree.builder import reset_default_registry


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    """Reset the global default builder registry before every test.

    Without this fixture, a test that registers a custom builder leaves it
    in place for every subsequent test, leading to order-dependent failures.
    """
    reset_default_registry()
```

- [ ] **Step 4: Write the failing test for the helper**

Create `tests/unit/test_registry_reset.py`:

```python
"""Tests for reset_default_registry()."""

from __future__ import annotations

from typing import Any

from pydantic.fields import FieldInfo

from pydantic_studio.tree.builder import (
    default_registry,
    reset_default_registry,
)
from pydantic_studio.tree.nodes import StringNode


class _StubBuilder:
    """Minimal NodeBuilder for testing — matches str only."""

    def matches(self, type_: type) -> bool:
        return type_ is str

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> StringNode:
        return StringNode(name="stub", value="stubbed")


def test_reset_returns_fresh_registry_after_register() -> None:
    reg1 = default_registry()
    reg1.register(_StubBuilder())
    reset_default_registry()
    reg2 = default_registry()
    # Must be a fresh instance, not the mutated one.
    assert reg1 is not reg2
    # The stub registration must not survive.
    found = reg2.find(str)
    assert not isinstance(found, _StubBuilder)


def test_reset_is_idempotent() -> None:
    reset_default_registry()
    reset_default_registry()  # second call must not error
    reg = default_registry()
    assert reg is not None
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_registry_reset.py -v`
Expected: 2 passed.

- [ ] **Step 6: Run the full test suite to confirm no regressions**

Run: `uv run pytest -q`
Expected: all prior tests still pass (96 from Phase 1 + 2 new = 98).

- [ ] **Step 7: Lint + type check**

Run: `uv run ruff check . && uv run pyright src tests`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/pydantic_studio/tree/builder.py tests/conftest.py tests/unit/test_registry_reset.py
git commit -m "chore: pin uv_build<0.12 + reset_default_registry helper + autouse fixture"
```

---

### Task 2: Refactor — move dispatch layer into `types/` subpackage

**Why now:** Plan 2 adds 5+ new builder modules. Putting them all in `tree/builder.py` would balloon that file past the "one clear responsibility" rule. The spec's section 4 module layout already calls for a `types/` subpackage; we land that structure now so every later task knows where to add its builder.

**Files:**
- Create: `src/pydantic_studio/types/__init__.py`
- Create: `src/pydantic_studio/types/registry.py`
- Create: `src/pydantic_studio/types/primitives.py`
- Create: `src/pydantic_studio/types/models.py`
- Modify: `src/pydantic_studio/tree/builder.py` (slim to entry point + re-exports)
- Modify: `src/pydantic_studio/__init__.py` (no public-API changes; verify imports still work)

- [ ] **Step 1: Create the `types/` package marker**

Create `src/pydantic_studio/types/__init__.py`:

```python
"""Type-dispatch layer.

Each module in this package owns one type family. ``registry.py`` defines
the ``NodeBuilder`` Protocol and the ``Registry`` class; the per-family
modules (``primitives``, ``models``, ``choices``, ``sequences``,
``mapping``, ``unions``) implement concrete builders.
"""

from __future__ import annotations
```

- [ ] **Step 2: Create `types/registry.py`**

Create `src/pydantic_studio/types/registry.py` with the `NodeBuilder` Protocol and `Registry` class moved verbatim from `tree/builder.py`:

```python
"""NodeBuilder protocol and Registry.

Builders are kept in an ordered list; ``find`` returns the first builder
whose ``matches`` returns True. New registrations are *prepended* so user
code can override defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic_studio.exceptions import NoBuilderError

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.nodes import AnyNode


@runtime_checkable
class NodeBuilder(Protocol):
    """A builder turns one Python type into a FormNode."""

    def matches(self, type_: type) -> bool: ...

    def build(
        self,
        type_: type,
        field_info: FieldInfo,
        existing: Any,
    ) -> AnyNode: ...


class Registry:
    """Ordered list of builders. First match wins."""

    def __init__(self) -> None:
        self._builders: list[NodeBuilder] = []

    def register(self, builder: NodeBuilder) -> None:
        """Prepend ``builder``; new registrations take priority."""
        self._builders.insert(0, builder)

    def find(self, type_: type) -> NodeBuilder:
        for b in self._builders:
            if b.matches(type_):
                return b
        raise NoBuilderError(type_)

    def __len__(self) -> int:
        return len(self._builders)
```

- [ ] **Step 3: Create `types/primitives.py`**

Move `StringBuilder`, `IntBuilder`, `FloatBuilder`, `BoolBuilder`, `DecimalBuilder` verbatim from `tree/builder.py` into `src/pydantic_studio/types/primitives.py`:

```python
"""Builders for str / int / float / bool / Decimal."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    FloatNode,
    IntNode,
    StringNode,
)

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


class StringBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is str

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> StringNode:
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return StringNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
        )


class IntBuilder:
    def matches(self, type_: type) -> bool:
        # Exclude bool, which is a subclass of int in Python.
        return type_ is int

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> IntNode:
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return IntNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
        )


class FloatBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is float

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> FloatNode:
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return FloatNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
        )


class BoolBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is bool

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> BoolNode:
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return BoolNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
        )


class DecimalBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is Decimal

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> DecimalNode:
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return DecimalNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
        )
```

- [ ] **Step 4: Create `types/models.py`**

Move `GroupBuilder` from `tree/builder.py` into `src/pydantic_studio/types/models.py`:

```python
"""Builder for nested Pydantic BaseModel subclasses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from pydantic_studio.tree.nodes import GroupNode

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry


class GroupBuilder:
    """Recursive builder for any ``BaseModel`` subclass.

    Owns a back-reference to the registry so it can dispatch each field of
    the model to whichever builder matches that field's annotation.
    """

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return isinstance(type_, type) and issubclass(type_, BaseModel)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> GroupNode:
        assert issubclass(type_, BaseModel)
        existing_dict: dict[str, Any] = existing if isinstance(existing, dict) else {}

        children: list[Any] = []
        for fname, finfo in type_.model_fields.items():
            child_type = finfo.annotation
            if child_type is None:
                child_type = str  # fallback — shouldn't happen in practice
            child_builder = self._registry.find(child_type)
            child = child_builder.build(child_type, finfo, existing_dict.get(fname))
            # The child builder didn't know the field name (it sees only the
            # type); we set it here from the parent's perspective. This avoids
            # the FieldInfo.alias hack and respects users' real aliases.
            child.name = fname
            children.append(child)

        return GroupNode(
            name=field_info.alias or type_.__name__,
            description=field_info.description,
            required=field_info.is_required(),
            schema_class=type_,
            fields=children,
        )
```

- [ ] **Step 5: Slim `tree/builder.py`**

Replace `src/pydantic_studio/tree/builder.py` entirely with:

```python
"""Public entry point for tree construction.

The dispatch layer (Registry, NodeBuilder Protocol, concrete builders)
lives in ``pydantic_studio.types``. This module is a thin facade that
wires the default registry and exposes ``build_form_tree``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic_studio.types.models import GroupBuilder
from pydantic_studio.types.primitives import (
    BoolBuilder,
    DecimalBuilder,
    FloatBuilder,
    IntBuilder,
    StringBuilder,
)
from pydantic_studio.types.registry import NodeBuilder, Registry

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = [
    "NodeBuilder",
    "Registry",
    "build_form_tree",
    "default_registry",
    "reset_default_registry",
]

_DEFAULT_REGISTRY: Registry | None = None


def default_registry() -> Registry:
    """Return the global default registry (lazily constructed)."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        reg = Registry()
        # Order does not matter among primitives (mutually exclusive on type),
        # but follow a stable convention. GroupBuilder comes last so it only
        # matches BaseModel subclasses no other builder claimed.
        reg.register(StringBuilder())
        reg.register(IntBuilder())
        reg.register(FloatBuilder())
        reg.register(BoolBuilder())
        reg.register(DecimalBuilder())
        reg.register(GroupBuilder(reg))
        _DEFAULT_REGISTRY = reg
    return _DEFAULT_REGISTRY


def reset_default_registry() -> None:
    """Drop the cached default registry. See ``tests/conftest.py``."""
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None


def build_form_tree(
    schema: type[BaseModel],
    existing: dict[str, Any] | None = None,
    registry: Registry | None = None,
) -> Any:
    """Build a FormTree from a Pydantic BaseModel subclass.

    Args:
        schema: The user's Pydantic model class.
        existing: Optional dict to pre-populate field values.
        registry: Optional custom registry (defaults to the global default).

    Returns:
        FormTree: Root container with schema reference, root group, and history fields.
    """
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.nodes import FormTree

    reg = registry if registry is not None else default_registry()
    group_builder = GroupBuilder(reg)
    root = group_builder.build(schema, FieldInfo(annotation=schema), existing or {})
    schema_name = f"{schema.__module__}:{schema.__qualname__}"
    return FormTree(
        schema_class=schema,
        schema_name=schema_name,
        root=root,
        created_at=datetime.now(tz=UTC),
    )
```

- [ ] **Step 6: Run all existing tests — must remain green**

Run: `uv run pytest -q`
Expected: 98 passed (96 prior + 2 from T1).

- [ ] **Step 7: Lint + type check**

Run: `uv run ruff check . && uv run pyright src tests`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/ src/pydantic_studio/tree/builder.py
git commit -m "refactor: move dispatch layer into types/ subpackage"
```

---

### Task 3: Recursive `None` filtering in `to_python`

**Why:** Phase 1 reviewer flagged that `FormTree.to_instance` filters `None` only at the top level, so a nested `GroupNode` with `None`-valued fields can pass through and hit Pydantic, which then can't apply defaults. Fix: each `GroupNode.to_python()` filters `None` from its own dict before returning. `to_instance` no longer needs to filter.

**Known v0.1 limitation (document in code):** This means a user cannot save an `Optional[T]` field as explicit `None` — the value is treated as "unset" and Pydantic applies the field's default. v0.2 may add an "explicit-null" toggle on Optional nodes.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py:184-186` (`GroupNode.to_python`)
- Modify: `src/pydantic_studio/tree/nodes.py:217-240` (`FormTree.to_instance` — drop redundant top-level filter)
- Create: `tests/unit/test_to_python_filtering.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_to_python_filtering.py`:

```python
"""Recursive None filtering in GroupNode.to_python and FormTree.to_instance."""

from __future__ import annotations

from pydantic import BaseModel

from pydantic_studio import build_form_tree


class Inner(BaseModel):
    a: int = 7
    b: str = "default-b"


class Outer(BaseModel):
    name: str = "n"
    inner: Inner = Inner()


def test_nested_none_dropped_for_default_to_apply() -> None:
    tree = build_form_tree(Outer)
    # Nothing was filled in: every leaf is None.
    out = tree.root.to_python()
    # Top-level None dropped (was already true in Phase 1).
    assert "name" not in out
    # The inner group must serialize either as an empty dict or be absent —
    # either way, no None-valued keys leak through.
    assert "inner" not in out or out["inner"] == {}


def test_nested_to_instance_applies_defaults() -> None:
    tree = build_form_tree(Outer)
    instance = tree.to_instance()
    assert instance.name == "n"
    assert instance.inner.a == 7
    assert instance.inner.b == "default-b"


def test_nested_partially_filled() -> None:
    tree = build_form_tree(Outer, existing={"inner": {"a": 99}})
    out = tree.root.to_python()
    assert out["inner"] == {"a": 99}  # b is None and is filtered
    instance = tree.to_instance()
    assert instance.inner.a == 99
    assert instance.inner.b == "default-b"  # default applied
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_to_python_filtering.py -v`
Expected: at least the second + third tests fail (nested None leaks into Pydantic and either crashes or yields wrong values).

- [ ] **Step 3: Update `GroupNode.to_python`**

Replace the `to_python` method on `GroupNode` (around `nodes.py:184-186`):

```python
    def to_python(self) -> dict[str, Any]:
        """Collect child values into a dict keyed by child names.

        ``None`` values are filtered: a field whose value is ``None`` is
        treated as "not set", letting Pydantic apply the schema default.
        Known v0.1 limitation: users cannot save an Optional[T] field as
        explicit None — that requires v0.2's explicit-null toggle.
        """
        out: dict[str, Any] = {}
        for f in self.fields:
            v = f.to_python()
            if v is None:
                continue
            out[f.name] = v
        return out
```

- [ ] **Step 4: Drop the redundant top-level filter in `FormTree.to_instance`**

In `nodes.py`, replace the body of `to_instance` (around line 217):

```python
    def to_instance(self) -> BaseModel:
        """Materialize the tree into the user's schema_class.

        Raises:
            ValidationFailedError: if the schema rejects the produced dict.
        """
        from pydantic import ValidationError

        from pydantic_studio.exceptions import ValidationFailedError

        if self.schema_class is None:
            msg = "FormTree.schema_class is not set"
            raise RuntimeError(msg)
        # GroupNode.to_python now filters None at every depth, so no
        # additional top-level filtering is needed here.
        data = self.to_python()
        try:
            return self.schema_class.model_validate(data)
        except ValidationError as e:
            errors = [
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                for err in e.errors()
            ]
            raise ValidationFailedError(errors) from e
```

- [ ] **Step 5: Run the new test — must pass**

Run: `uv run pytest tests/unit/test_to_python_filtering.py -v`
Expected: 3 passed.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q`
Expected: all green (101 tests).

- [ ] **Step 7: Lint + type check**

Run: `uv run ruff check . && uv run pyright src tests`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py tests/unit/test_to_python_filtering.py
git commit -m "fix(tree): filter None recursively in GroupNode.to_python"
```

---

### Task 4: `set_value` returns `ValidationResult`

**Why:** Phase 1 reviewer flagged that `set_value`'s public contract was unclear — the spec says it returns `ValidationResult` after running node-local validation, but the Phase 1 implementation returned `None` and never validated. Land the contract change now: each `FormNode` subclass gets a `validate_value(v) -> tuple[str, ...]` method (returns error messages, empty if valid), and `set_value` aggregates into a `ValidationResult`.

This also unblocks per-field error display in renderers (Plan 4 / Plan 5).

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` (add `validate_value` on FormNode + each leaf subclass; change `set_value` signature + body)
- Create: `tests/unit/test_set_value.py`
- Modify: `tests/unit/test_mutations.py` (existing tests — update calls to `set_value` to consume the return value)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_set_value.py`:

```python
"""set_value contract: returns ValidationResult after node-local validation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.tree.validation import ValidationResult


class Schema(BaseModel):
    name: str = Field(min_length=3)
    age: int = Field(ge=0)


def test_set_valid_value_returns_ok() -> None:
    tree = build_form_tree(Schema)
    result = tree.set_value("name", "Alice")
    assert isinstance(result, ValidationResult)
    assert result.ok is True
    assert result.errors == ()


def test_set_invalid_value_returns_errors() -> None:
    tree = build_form_tree(Schema)
    # name has min_length=3 — but we won't have wired that constraint yet
    # in T4 (T6 wires metadata). Instead, use the type-level constraint:
    # set a non-int into the int field.
    result = tree.set_value("age", "not-a-number")
    assert result.ok is False
    assert len(result.errors) >= 1


def test_set_value_still_pushes_snapshot_on_invalid() -> None:
    """Even when validation fails, the mutation is applied and a snapshot
    is pushed — undo() should be able to revert the bad value."""
    tree = build_form_tree(Schema)
    tree.set_value("name", "Alice")  # valid baseline
    tree.set_value("age", "not-a-number")  # invalid
    assert tree.undo() is True
    age_node = tree.root.find("age")
    assert age_node is not None
    assert age_node.value != "not-a-number"
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest tests/unit/test_set_value.py -v`
Expected: at least the first test fails because `set_value` currently returns `None`, not `ValidationResult`.

- [ ] **Step 3: Add `validate_value` to FormNode + leaf subclasses**

In `src/pydantic_studio/tree/nodes.py`, add a default `validate_value` to `FormNode` and override it on each leaf:

```python
class FormNode(BaseModel):
    # ... existing fields ...

    def validate_value(self, value: Any) -> tuple[str, ...]:
        """Return tuple of error messages for ``value`` against this node's
        type. Empty tuple = valid. Default: accept any value.

        Subclasses override to enforce per-type rules.
        """
        return ()
```

Override on `StringNode`:

```python
    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, str):
            return (f"expected str, got {type(value).__name__}",)
        return ()
```

Override on `IntNode`:

```python
    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Reject bool explicitly even though it is an int subclass.
        if isinstance(value, bool) or not isinstance(value, int):
            return (f"expected int, got {type(value).__name__}",)
        return ()
```

Override on `FloatNode`:

```python
    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Accept int (Pydantic coerces). Reject bool.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return (f"expected float, got {type(value).__name__}",)
        return ()
```

Override on `BoolNode`:

```python
    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, bool):
            return (f"expected bool, got {type(value).__name__}",)
        return ()
```

Override on `DecimalNode`:

```python
    def validate_value(self, value: Any) -> tuple[str, ...]:
        from decimal import Decimal, InvalidOperation

        if value is None:
            return () if not self.required else ("value is required",)
        if isinstance(value, Decimal):
            return ()
        if isinstance(value, (int, str)):
            try:
                Decimal(value)
            except (InvalidOperation, ValueError):
                return (f"cannot convert {value!r} to Decimal",)
            return ()
        return (f"expected Decimal, got {type(value).__name__}",)
```

(GroupNode keeps the default `validate_value` — group-level validation is `to_instance`'s job.)

- [ ] **Step 4: Update `FormTree.set_value` signature + body**

Replace the body of `set_value` in `FormTree`:

```python
    def set_value(self, path: str, value: Any) -> ValidationResult:
        """Set ``value`` at the given path; runs node-local validation.

        The mutation is applied and a snapshot is pushed regardless of
        whether validation passes — this lets the user undo a bad entry.
        Returns a ``ValidationResult`` whose ``errors`` are empty iff the
        value passes the target node's ``validate_value``.

        Cross-field validation runs at submit time (``to_instance``).
        """
        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.paths import Path as _Path
        from pydantic_studio.tree.validation import ValidationResult

        self._push_snapshot(_snap.take(self.root))

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            msg = "cannot set value on the root group itself"
            raise ValueError(msg)
        parent: Any = self.root
        for seg in path_obj.segments[:-1]:
            if isinstance(parent, GroupNode) and isinstance(seg, str):
                child = parent.find(seg)
                if child is None:
                    msg = f"no field named {seg!r} at this level"
                    raise KeyError(msg)
                parent = child
            else:
                msg = f"cannot navigate segment {seg!r} (not a group)"
                raise KeyError(msg)

        last = path_obj.segments[-1]
        if isinstance(parent, GroupNode) and isinstance(last, str):
            target = parent.find(last)
            if target is None:
                msg = f"no field named {last!r}"
                raise KeyError(msg)
            errors = target.validate_value(value)
            target.value = value
            target.error = errors[0] if errors else None
        else:
            msg = f"cannot set on non-group parent at segment {last!r}"
            raise KeyError(msg)

        if self.draft_path is not None:
            from pydantic_studio.tree import snapshots as _snap_2

            _snap_2.draft_save(self, self.draft_path)

        return ValidationResult.fail(list(errors)) if errors else ValidationResult.ok()
```

Add at the top of `nodes.py` (with the other imports):

```python
from pydantic_studio.tree.validation import ValidationResult
```

- [ ] **Step 5: Update existing `test_mutations.py` to consume the return value**

Open `tests/unit/test_mutations.py`. For every line that calls `tree.set_value(...)` without using the return value, leave it as is (Python allows ignoring returns). For any test that asserted `set_value` returned `None`, change the assertion to check `ValidationResult`.

Run: `uv run pytest tests/unit/test_mutations.py -v`
Expected: existing tests still green.

- [ ] **Step 6: Run the new tests — must pass**

Run: `uv run pytest tests/unit/test_set_value.py -v`
Expected: 3 passed.

- [ ] **Step 7: Run the full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py tests/unit/test_set_value.py tests/unit/test_mutations.py
git commit -m "feat(tree): set_value returns ValidationResult after node-local validation"
```

---

### Task 5: `types/annotated.py` — predicates and `strip_annotated`

**Why:** Every type builder we add from now on must answer questions like *"is this a Union? Optional? Literal? Enum?"* on annotations that may be wrapped in `Annotated[...]`. Centralize the predicates so each builder calls one helper instead of re-implementing the unwrap dance. Vendored from promptantic's `type_utils.py` (MIT, attribution comment in the file).

**Files:**
- Create: `src/pydantic_studio/types/annotated.py`
- Create: `tests/unit/test_annotated.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_annotated.py`:

```python
"""Type-detection predicates for the dispatch layer."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from pydantic_studio.types.annotated import (
    get_optional_inner,
    get_union_args,
    is_enum_type,
    is_literal_type,
    is_optional_type,
    is_pydantic_model,
    is_union_type,
    strip_annotated,
)


class Color(Enum):
    RED = "red"
    BLUE = "blue"


class Inner(BaseModel):
    x: int = 0


def test_strip_annotated_unwraps_metadata() -> None:
    typ = Annotated[int, Field(ge=0)]
    assert strip_annotated(typ) is int


def test_strip_annotated_passes_through_plain_types() -> None:
    assert strip_annotated(int) is int
    assert strip_annotated(str) is str


def test_is_union_type_detects_pep604_and_typing_union() -> None:
    assert is_union_type(int | str) is True
    from typing import Union  # noqa: UP035 — testing the legacy form
    assert is_union_type(Union[int, str]) is True
    assert is_union_type(int) is False


def test_is_optional_type_detects_t_or_none() -> None:
    assert is_optional_type(int | None) is True
    assert is_optional_type(int | str | None) is True
    assert is_optional_type(int | str) is False  # union but no None
    assert is_optional_type(int) is False


def test_get_optional_inner_strips_none() -> None:
    assert get_optional_inner(int | None) is int
    # For a multi-variant Optional, returns the union of the non-None members.
    inner = get_optional_inner(int | str | None)
    args = get_union_args(inner)
    assert set(args) == {int, str}


def test_get_optional_inner_returns_input_when_not_optional() -> None:
    assert get_optional_inner(int) is int


def test_is_literal_type() -> None:
    assert is_literal_type(Literal["a", "b"]) is True
    assert is_literal_type(int) is False


def test_is_enum_type() -> None:
    assert is_enum_type(Color) is True
    assert is_enum_type(int) is False


def test_is_pydantic_model() -> None:
    assert is_pydantic_model(Inner) is True
    assert is_pydantic_model(int) is False
    assert is_pydantic_model("not a class") is False


def test_predicates_unwrap_annotated() -> None:
    assert is_literal_type(Annotated[Literal["a", "b"], "meta"]) is True
    assert is_enum_type(Annotated[Color, "meta"]) is True
    assert is_pydantic_model(Annotated[Inner, "meta"]) is True
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/unit/test_annotated.py -v`
Expected: collection error (module doesn't exist yet).

- [ ] **Step 3: Create `types/annotated.py`**

Create `src/pydantic_studio/types/annotated.py`:

```python
"""Type-detection predicates and ``Annotated`` unwrapping.

Vendored from promptantic (MIT, https://github.com/phil65/promptantic,
``src/promptantic/type_utils.py``). Adapted to drop the prompt_toolkit-
specific helpers and to add ``is_optional_type`` / ``get_optional_inner``
which we need for UnionBuilder's None-aware fast path.
"""

from __future__ import annotations

import types as _types
from enum import Enum
from typing import (
    Annotated,
    Any,
    Literal,
    TypeGuard,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel


def strip_annotated(typ: Any) -> Any:
    """Return the underlying type, unwrapping ``Annotated[T, ...]`` once.

    Non-Annotated inputs pass through unchanged.
    """
    if get_origin(typ) is Annotated:
        return get_args(typ)[0]
    return typ


def is_union_type(typ: Any) -> TypeGuard[Any]:
    """True for both ``Union[A, B]`` and PEP 604 ``A | B``."""
    typ = strip_annotated(typ)
    origin = get_origin(typ)
    return origin is Union or origin is _types.UnionType


def get_union_args(typ: Any) -> tuple[Any, ...]:
    """Return the variant types of a union. Empty tuple if not a union."""
    if not is_union_type(typ):
        return ()
    return get_args(strip_annotated(typ))


def is_optional_type(typ: Any) -> bool:
    """True when ``typ`` is a union that includes ``None``.

    Includes single-variant ``T | None`` (the classical Optional) and
    multi-variant unions like ``int | str | None``.
    """
    if not is_union_type(typ):
        return False
    return type(None) in get_union_args(typ)


def get_optional_inner(typ: Any) -> Any:
    """Strip ``None`` from an Optional union.

    Examples:
        ``int | None``         → ``int``
        ``int | str | None``   → ``int | str``
        ``int``                → ``int`` (passthrough)
    """
    if not is_optional_type(typ):
        return typ
    non_none = tuple(t for t in get_union_args(typ) if t is not type(None))
    if len(non_none) == 1:
        return non_none[0]
    # Reconstruct a union of the remaining members.
    result: Any = non_none[0]
    for t in non_none[1:]:
        result = result | t
    return result


def is_literal_type(typ: Any) -> TypeGuard[Any]:
    """True for ``Literal[...]`` annotations."""
    typ = strip_annotated(typ)
    return get_origin(typ) is Literal


def is_enum_type(typ: Any) -> TypeGuard[type[Enum]]:
    """True for ``Enum`` subclasses."""
    typ = strip_annotated(typ)
    return isinstance(typ, type) and issubclass(typ, Enum)


def is_pydantic_model(typ: Any) -> TypeGuard[type[BaseModel]]:
    """True for ``BaseModel`` subclasses."""
    typ = strip_annotated(typ)
    return isinstance(typ, type) and issubclass(typ, BaseModel)
```

- [ ] **Step 4: Run the tests — must pass**

Run: `uv run pytest tests/unit/test_annotated.py -v`
Expected: 9 passed.

- [ ] **Step 5: Run the full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/types/annotated.py tests/unit/test_annotated.py
git commit -m "feat(types): annotated unwrapping + type-detection predicates"
```

---

### Task 6: `types/metadata.py` — extract constraints + wire into primitive builders

**Why:** Right now `StringBuilder` ignores `Field(min_length=5)` — the constraint is in `field_info.metadata` (a `StringConstraints` instance from Pydantic) but no builder reads it. This task extracts those constraints and pushes them onto the corresponding node fields. Once it lands, Pydantic v2's constrained types (`constr`, `conint`, `confloat`, `condecimal`) **work for free** because they desugar to `Annotated[T, Constraints(...)]`.

**Files:**
- Create: `src/pydantic_studio/types/metadata.py`
- Create: `tests/unit/test_metadata.py`
- Modify: `src/pydantic_studio/types/primitives.py` (each builder reads constraints)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_metadata.py`:

```python
"""extract_constraints: pull annotated_types / pydantic constraints from a FieldInfo."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.types.metadata import extract_constraints


class StrSchema(BaseModel):
    name: str = Field(min_length=2, max_length=10, pattern=r"^[A-Z]")


class IntSchema(BaseModel):
    age: int = Field(ge=0, le=120, multiple_of=1)
    count: int = Field(gt=0, lt=100)


class FloatSchema(BaseModel):
    ratio: float = Field(ge=0.0, le=1.0)


class DecimalSchema(BaseModel):
    price: Decimal = Field(max_digits=10, decimal_places=2, ge=Decimal("0"))


def test_extract_string_constraints() -> None:
    finfo = StrSchema.model_fields["name"]
    c = extract_constraints(finfo)
    assert c["min_length"] == 2
    assert c["max_length"] == 10
    assert c["pattern"] == r"^[A-Z]"


def test_extract_int_constraints_inclusive() -> None:
    finfo = IntSchema.model_fields["age"]
    c = extract_constraints(finfo)
    assert c["ge"] == 0
    assert c["le"] == 120
    assert c["multiple_of"] == 1


def test_extract_int_constraints_exclusive() -> None:
    finfo = IntSchema.model_fields["count"]
    c = extract_constraints(finfo)
    assert c["gt"] == 0
    assert c["lt"] == 100


def test_extract_float_constraints() -> None:
    finfo = FloatSchema.model_fields["ratio"]
    c = extract_constraints(finfo)
    assert c["ge"] == 0.0
    assert c["le"] == 1.0


def test_extract_decimal_constraints() -> None:
    finfo = DecimalSchema.model_fields["price"]
    c = extract_constraints(finfo)
    assert c["max_digits"] == 10
    assert c["decimal_places"] == 2
    assert c["ge"] == Decimal("0")


def test_string_node_carries_constraints_after_build() -> None:
    tree = build_form_tree(StrSchema)
    name = tree.root.find("name")
    assert name is not None
    assert name.min_length == 2
    assert name.max_length == 10
    assert name.pattern == r"^[A-Z]"


def test_int_node_carries_constraints_after_build() -> None:
    tree = build_form_tree(IntSchema)
    age = tree.root.find("age")
    assert age is not None
    assert age.ge == 0
    assert age.le == 120
    assert age.multiple_of == 1


def test_constrained_int_type_works_via_metadata() -> None:
    """Pydantic v2's ``conint`` desugars to Annotated[int, Interval(...)],
    so the metadata extractor handles it transparently."""
    from pydantic import conint

    class S(BaseModel):
        n: conint(ge=5, le=10)  # type: ignore[valid-type]

    tree = build_form_tree(S)
    n = tree.root.find("n")
    assert n is not None
    assert n.ge == 5
    assert n.le == 10


def test_annotated_constraints_via_annotated_types() -> None:
    """Direct Annotated[int, Ge(5)] should also work."""
    from annotated_types import Ge, Le

    class S(BaseModel):
        n: Annotated[int, Ge(5), Le(10)]

    tree = build_form_tree(S)
    n = tree.root.find("n")
    assert n is not None
    assert n.ge == 5
    assert n.le == 10
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/unit/test_metadata.py -v`
Expected: collection or attribute errors.

- [ ] **Step 3: Create `types/metadata.py`**

Create `src/pydantic_studio/types/metadata.py`:

```python
"""Extract numeric / string / decimal constraints from a Pydantic FieldInfo.

Pydantic v2 stores constraints in two places:

1. ``field_info.metadata`` — a list of objects from ``annotated_types``
   (``Ge``, ``Le``, ``Gt``, ``Lt``, ``MultipleOf``, ``MinLen``, ``MaxLen``,
   ``Interval``, ``Len``) plus Pydantic's own ``StringConstraints`` and
   ``Decimal`` helpers.
2. ``field_info.metadata`` for ``Field(min_length=...)`` calls — Pydantic
   normalizes these into the same ``annotated_types`` shapes.

This module flattens those into a plain dict so each builder picks the
keys it understands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def extract_constraints(field_info: FieldInfo) -> dict[str, Any]:
    """Flatten ``field_info.metadata`` into a constraint dict.

    Recognized keys:
        ge, le, gt, lt, multiple_of   — numeric (annotated_types.Interval/Ge/Le/Gt/Lt/MultipleOf)
        min_length, max_length        — sequence/string (annotated_types.MinLen/MaxLen, StringConstraints)
        pattern                       — string (StringConstraints.pattern)
        max_digits, decimal_places    — Decimal (pydantic Decimal helper)

    Unknown metadata items are silently ignored.
    """
    out: dict[str, Any] = {}
    for item in getattr(field_info, "metadata", []) or []:
        # annotated_types primitives
        for attr, key in (
            ("ge", "ge"),
            ("le", "le"),
            ("gt", "gt"),
            ("lt", "lt"),
            ("multiple_of", "multiple_of"),
            ("min_length", "min_length"),
            ("max_length", "max_length"),
            ("max_digits", "max_digits"),
            ("decimal_places", "decimal_places"),
        ):
            v = getattr(item, attr, None)
            if v is not None:
                out[key] = v
        # Interval bundles ge/le/gt/lt — already covered by the loop above.
        # Len bundles min_length/max_length — already covered.
        # StringConstraints.pattern is a string or None.
        pat = getattr(item, "pattern", None)
        if pat is not None and isinstance(pat, str):
            out["pattern"] = pat
    return out
```

- [ ] **Step 4: Wire constraints into the primitive builders**

Update each primitive builder in `src/pydantic_studio/types/primitives.py` to read constraints. Replace the file contents with:

```python
"""Builders for str / int / float / bool / Decimal — constraint-aware."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    FloatNode,
    IntNode,
    StringNode,
)
from pydantic_studio.types.metadata import extract_constraints

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def _default(field_info: FieldInfo) -> Any:
    d = field_info.get_default(call_default_factory=True)
    return None if d is PydanticUndefined else d


class StringBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is str

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> StringNode:
        c = extract_constraints(field_info)
        return StringNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=_default(field_info),
            min_length=c.get("min_length"),
            max_length=c.get("max_length"),
            pattern=c.get("pattern"),
        )


class IntBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is int

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> IntNode:
        c = extract_constraints(field_info)
        return IntNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=_default(field_info),
            ge=c.get("ge"),
            le=c.get("le"),
            gt=c.get("gt"),
            lt=c.get("lt"),
            multiple_of=c.get("multiple_of"),
        )


class FloatBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is float

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> FloatNode:
        c = extract_constraints(field_info)
        return FloatNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=_default(field_info),
            ge=c.get("ge"),
            le=c.get("le"),
            gt=c.get("gt"),
            lt=c.get("lt"),
            multiple_of=c.get("multiple_of"),
        )


class BoolBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is bool

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> BoolNode:
        return BoolNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=_default(field_info),
        )


class DecimalBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is Decimal

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> DecimalNode:
        c = extract_constraints(field_info)
        return DecimalNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=_default(field_info),
            max_digits=c.get("max_digits"),
            decimal_places=c.get("decimal_places"),
            ge=c.get("ge"),
            le=c.get("le"),
        )
```

- [ ] **Step 5: Run the new tests — must pass**

Run: `uv run pytest tests/unit/test_metadata.py -v`
Expected: 9 passed.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 7: Lint + types**

```
uv run ruff check .
uv run pyright src tests
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/metadata.py src/pydantic_studio/types/primitives.py tests/unit/test_metadata.py
git commit -m "feat(types): extract constraints from field metadata + wire into primitive builders"
```

---

### Task 7: `EnumNode` + `EnumBuilder`

**Why:** `Enum` subclasses are common in config schemas (log levels, run modes, etc.). The node stores a closed list of allowed values; the renderer turns it into a dropdown / radio group.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` (add `EnumNode`, extend `AnyNode` discriminated union)
- Create: `src/pydantic_studio/types/choices.py` (will also hold `LiteralBuilder` in T8)
- Modify: `src/pydantic_studio/tree/builder.py` (register `EnumBuilder` in `default_registry`)
- Modify: `tests/fixtures/schemas.py` (add `Color` enum + `WithColor` schema)
- Create: `tests/unit/test_enum.py`

- [ ] **Step 1: Add `Color` and `WithColor` to fixtures**

Append to `tests/fixtures/schemas.py`:

```python
from enum import Enum


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class WithColor(BaseModel):
    favorite: Color = Color.BLUE
    accent: Color | None = None
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_enum.py`:

```python
"""EnumNode + EnumBuilder coverage."""

from __future__ import annotations

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import EnumNode
from tests.fixtures.schemas import Color, WithColor


def test_enum_field_builds_into_enum_node() -> None:
    tree = build_form_tree(WithColor)
    fav = tree.root.find("favorite")
    assert isinstance(fav, EnumNode)
    assert fav.choices == [
        ("RED", Color.RED),
        ("GREEN", Color.GREEN),
        ("BLUE", Color.BLUE),
    ]
    assert fav.default == Color.BLUE


def test_enum_to_python_returns_member() -> None:
    tree = build_form_tree(WithColor, existing={"favorite": Color.RED})
    fav = tree.root.find("favorite")
    assert isinstance(fav, EnumNode)
    assert fav.value == Color.RED
    assert fav.to_python() == Color.RED


def test_enum_to_instance_round_trips() -> None:
    tree = build_form_tree(WithColor, existing={"favorite": Color.GREEN})
    instance = tree.to_instance()
    assert instance.favorite == Color.GREEN


def test_enum_validate_value_rejects_non_member() -> None:
    tree = build_form_tree(WithColor)
    result = tree.set_value("favorite", "not-a-color")
    assert result.ok is False
    assert any("not a Color member" in e for e in result.errors)


def test_enum_validate_value_accepts_member() -> None:
    tree = build_form_tree(WithColor)
    result = tree.set_value("favorite", Color.RED)
    assert result.ok is True
```

- [ ] **Step 3: Add `EnumNode` to `tree/nodes.py`**

In `src/pydantic_studio/tree/nodes.py`, add `EnumNode` below `DecimalNode` (and before `GroupNode`):

```python
class EnumNode(FormNode):
    """Holds a single value drawn from a closed set of Enum members."""

    kind: Literal["enum"] = "enum"
    value: Any = None  # an Enum member or None
    default: Any = None
    # Enum members serialized as (name, member) pairs. Member objects are
    # not Pydantic-friendly across snapshots, so we also store the FQ name
    # of the Enum class for round-trip via sys.modules lookup.
    enum_class_name: str
    choices: list[tuple[str, Any]] = []

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        return self.value

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from enum import Enum

        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, Enum):
            return (f"{value!r} is not a {self.enum_class_name} member",)
        # Compare by name to avoid identity drift across imports.
        if value.name not in [name for name, _ in self.choices]:
            return (f"{value!r} is not a {self.enum_class_name} member",)
        return ()
```

Update the `AnyNode` discriminated union:

```python
AnyNode = Annotated[
    StringNode
    | IntNode
    | FloatNode
    | BoolNode
    | DecimalNode
    | EnumNode
    | GroupNode,
    Discriminator("kind"),
]
```

(Keep the `GroupNode.model_rebuild()` call below the `AnyNode` definition.)

- [ ] **Step 4: Create `types/choices.py` with `EnumBuilder`**

Create `src/pydantic_studio/types/choices.py`:

```python
"""Builders for choice types: Enum and Literal.

(LiteralBuilder is added in T8.)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import EnumNode
from pydantic_studio.types.annotated import is_enum_type, strip_annotated

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


class EnumBuilder:
    """Builds an EnumNode for any Enum subclass."""

    def matches(self, type_: type) -> bool:
        return is_enum_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> EnumNode:
        enum_cls: type[Enum] = strip_annotated(type_)
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        choices = [(m.name, m) for m in enum_cls]
        return EnumNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
            enum_class_name=f"{enum_cls.__module__}.{enum_cls.__qualname__}",
            choices=choices,
        )
```

- [ ] **Step 5: Register `EnumBuilder` in `default_registry`**

In `src/pydantic_studio/tree/builder.py`, update imports + `default_registry`:

```python
from pydantic_studio.types.choices import EnumBuilder  # add to imports
```

Inside `default_registry`, register it before `GroupBuilder` (so Enum subclasses don't fall through to `GroupBuilder`'s `BaseModel` check — they wouldn't, but ordering keeps things clear):

```python
        reg.register(StringBuilder())
        reg.register(IntBuilder())
        reg.register(FloatBuilder())
        reg.register(BoolBuilder())
        reg.register(DecimalBuilder())
        reg.register(EnumBuilder())          # NEW
        reg.register(GroupBuilder(reg))
```

- [ ] **Step 6: Run the new tests — must pass**

Run: `uv run pytest tests/unit/test_enum.py -v`
Expected: 5 passed.

- [ ] **Step 7: Run the full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py src/pydantic_studio/types/choices.py tests/fixtures/schemas.py tests/unit/test_enum.py
git commit -m "feat(types): EnumNode + EnumBuilder"
```

---

### Task 8: `LiteralNode` + `LiteralBuilder`

**Why:** `Literal["debug", "info", "warn"]` is the type-system idiom for closed string/int sets without the ceremony of `Enum`. Same UI shape as Enum, different annotation form.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` (add `LiteralNode`, extend `AnyNode`)
- Modify: `src/pydantic_studio/types/choices.py` (add `LiteralBuilder`)
- Modify: `src/pydantic_studio/tree/builder.py` (register `LiteralBuilder`)
- Modify: `tests/fixtures/schemas.py` (add `LogLevel` literal alias + schema)
- Create: `tests/unit/test_literal.py`

- [ ] **Step 1: Add `LogLevel` to fixtures**

Append to `tests/fixtures/schemas.py`:

```python
from typing import Literal


LogLevel = Literal["debug", "info", "warn", "error"]


class WithLogLevel(BaseModel):
    level: LogLevel = "info"
    severity: Literal[1, 2, 3] = 2
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_literal.py`:

```python
"""LiteralNode + LiteralBuilder coverage."""

from __future__ import annotations

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import LiteralNode
from tests.fixtures.schemas import WithLogLevel


def test_literal_string_field_builds_into_literal_node() -> None:
    tree = build_form_tree(WithLogLevel)
    level = tree.root.find("level")
    assert isinstance(level, LiteralNode)
    assert level.choices == ["debug", "info", "warn", "error"]
    assert level.default == "info"


def test_literal_int_field() -> None:
    tree = build_form_tree(WithLogLevel)
    sev = tree.root.find("severity")
    assert isinstance(sev, LiteralNode)
    assert sev.choices == [1, 2, 3]
    assert sev.default == 2


def test_literal_to_instance_round_trip() -> None:
    tree = build_form_tree(WithLogLevel, existing={"level": "warn"})
    instance = tree.to_instance()
    assert instance.level == "warn"


def test_literal_validate_rejects_unlisted_value() -> None:
    tree = build_form_tree(WithLogLevel)
    result = tree.set_value("level", "trace")
    assert result.ok is False
    assert any("not in choices" in e for e in result.errors)


def test_literal_validate_accepts_listed_value() -> None:
    tree = build_form_tree(WithLogLevel)
    result = tree.set_value("level", "error")
    assert result.ok is True
```

- [ ] **Step 3: Add `LiteralNode` to `tree/nodes.py`**

In `src/pydantic_studio/tree/nodes.py`, add `LiteralNode` below `EnumNode`:

```python
class LiteralNode(FormNode):
    """Holds a value drawn from a closed list defined by ``Literal[...]``."""

    kind: Literal["literal"] = "literal"
    value: Any = None
    default: Any = None
    choices: list[Any] = []

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        return self.value

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if value not in self.choices:
            return (f"{value!r} not in choices {self.choices!r}",)
        return ()
```

Extend the `AnyNode` discriminated union to include `LiteralNode`:

```python
AnyNode = Annotated[
    StringNode
    | IntNode
    | FloatNode
    | BoolNode
    | DecimalNode
    | EnumNode
    | LiteralNode
    | GroupNode,
    Discriminator("kind"),
]
```

- [ ] **Step 4: Add `LiteralBuilder` to `types/choices.py`**

Append to `src/pydantic_studio/types/choices.py`:

```python
from typing import get_args  # add to imports at top

from pydantic_studio.tree.nodes import LiteralNode  # add to imports
from pydantic_studio.types.annotated import is_literal_type  # add to imports


class LiteralBuilder:
    """Builds a LiteralNode for any ``Literal[...]`` annotation."""

    def matches(self, type_: type) -> bool:
        return is_literal_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> LiteralNode:
        choices = list(get_args(strip_annotated(type_)))
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return LiteralNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
            choices=choices,
        )
```

- [ ] **Step 5: Register `LiteralBuilder`**

In `src/pydantic_studio/tree/builder.py`, update imports and `default_registry`:

```python
from pydantic_studio.types.choices import EnumBuilder, LiteralBuilder
```

```python
        reg.register(StringBuilder())
        reg.register(IntBuilder())
        reg.register(FloatBuilder())
        reg.register(BoolBuilder())
        reg.register(DecimalBuilder())
        reg.register(EnumBuilder())
        reg.register(LiteralBuilder())       # NEW
        reg.register(GroupBuilder(reg))
```

- [ ] **Step 6: Run the new tests — must pass**

Run: `uv run pytest tests/unit/test_literal.py -v`
Expected: 5 passed.

- [ ] **Step 7: Run the full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py src/pydantic_studio/tree/builder.py src/pydantic_studio/types/choices.py tests/fixtures/schemas.py tests/unit/test_literal.py
git commit -m "feat(types): LiteralNode + LiteralBuilder"
```

---

### Task 9: `SequenceNode` definition + add to discriminated union

**Why:** Container types are bigger than primitives, so we land the data shape and Pydantic discriminator extension first as a self-contained step. The actual builders (`ListBuilder`, `SetBuilder`, `TupleBuilder`) and mutations (`add_item`, `remove_item`, ...) follow in T10-T12.

**Design notes:**
- One node type, `SequenceNode`, covers list/set/tuple. The `kind: Literal["sequence"]` discriminator is shared; an `origin` field records which container the user expects (`"list"`, `"set"`, `"tuple"`, `"tuple_fixed"`).
- `items: list[AnyNode]` holds the children. For homogeneous containers each item shares the same node type. For fixed-length tuples `tuple[int, str, bool]` each slot has its own annotation (positional types).
- `item_type_name: str | None` — the fully-qualified name of the item annotation, used by the registry on `add_item` to build a fresh child.
- For fixed-length tuples we also store `slot_type_names: list[str] | None` so each slot's type is recoverable.
- `min_length` / `max_length` from `annotated_types.MinLen` / `MaxLen` (extracted via `extract_constraints`).

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` (add `SequenceNode`, extend `AnyNode`)
- Create: `tests/unit/test_sequence.py` (only the discriminator round-trip tests for now)

- [ ] **Step 1: Write the discriminator-level tests**

Create `tests/unit/test_sequence.py`:

```python
"""SequenceNode shape and discriminator round-trip."""

from __future__ import annotations

from pydantic_studio.tree.nodes import GroupNode, SequenceNode, StringNode


def test_sequence_node_construct() -> None:
    node = SequenceNode(
        name="tags",
        origin="list",
        items=[StringNode(name="0", value="a"), StringNode(name="1", value="b")],
        item_type_name="builtins.str",
    )
    assert node.kind == "sequence"
    assert node.origin == "list"
    assert len(node.items) == 2


def test_sequence_node_round_trips_through_group() -> None:
    """A SequenceNode embedded in a GroupNode must serialize and rehydrate
    without losing its kind discriminator."""
    seq = SequenceNode(
        name="tags",
        origin="list",
        items=[StringNode(name="0", value="a")],
        item_type_name="builtins.str",
    )
    group = GroupNode.model_construct(
        name="root",
        kind="group",
        schema_class=__import__("pydantic").BaseModel,
        fields=[seq],
    )
    raw = group.model_dump_json()
    rehydrated = GroupNode.model_validate_json(raw)
    inner = rehydrated.fields[0]
    assert isinstance(inner, SequenceNode)
    assert inner.origin == "list"
    assert inner.items[0].value == "a"


def test_sequence_to_python_returns_list_of_item_values() -> None:
    seq = SequenceNode(
        name="tags",
        origin="list",
        items=[StringNode(name="0", value="a"), StringNode(name="1", value="b")],
        item_type_name="builtins.str",
    )
    assert seq.to_python() == ["a", "b"]


def test_sequence_to_python_for_set_origin_returns_set() -> None:
    seq = SequenceNode(
        name="tags",
        origin="set",
        items=[StringNode(name="0", value="a"), StringNode(name="1", value="b")],
        item_type_name="builtins.str",
    )
    assert seq.to_python() == {"a", "b"}


def test_sequence_to_python_for_tuple_origin_returns_tuple() -> None:
    seq = SequenceNode(
        name="tags",
        origin="tuple",
        items=[StringNode(name="0", value="a")],
        item_type_name="builtins.str",
    )
    assert seq.to_python() == ("a",)
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/unit/test_sequence.py -v`
Expected: collection or attribute errors (`SequenceNode` doesn't exist).

- [ ] **Step 3: Add `SequenceNode` to `tree/nodes.py`**

In `src/pydantic_studio/tree/nodes.py`, add below `LiteralNode`:

```python
class SequenceNode(FormNode):
    """Container for list / set / tuple values.

    ``origin`` selects the Python container used by ``to_python``.
    ``item_type_name`` is the FQ name of the (homogeneous) item annotation,
    used by ``FormTree.add_item`` to build a fresh child via the registry.
    For fixed-length heterogeneous tuples (``origin="tuple_fixed"``),
    ``slot_type_names`` carries one FQ name per slot.
    """

    kind: Literal["sequence"] = "sequence"
    origin: Literal["list", "set", "tuple", "tuple_fixed"]
    items: "list[AnyNode]" = []
    item_type_name: str | None = None
    slot_type_names: list[str] | None = None
    min_length: int | None = None
    max_length: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        values = [it.to_python() for it in self.items]
        if self.origin == "list":
            return values
        if self.origin == "set":
            return set(values)
        return tuple(values)  # both "tuple" and "tuple_fixed"

    def validate_value(self, value: Any) -> tuple[str, ...]:
        # Whole-sequence replacement isn't a typical mutation; renderers
        # use add_item / remove_item / move_item instead. Accept anything
        # iterable for now and let the schema do the work at submit time.
        return ()
```

Extend `AnyNode`:

```python
AnyNode = Annotated[
    StringNode
    | IntNode
    | FloatNode
    | BoolNode
    | DecimalNode
    | EnumNode
    | LiteralNode
    | SequenceNode
    | GroupNode,
    Discriminator("kind"),
]
```

Keep `GroupNode.model_rebuild()` and add `SequenceNode.model_rebuild()` below it (forward-ref `AnyNode` inside `items`):

```python
GroupNode.model_rebuild()
SequenceNode.model_rebuild()
```

- [ ] **Step 4: Run the new tests — must pass**

Run: `uv run pytest tests/unit/test_sequence.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run the full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py tests/unit/test_sequence.py
git commit -m "feat(tree): SequenceNode shape + discriminated union extension"
```

---

### Task 10: `ListBuilder` + `SetBuilder` (homogeneous sequences)

**Why:** Most config sequences are `list[str]` or `list[int]`. SetBuilder shares the same shape with `origin="set"` plus dedup-on-add semantics.

**Files:**
- Create: `src/pydantic_studio/types/sequences.py` (will hold ListBuilder, SetBuilder, TupleBuilder)
- Modify: `src/pydantic_studio/tree/builder.py` (register ListBuilder + SetBuilder)
- Modify: `tests/fixtures/schemas.py` (add `WithList`, `WithSet`)
- Modify: `tests/unit/test_sequence.py` (add builder tests)

- [ ] **Step 1: Add `WithList` + `WithSet` to fixtures**

Append to `tests/fixtures/schemas.py`:

```python
class WithList(BaseModel):
    tags: list[str] = []
    counts: list[int] = []


class WithSet(BaseModel):
    flags: set[str] = set()
```

- [ ] **Step 2: Add builder tests**

Append to `tests/unit/test_sequence.py`:

```python
from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import IntNode
from tests.fixtures.schemas import WithList, WithSet


def test_list_builder_constructs_sequence_node() -> None:
    tree = build_form_tree(WithList)
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert tags.origin == "list"
    assert tags.item_type_name == "builtins.str"
    assert tags.items == []


def test_list_builder_pre_populates_from_existing() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["a", "b", "c"]})
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert len(tags.items) == 3
    assert all(isinstance(it, StringNode) for it in tags.items)
    assert [it.value for it in tags.items] == ["a", "b", "c"]


def test_list_of_int_dispatches_through_int_builder() -> None:
    tree = build_form_tree(WithList, existing={"counts": [1, 2, 3]})
    counts = tree.root.find("counts")
    assert isinstance(counts, SequenceNode)
    assert all(isinstance(it, IntNode) for it in counts.items)
    assert [it.value for it in counts.items] == [1, 2, 3]


def test_set_builder_constructs_sequence_node_origin_set() -> None:
    tree = build_form_tree(WithSet, existing={"flags": {"a", "b"}})
    flags = tree.root.find("flags")
    assert isinstance(flags, SequenceNode)
    assert flags.origin == "set"
    assert {it.value for it in flags.items} == {"a", "b"}


def test_list_to_instance_round_trip() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["x", "y"]})
    instance = tree.to_instance()
    assert instance.tags == ["x", "y"]


def test_set_to_instance_round_trip() -> None:
    tree = build_form_tree(WithSet, existing={"flags": {"x", "y"}})
    instance = tree.to_instance()
    assert instance.flags == {"x", "y"}
```

- [ ] **Step 3: Run the failing tests**

Run: `uv run pytest tests/unit/test_sequence.py -v`
Expected: collection or attribute errors (the new builders + module don't exist).

- [ ] **Step 4: Create `types/sequences.py`**

Create `src/pydantic_studio/types/sequences.py`:

```python
"""Builders for list / set / tuple containers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, get_args, get_origin

from pydantic_studio.tree.nodes import SequenceNode
from pydantic_studio.types.annotated import strip_annotated
from pydantic_studio.types.metadata import extract_constraints

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry


def _fq(t: Any) -> str:
    """Fully-qualified name of a type, for registry round-trip."""
    return f"{getattr(t, '__module__', 'builtins')}.{getattr(t, '__qualname__', repr(t))}"


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
    item_finfo = FieldInfo(annotation=item_type)
    item_builder = registry.find(item_type)
    items: list[Any] = []
    for i, v in enumerate(existing):
        child = item_builder.build(item_type, item_finfo, v)
        child.name = str(i)
        items.append(child)
    return items


class ListBuilder:
    """Builds a SequenceNode (origin='list') for ``list[T]`` annotations."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return get_origin(strip_annotated(type_)) is list

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> SequenceNode:
        unwrapped = strip_annotated(type_)
        args = get_args(unwrapped)
        item_type = args[0] if args else str
        c = extract_constraints(field_info)
        return SequenceNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            origin="list",
            items=_build_items(self._registry, item_type, existing, field_info),
            item_type_name=_fq(item_type),
            min_length=c.get("min_length"),
            max_length=c.get("max_length"),
        )


class SetBuilder:
    """Builds a SequenceNode (origin='set') for ``set[T]`` annotations."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return get_origin(strip_annotated(type_)) is set

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> SequenceNode:
        unwrapped = strip_annotated(type_)
        args = get_args(unwrapped)
        item_type = args[0] if args else str
        c = extract_constraints(field_info)
        return SequenceNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            origin="set",
            items=_build_items(self._registry, item_type, existing, field_info),
            item_type_name=_fq(item_type),
            min_length=c.get("min_length"),
            max_length=c.get("max_length"),
        )
```

- [ ] **Step 5: Register `ListBuilder` + `SetBuilder`**

In `src/pydantic_studio/tree/builder.py`, update imports + `default_registry`:

```python
from pydantic_studio.types.sequences import ListBuilder, SetBuilder
```

```python
        reg.register(StringBuilder())
        reg.register(IntBuilder())
        reg.register(FloatBuilder())
        reg.register(BoolBuilder())
        reg.register(DecimalBuilder())
        reg.register(EnumBuilder())
        reg.register(LiteralBuilder())
        reg.register(ListBuilder(reg))       # NEW
        reg.register(SetBuilder(reg))        # NEW
        reg.register(GroupBuilder(reg))
```

- [ ] **Step 6: Run the new tests — must pass**

Run: `uv run pytest tests/unit/test_sequence.py -v`
Expected: 11 passed (5 from T9 + 6 new).

- [ ] **Step 7: Run the full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/sequences.py src/pydantic_studio/tree/builder.py tests/fixtures/schemas.py tests/unit/test_sequence.py
git commit -m "feat(types): ListBuilder + SetBuilder for homogeneous sequences"
```

---

### Task 11: `TupleBuilder` (homogeneous variadic + fixed-length heterogeneous)

**Why:** `tuple[int, ...]` (variadic, homogeneous) reuses the SequenceNode shape with `origin="tuple"`. `tuple[int, str, bool]` (fixed-length, heterogeneous) needs `origin="tuple_fixed"` + `slot_type_names`. Each slot has its own item annotation.

**Files:**
- Modify: `src/pydantic_studio/types/sequences.py` (add `TupleBuilder`)
- Modify: `src/pydantic_studio/tree/builder.py` (register)
- Modify: `tests/fixtures/schemas.py` (add `WithTuple`, `WithFixedTuple`)
- Modify: `tests/unit/test_sequence.py` (add tuple tests)

- [ ] **Step 1: Add fixtures**

Append to `tests/fixtures/schemas.py`:

```python
class WithTuple(BaseModel):
    coords: tuple[int, ...] = ()


class WithFixedTuple(BaseModel):
    rgb: tuple[int, int, int] = (0, 0, 0)
    pair: tuple[str, int] = ("k", 0)
```

- [ ] **Step 2: Add tests**

Append to `tests/unit/test_sequence.py`:

```python
from tests.fixtures.schemas import WithFixedTuple, WithTuple


def test_variadic_tuple_uses_origin_tuple() -> None:
    tree = build_form_tree(WithTuple, existing={"coords": (1, 2, 3)})
    coords = tree.root.find("coords")
    assert isinstance(coords, SequenceNode)
    assert coords.origin == "tuple"
    assert [it.value for it in coords.items] == [1, 2, 3]


def test_fixed_tuple_uses_origin_tuple_fixed() -> None:
    tree = build_form_tree(WithFixedTuple, existing={"rgb": (10, 20, 30)})
    rgb = tree.root.find("rgb")
    assert isinstance(rgb, SequenceNode)
    assert rgb.origin == "tuple_fixed"
    assert rgb.slot_type_names == ["builtins.int", "builtins.int", "builtins.int"]
    assert [it.value for it in rgb.items] == [10, 20, 30]


def test_fixed_tuple_heterogeneous_slot_types() -> None:
    tree = build_form_tree(WithFixedTuple, existing={"pair": ("hello", 7)})
    pair = tree.root.find("pair")
    assert isinstance(pair, SequenceNode)
    assert pair.origin == "tuple_fixed"
    assert pair.slot_type_names == ["builtins.str", "builtins.int"]
    assert pair.items[0].value == "hello"
    assert pair.items[1].value == 7


def test_fixed_tuple_to_instance_round_trip() -> None:
    tree = build_form_tree(WithFixedTuple, existing={"rgb": (1, 2, 3)})
    instance = tree.to_instance()
    assert instance.rgb == (1, 2, 3)
```

- [ ] **Step 3: Run the failing tests**

Run: `uv run pytest tests/unit/test_sequence.py -v`
Expected: 4 new failures (`TupleBuilder` not registered).

- [ ] **Step 4: Add `TupleBuilder` to `types/sequences.py`**

Append to `src/pydantic_studio/types/sequences.py`:

```python
class TupleBuilder:
    """Builds a SequenceNode for ``tuple[T, ...]`` (variadic) and
    ``tuple[T1, T2, ...]`` (fixed-length heterogeneous)."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return get_origin(strip_annotated(type_)) is tuple

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> SequenceNode:
        from pydantic.fields import FieldInfo as _FI

        unwrapped = strip_annotated(type_)
        args = get_args(unwrapped)
        c = extract_constraints(field_info)

        if not args:
            # Plain ``tuple`` with no parameters — treat as ``tuple[Any, ...]``.
            return SequenceNode(
                name=field_info.alias or "<unnamed>",
                description=field_info.description,
                required=field_info.is_required(),
                origin="tuple",
                items=[],
                item_type_name=_fq(object),
                min_length=c.get("min_length"),
                max_length=c.get("max_length"),
            )

        is_variadic = len(args) == 2 and args[1] is Ellipsis
        if is_variadic:
            item_type = args[0]
            return SequenceNode(
                name=field_info.alias or "<unnamed>",
                description=field_info.description,
                required=field_info.is_required(),
                origin="tuple",
                items=_build_items(self._registry, item_type, existing, field_info),
                item_type_name=_fq(item_type),
                min_length=c.get("min_length"),
                max_length=c.get("max_length"),
            )

        # Fixed-length heterogeneous tuple: one slot per arg.
        items: list[Any] = []
        existing_seq = list(existing) if existing is not None else [None] * len(args)
        # Pad existing_seq to len(args) so missing slots become None children.
        while len(existing_seq) < len(args):
            existing_seq.append(None)
        for i, slot_type in enumerate(args):
            slot_finfo = _FI(annotation=slot_type)
            slot_builder = self._registry.find(slot_type)
            child = slot_builder.build(slot_type, slot_finfo, existing_seq[i])
            child.name = str(i)
            items.append(child)
        return SequenceNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            origin="tuple_fixed",
            items=items,
            item_type_name=None,
            slot_type_names=[_fq(a) for a in args],
            min_length=len(args),
            max_length=len(args),
        )
```

- [ ] **Step 5: Register `TupleBuilder`**

In `src/pydantic_studio/tree/builder.py`:

```python
from pydantic_studio.types.sequences import ListBuilder, SetBuilder, TupleBuilder
```

```python
        reg.register(ListBuilder(reg))
        reg.register(SetBuilder(reg))
        reg.register(TupleBuilder(reg))      # NEW
        reg.register(GroupBuilder(reg))
```

- [ ] **Step 6: Run the new tests — must pass**

Run: `uv run pytest tests/unit/test_sequence.py -v`
Expected: 15 passed.

- [ ] **Step 7: Run full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/types/sequences.py src/pydantic_studio/tree/builder.py tests/fixtures/schemas.py tests/unit/test_sequence.py
git commit -m "feat(types): TupleBuilder — variadic + fixed-length heterogeneous"
```

---

### Task 12: Sequence mutations — `add_item`, `remove_item`, `insert_item`, `move_item`

**Why:** Up to now `SequenceNode` is read-only — built from `existing`, never mutated. Renderers need explicit add/remove/move operations because the user can only interact with the form via discrete events ("clicked +", "dragged row").

**Design notes:**
- All four mutations push a snapshot before applying (same pattern as `set_value`).
- `add_item(path, value=None)` → append a default child to the sequence at `path`. The child's type comes from `SequenceNode.item_type_name` (or, for `tuple_fixed`, this raises — fixed-length tuples can't grow).
- `remove_item(path, index)` → remove and re-number remaining items.
- `insert_item(path, index, value=None)` → insert at index.
- `move_item(path, from_index, to_index)` → reorder (no rebuild).
- Item-type lookup: take the FQ name and walk `sys.modules` (same pattern as `GroupNode.schema_class`). Fall back to a sensible default for builtins (e.g. `builtins.str` → `str`).

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` (add four methods on `FormTree`)
- Modify: `tests/unit/test_sequence.py` (add mutation tests)

- [ ] **Step 1: Add mutation tests**

Append to `tests/unit/test_sequence.py`:

```python
def test_add_item_appends_default_child() -> None:
    tree = build_form_tree(WithList)
    result = tree.add_item("tags")
    assert result.ok is True
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert len(tags.items) == 1
    assert isinstance(tags.items[0], StringNode)
    assert tags.items[0].name == "0"


def test_add_item_with_explicit_value() -> None:
    tree = build_form_tree(WithList)
    tree.add_item("tags", "hello")
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert tags.items[0].value == "hello"


def test_remove_item_renumbers() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["a", "b", "c"]})
    tree.remove_item("tags", 1)
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert [it.value for it in tags.items] == ["a", "c"]
    assert [it.name for it in tags.items] == ["0", "1"]


def test_insert_item_at_index() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["a", "c"]})
    tree.insert_item("tags", 1, "b")
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert [it.value for it in tags.items] == ["a", "b", "c"]


def test_move_item_reorders() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["a", "b", "c"]})
    tree.move_item("tags", 0, 2)
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert [it.value for it in tags.items] == ["b", "c", "a"]


def test_add_item_pushes_snapshot_so_undo_works() -> None:
    tree = build_form_tree(WithList)
    tree.add_item("tags", "x")
    assert tree.undo() is True
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert tags.items == []


def test_add_item_fails_on_fixed_tuple() -> None:
    tree = build_form_tree(WithFixedTuple)
    result = tree.add_item("rgb")
    assert result.ok is False
    assert any("fixed-length" in e for e in result.errors)
```

- [ ] **Step 2: Run failing tests**

Run: `uv run pytest tests/unit/test_sequence.py -v`
Expected: 7 new failures (mutations don't exist).

- [ ] **Step 3: Add a `_resolve_type_name` helper to `tree/nodes.py`**

Near the top of `nodes.py`, add (it'll be used by mutation methods and later by UnionBuilder):

```python
def _resolve_type_name(name: str) -> Any:
    """Look up a fully-qualified type name (``module.Qualname``).

    Handles ``builtins.str`` etc. specially so unit tests don't need to
    import builtins. Raises ValueError on miss with a diagnostic message.
    """
    parts = name.rsplit(".", 1)
    if len(parts) != 2:
        msg = f"malformed type name {name!r} (expected 'module.Qualname')"
        raise ValueError(msg)
    module_name, qualname = parts
    if module_name == "builtins":
        builtin = __builtins__.get(qualname) if isinstance(__builtins__, dict) else getattr(__builtins__, qualname, None)
        if builtin is None:
            msg = f"unknown builtin {qualname!r}"
            raise ValueError(msg)
        return builtin
    module = sys.modules.get(module_name)
    if module is None:
        msg = f"module {module_name!r} not in sys.modules — import it before resolving {name!r}"
        raise ValueError(msg)
    obj: Any = module
    for part in qualname.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            msg = f"{module_name!r} has no {part!r} (resolving {name!r})"
            raise ValueError(msg)
    return obj
```

- [ ] **Step 4: Add the four sequence mutations to `FormTree`**

In `nodes.py`, append to the `FormTree` class:

```python
    def _walk_to_sequence(self, path: str) -> SequenceNode:
        """Resolve ``path`` and return the SequenceNode at that location."""
        from pydantic_studio.tree.paths import Path as _Path

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            msg = "empty path"
            raise ValueError(msg)
        node: Any = self.root
        for seg in path_obj.segments:
            if isinstance(node, GroupNode) and isinstance(seg, str):
                child = node.find(seg)
                if child is None:
                    msg = f"no field named {seg!r}"
                    raise KeyError(msg)
                node = child
            else:
                msg = f"cannot navigate {seg!r}"
                raise KeyError(msg)
        if not isinstance(node, SequenceNode):
            msg = f"{path!r} is not a SequenceNode"
            raise TypeError(msg)
        return node

    def add_item(self, path: str, value: Any = None) -> ValidationResult:
        """Append a default child to the SequenceNode at ``path``."""
        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        seq = self._walk_to_sequence(path)
        if seq.origin == "tuple_fixed":
            return ValidationResult.fail(
                ["cannot add to a fixed-length tuple"]
            )
        self._push_snapshot(_snap.take(self.root))
        if seq.item_type_name is None:
            return ValidationResult.fail(["sequence has no item_type_name"])
        from pydantic.fields import FieldInfo

        item_type = _resolve_type_name(seq.item_type_name)
        builder = default_registry().find(item_type)
        child = builder.build(item_type, FieldInfo(annotation=item_type), value)
        child.name = str(len(seq.items))
        seq.items = [*seq.items, child]
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def remove_item(self, path: str, index: int) -> ValidationResult:
        from pydantic_studio.tree import snapshots as _snap

        seq = self._walk_to_sequence(path)
        if not (0 <= index < len(seq.items)):
            return ValidationResult.fail([f"index {index} out of range"])
        self._push_snapshot(_snap.take(self.root))
        new_items = [it for i, it in enumerate(seq.items) if i != index]
        for i, it in enumerate(new_items):
            it.name = str(i)
        seq.items = new_items
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def insert_item(self, path: str, index: int, value: Any = None) -> ValidationResult:
        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        seq = self._walk_to_sequence(path)
        if seq.origin == "tuple_fixed":
            return ValidationResult.fail(["cannot insert into a fixed-length tuple"])
        if not (0 <= index <= len(seq.items)):
            return ValidationResult.fail([f"index {index} out of range"])
        self._push_snapshot(_snap.take(self.root))
        if seq.item_type_name is None:
            return ValidationResult.fail(["sequence has no item_type_name"])
        from pydantic.fields import FieldInfo

        item_type = _resolve_type_name(seq.item_type_name)
        builder = default_registry().find(item_type)
        child = builder.build(item_type, FieldInfo(annotation=item_type), value)
        new_items = [*seq.items[:index], child, *seq.items[index:]]
        for i, it in enumerate(new_items):
            it.name = str(i)
        seq.items = new_items
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def move_item(self, path: str, from_index: int, to_index: int) -> ValidationResult:
        from pydantic_studio.tree import snapshots as _snap

        seq = self._walk_to_sequence(path)
        if not (0 <= from_index < len(seq.items)):
            return ValidationResult.fail([f"from_index {from_index} out of range"])
        if not (0 <= to_index < len(seq.items)):
            return ValidationResult.fail([f"to_index {to_index} out of range"])
        self._push_snapshot(_snap.take(self.root))
        items = list(seq.items)
        item = items.pop(from_index)
        items.insert(to_index, item)
        for i, it in enumerate(items):
            it.name = str(i)
        seq.items = items
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()
```

- [ ] **Step 5: Run the tests — must pass**

Run: `uv run pytest tests/unit/test_sequence.py -v`
Expected: 22 passed (15 prior + 7 new).

- [ ] **Step 6: Run full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py tests/unit/test_sequence.py
git commit -m "feat(tree): sequence mutations — add/remove/insert/move_item"
```

---

### Task 13: `MappingNode` + `DictBuilder` + entry mutations

**Why:** `dict[K, V]` is the second container family. The node holds an ordered list of `(key_node, value_node)` pairs — preserving insertion order matters for config files (YAML round-trip).

**Design notes:**
- `entries: list[tuple[AnyNode, AnyNode]]` keeps the pair structure. Tuple discrimination inside Pydantic discriminated unions works as long as we keep the outer container shape identical for serialization.
- `key_type_name` + `value_type_name` enable rebuild on `add_entry`.
- Mutations: `add_entry(path, key, value=None)`, `remove_entry(path, index)`, `rename_key(path, index, new_key)`.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` (`MappingNode`, extend `AnyNode`, add three mutations)
- Create: `src/pydantic_studio/types/mapping.py`
- Modify: `src/pydantic_studio/tree/builder.py` (register)
- Modify: `tests/fixtures/schemas.py` (add `WithDict`)
- Create: `tests/unit/test_mapping.py`

- [ ] **Step 1: Add `WithDict` fixture**

Append to `tests/fixtures/schemas.py`:

```python
class WithDict(BaseModel):
    settings: dict[str, int] = {}
    labels: dict[str, str] = {}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_mapping.py`:

```python
"""MappingNode + DictBuilder + entry mutations."""

from __future__ import annotations

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import IntNode, MappingNode, StringNode
from tests.fixtures.schemas import WithDict


def test_dict_builder_constructs_mapping_node() -> None:
    tree = build_form_tree(WithDict)
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert settings.key_type_name == "builtins.str"
    assert settings.value_type_name == "builtins.int"
    assert settings.entries == []


def test_dict_pre_populates_from_existing() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"timeout": 30, "retries": 3}}
    )
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert len(settings.entries) == 2
    assert all(isinstance(k, StringNode) for k, _ in settings.entries)
    assert all(isinstance(v, IntNode) for _, v in settings.entries)
    assert {(k.value, v.value) for k, v in settings.entries} == {
        ("timeout", 30),
        ("retries", 3),
    }


def test_dict_to_python_returns_dict() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"timeout": 30}}
    )
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert settings.to_python() == {"timeout": 30}


def test_dict_to_instance_round_trip() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"a": 1, "b": 2}}
    )
    instance = tree.to_instance()
    assert instance.settings == {"a": 1, "b": 2}


def test_add_entry_appends() -> None:
    tree = build_form_tree(WithDict)
    result = tree.add_entry("settings", "timeout", 30)
    assert result.ok is True
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert len(settings.entries) == 1
    k, v = settings.entries[0]
    assert k.value == "timeout"
    assert v.value == 30


def test_remove_entry() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"a": 1, "b": 2, "c": 3}}
    )
    tree.remove_entry("settings", 1)
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert {(k.value, v.value) for k, v in settings.entries} == {
        ("a", 1),
        ("c", 3),
    }


def test_rename_key() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"old": 1}}
    )
    tree.rename_key("settings", 0, "new")
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    k, v = settings.entries[0]
    assert k.value == "new"
    assert v.value == 1


def test_add_entry_pushes_snapshot_for_undo() -> None:
    tree = build_form_tree(WithDict)
    tree.add_entry("settings", "k", 1)
    assert tree.undo() is True
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert settings.entries == []
```

- [ ] **Step 3: Run failing tests**

Run: `uv run pytest tests/unit/test_mapping.py -v`
Expected: collection errors (`MappingNode`, `add_entry` etc. don't exist).

- [ ] **Step 4: Add `MappingNode` to `tree/nodes.py`**

Below `SequenceNode`, add:

```python
class MappingNode(FormNode):
    """Container for ``dict[K, V]`` values.

    ``entries`` preserves insertion order; each entry is a (key_node,
    value_node) pair built from the corresponding annotations.
    """

    kind: Literal["mapping"] = "mapping"
    entries: "list[tuple[AnyNode, AnyNode]]" = []
    key_type_name: str
    value_type_name: str
    min_length: int | None = None
    max_length: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> dict[Any, Any]:
        return {k.to_python(): v.to_python() for k, v in self.entries}

    def validate_value(self, value: Any) -> tuple[str, ...]:
        return ()  # whole-mapping replacement deferred to v0.2
```

Extend `AnyNode`:

```python
AnyNode = Annotated[
    StringNode
    | IntNode
    | FloatNode
    | BoolNode
    | DecimalNode
    | EnumNode
    | LiteralNode
    | SequenceNode
    | MappingNode
    | GroupNode,
    Discriminator("kind"),
]
```

Add `MappingNode.model_rebuild()` after the existing rebuilds:

```python
GroupNode.model_rebuild()
SequenceNode.model_rebuild()
MappingNode.model_rebuild()
```

- [ ] **Step 5: Create `types/mapping.py`**

Create `src/pydantic_studio/types/mapping.py`:

```python
"""Builder for ``dict[K, V]`` containers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, get_args, get_origin

from pydantic_studio.tree.nodes import MappingNode
from pydantic_studio.types.annotated import strip_annotated
from pydantic_studio.types.metadata import extract_constraints

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry


def _fq(t: Any) -> str:
    return f"{getattr(t, '__module__', 'builtins')}.{getattr(t, '__qualname__', repr(t))}"


class DictBuilder:
    """Builds a MappingNode for ``dict[K, V]`` annotations."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return get_origin(strip_annotated(type_)) is dict

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> MappingNode:
        from pydantic.fields import FieldInfo as _FI

        unwrapped = strip_annotated(type_)
        args = get_args(unwrapped)
        key_type = args[0] if len(args) >= 1 else str
        value_type = args[1] if len(args) >= 2 else str
        c = extract_constraints(field_info)

        entries: list[tuple[Any, Any]] = []
        if isinstance(existing, dict):
            key_builder = self._registry.find(key_type)
            value_builder = self._registry.find(value_type)
            key_finfo = _FI(annotation=key_type)
            value_finfo = _FI(annotation=value_type)
            for raw_key, raw_value in existing.items():
                k_node = key_builder.build(key_type, key_finfo, raw_key)
                v_node = value_builder.build(value_type, value_finfo, raw_value)
                k_node.name = "key"
                v_node.name = "value"
                entries.append((k_node, v_node))

        return MappingNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            entries=entries,
            key_type_name=_fq(key_type),
            value_type_name=_fq(value_type),
            min_length=c.get("min_length"),
            max_length=c.get("max_length"),
        )
```

- [ ] **Step 6: Register `DictBuilder`**

In `src/pydantic_studio/tree/builder.py`:

```python
from pydantic_studio.types.mapping import DictBuilder
```

```python
        reg.register(ListBuilder(reg))
        reg.register(SetBuilder(reg))
        reg.register(TupleBuilder(reg))
        reg.register(DictBuilder(reg))       # NEW
        reg.register(GroupBuilder(reg))
```

- [ ] **Step 7: Add mapping mutations to `FormTree`**

Append to `FormTree` in `nodes.py`:

```python
    def _walk_to_mapping(self, path: str) -> MappingNode:
        from pydantic_studio.tree.paths import Path as _Path

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            msg = "empty path"
            raise ValueError(msg)
        node: Any = self.root
        for seg in path_obj.segments:
            if isinstance(node, GroupNode) and isinstance(seg, str):
                child = node.find(seg)
                if child is None:
                    msg = f"no field named {seg!r}"
                    raise KeyError(msg)
                node = child
            else:
                msg = f"cannot navigate {seg!r}"
                raise KeyError(msg)
        if not isinstance(node, MappingNode):
            msg = f"{path!r} is not a MappingNode"
            raise TypeError(msg)
        return node

    def add_entry(
        self, path: str, key: Any, value: Any = None
    ) -> ValidationResult:
        """Append a (key, value) entry to the MappingNode at ``path``."""
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        mp = self._walk_to_mapping(path)
        self._push_snapshot(_snap.take(self.root))
        key_type = _resolve_type_name(mp.key_type_name)
        value_type = _resolve_type_name(mp.value_type_name)
        reg = default_registry()
        k_builder = reg.find(key_type)
        v_builder = reg.find(value_type)
        k_node = k_builder.build(key_type, FieldInfo(annotation=key_type), key)
        v_node = v_builder.build(value_type, FieldInfo(annotation=value_type), value)
        k_node.name = "key"
        v_node.name = "value"
        mp.entries = [*mp.entries, (k_node, v_node)]
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def remove_entry(self, path: str, index: int) -> ValidationResult:
        from pydantic_studio.tree import snapshots as _snap

        mp = self._walk_to_mapping(path)
        if not (0 <= index < len(mp.entries)):
            return ValidationResult.fail([f"index {index} out of range"])
        self._push_snapshot(_snap.take(self.root))
        mp.entries = [e for i, e in enumerate(mp.entries) if i != index]
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def rename_key(
        self, path: str, index: int, new_key: Any
    ) -> ValidationResult:
        from pydantic_studio.tree import snapshots as _snap

        mp = self._walk_to_mapping(path)
        if not (0 <= index < len(mp.entries)):
            return ValidationResult.fail([f"index {index} out of range"])
        self._push_snapshot(_snap.take(self.root))
        k_node, v_node = mp.entries[index]
        errors = k_node.validate_value(new_key)
        if errors:
            return ValidationResult.fail(list(errors))
        k_node.value = new_key
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()
```

- [ ] **Step 8: Run the tests — must pass**

Run: `uv run pytest tests/unit/test_mapping.py -v`
Expected: 8 passed.

- [ ] **Step 9: Run full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 10: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py src/pydantic_studio/types/mapping.py src/pydantic_studio/tree/builder.py tests/fixtures/schemas.py tests/unit/test_mapping.py
git commit -m "feat(types): MappingNode + DictBuilder + add/remove/rename entry mutations"
```

---

### Task 14: `UnionNode` + `UnionBuilder` (incl. Optional unwrap)

**Why:** Discriminated and undiscriminated unions are common (`SqliteCfg | PostgresCfg`, `int | str`, `Address | None`). Optional types are unions with `None` — for those, we unwrap to the non-None inner type and just lower `required` to False, **no UnionNode is created**. True unions (≥ 2 non-None variants) get a `UnionNode` with selected-variant state.

**Design notes:**
- `UnionBuilder.matches`: true for any union type **except** an Optional with exactly one non-None variant (those are handled inline by demoting `required`).
- `variant_type_names: list[str]` — FQ name of each variant. The selected node is built lazily via the registry on `select_variant`.
- `selected_index: int | None` and `selected: AnyNode | None`. Both serializable (selected uses the discriminated union).
- `to_python` returns `selected.to_python()` if a variant is selected, else None.
- For `T | None` where the user has not yet picked, `selected` stays `None` — that's fine because the field is Optional.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` (add `UnionNode`, extend `AnyNode`)
- Create: `src/pydantic_studio/types/unions.py`
- Modify: `src/pydantic_studio/tree/builder.py` (register; place **before** `GroupBuilder` so unions are detected first)
- Modify: `tests/fixtures/schemas.py` (add `WithUnion`, `WithOptional`)
- Create: `tests/unit/test_union.py`

- [ ] **Step 1: Add fixtures**

Append to `tests/fixtures/schemas.py`:

```python
class WithUnion(BaseModel):
    value: int | str = 0


class WithOptional(BaseModel):
    nickname: str | None = None
    age: int | None = None
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_union.py`:

```python
"""UnionNode + UnionBuilder coverage. select_variant lives in T15."""

from __future__ import annotations

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import IntNode, StringNode, UnionNode
from tests.fixtures.schemas import WithOptional, WithUnion


def test_optional_demotes_to_inner_type_node() -> None:
    """``str | None`` becomes a StringNode with required=False, NOT a UnionNode."""
    tree = build_form_tree(WithOptional)
    nick = tree.root.find("nickname")
    assert isinstance(nick, StringNode)
    assert nick.required is False
    age = tree.root.find("age")
    assert isinstance(age, IntNode)
    assert age.required is False


def test_true_union_becomes_union_node() -> None:
    tree = build_form_tree(WithUnion)
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.variant_type_names == ["builtins.int", "builtins.str"]


def test_union_pre_populated_from_existing_int() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 42})
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 0
    assert isinstance(val.selected, IntNode)
    assert val.selected.value == 42


def test_union_pre_populated_from_existing_str() -> None:
    tree = build_form_tree(WithUnion, existing={"value": "hi"})
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 1
    assert isinstance(val.selected, StringNode)
    assert val.selected.value == "hi"


def test_union_to_python_returns_inner_value() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 7})
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.to_python() == 7


def test_union_to_instance_round_trip() -> None:
    tree = build_form_tree(WithUnion, existing={"value": "hello"})
    instance = tree.to_instance()
    assert instance.value == "hello"
```

- [ ] **Step 3: Run failing tests**

Run: `uv run pytest tests/unit/test_union.py -v`
Expected: collection errors (`UnionNode` doesn't exist; UnionBuilder isn't registered).

- [ ] **Step 4: Add `UnionNode` to `tree/nodes.py`**

Below `MappingNode`, add:

```python
class UnionNode(FormNode):
    """Holds a value that could be one of several types.

    The user picks a variant; the node's ``selected`` carries the chosen
    variant's child node. ``variant_type_names`` records all candidate
    types for ``select_variant`` to rebuild on switch.
    """

    kind: Literal["union"] = "union"
    variant_type_names: list[str]
    selected_index: int | None = None
    selected: "AnyNode | None" = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        if self.selected is None:
            return None
        return self.selected.to_python()

    def validate_value(self, value: Any) -> tuple[str, ...]:
        # Per-leaf validation happens on the inner node; the union itself
        # accepts any value the user is staging.
        return ()
```

Extend `AnyNode`:

```python
AnyNode = Annotated[
    StringNode
    | IntNode
    | FloatNode
    | BoolNode
    | DecimalNode
    | EnumNode
    | LiteralNode
    | SequenceNode
    | MappingNode
    | UnionNode
    | GroupNode,
    Discriminator("kind"),
]
```

Add rebuild:

```python
GroupNode.model_rebuild()
SequenceNode.model_rebuild()
MappingNode.model_rebuild()
UnionNode.model_rebuild()
```

- [ ] **Step 5: Create `types/unions.py`**

Create `src/pydantic_studio/types/unions.py`:

```python
"""Builder for union and Optional annotations.

Optional unions (T | None) are demoted: we strip None and return whatever
the inner builder produces, with ``required=False``. True multi-variant
unions become a UnionNode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import UnionNode
from pydantic_studio.types.annotated import (
    get_optional_inner,
    get_union_args,
    is_optional_type,
    is_union_type,
    strip_annotated,
)

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry


def _fq(t: Any) -> str:
    return f"{getattr(t, '__module__', 'builtins')}.{getattr(t, '__qualname__', repr(t))}"


class UnionBuilder:
    """Builds either a UnionNode (true union) or delegates to the inner
    builder (Optional with one non-None variant)."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return is_union_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic.fields import FieldInfo as _FI

        unwrapped = strip_annotated(type_)
        non_none_args = tuple(t for t in get_union_args(unwrapped) if t is not type(None))

        # Optional[T] with a single non-None variant → just the inner builder
        # with required=False.
        if is_optional_type(unwrapped) and len(non_none_args) == 1:
            inner_type = non_none_args[0]
            inner_builder = self._registry.find(inner_type)
            inner = inner_builder.build(inner_type, field_info, existing)
            inner.required = False  # Optional implies not required
            return inner

        # True union: build a UnionNode. If existing matches one variant by
        # isinstance, pre-select that variant.
        variants = list(non_none_args) if not is_optional_type(unwrapped) else list(non_none_args)
        selected_index: int | None = None
        selected: Any = None
        if existing is not None:
            for i, v_type in enumerate(variants):
                try:
                    if isinstance(existing, v_type):
                        selected_index = i
                        v_finfo = _FI(annotation=v_type)
                        v_builder = self._registry.find(v_type)
                        selected = v_builder.build(v_type, v_finfo, existing)
                        break
                except TypeError:
                    continue

        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None

        return UnionNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            variant_type_names=[_fq(v) for v in variants],
            selected_index=selected_index,
            selected=selected,
        )
```

- [ ] **Step 6: Register `UnionBuilder`**

In `src/pydantic_studio/tree/builder.py`:

```python
from pydantic_studio.types.unions import UnionBuilder
```

Register **before** `GroupBuilder` (unions over BaseModels would otherwise route to GroupBuilder):

```python
        reg.register(ListBuilder(reg))
        reg.register(SetBuilder(reg))
        reg.register(TupleBuilder(reg))
        reg.register(DictBuilder(reg))
        reg.register(UnionBuilder(reg))      # NEW
        reg.register(GroupBuilder(reg))
```

- [ ] **Step 7: Run the tests — must pass**

Run: `uv run pytest tests/unit/test_union.py -v`
Expected: 6 passed.

- [ ] **Step 8: Run full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py src/pydantic_studio/types/unions.py src/pydantic_studio/tree/builder.py tests/fixtures/schemas.py tests/unit/test_union.py
git commit -m "feat(types): UnionNode + UnionBuilder (Optional demotion + true unions)"
```

---

### Task 15: `select_variant` mutation

**Why:** The user needs to switch which variant of a UnionNode is active. Switching wipes the previous variant's value (a fresh node is built) but keeps the snapshot history, so undo restores it.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` (`FormTree.select_variant`)
- Modify: `tests/unit/test_union.py` (add tests)

- [ ] **Step 1: Add tests**

Append to `tests/unit/test_union.py`:

```python
def test_select_variant_switches_to_str() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 42})
    result = tree.select_variant("value", 1)  # switch to str
    assert result.ok is True
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 1
    assert isinstance(val.selected, StringNode)
    assert val.selected.value is None  # fresh; previous int 42 is discarded


def test_select_variant_undo_restores() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 42})
    tree.select_variant("value", 1)
    assert tree.undo() is True
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 0
    assert isinstance(val.selected, IntNode)
    assert val.selected.value == 42


def test_select_variant_out_of_range_returns_error() -> None:
    tree = build_form_tree(WithUnion)
    result = tree.select_variant("value", 99)
    assert result.ok is False
    assert any("out of range" in e for e in result.errors)


def test_select_variant_with_seed_value() -> None:
    """Optional second arg lets caller seed the new variant's value."""
    tree = build_form_tree(WithUnion)
    result = tree.select_variant("value", 1, seed="seeded")
    assert result.ok is True
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected.value == "seeded"
```

- [ ] **Step 2: Run failing tests**

Run: `uv run pytest tests/unit/test_union.py -v`
Expected: 4 new failures.

- [ ] **Step 3: Add `select_variant` to `FormTree`**

Append to `FormTree`:

```python
    def _walk_to_union(self, path: str) -> UnionNode:
        from pydantic_studio.tree.paths import Path as _Path

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            msg = "empty path"
            raise ValueError(msg)
        node: Any = self.root
        for seg in path_obj.segments:
            if isinstance(node, GroupNode) and isinstance(seg, str):
                child = node.find(seg)
                if child is None:
                    msg = f"no field named {seg!r}"
                    raise KeyError(msg)
                node = child
            else:
                msg = f"cannot navigate {seg!r}"
                raise KeyError(msg)
        if not isinstance(node, UnionNode):
            msg = f"{path!r} is not a UnionNode"
            raise TypeError(msg)
        return node

    def select_variant(
        self, path: str, variant_index: int, seed: Any = None
    ) -> ValidationResult:
        """Switch the UnionNode at ``path`` to its ``variant_index``-th variant.

        If ``seed`` is provided, the freshly-built variant is initialized
        with that value (otherwise its value is None / default).
        """
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        union = self._walk_to_union(path)
        if not (0 <= variant_index < len(union.variant_type_names)):
            return ValidationResult.fail(
                [f"variant index {variant_index} out of range "
                 f"(0..{len(union.variant_type_names) - 1})"]
            )
        self._push_snapshot(_snap.take(self.root))
        v_type = _resolve_type_name(union.variant_type_names[variant_index])
        builder = default_registry().find(v_type)
        new_selected = builder.build(v_type, FieldInfo(annotation=v_type), seed)
        union.selected_index = variant_index
        union.selected = new_selected
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()
```

- [ ] **Step 4: Run the new tests — must pass**

Run: `uv run pytest tests/unit/test_union.py -v`
Expected: 10 passed (6 prior + 4 new).

- [ ] **Step 5: Run full suite + lint + types**

```
uv run pytest -q
uv run ruff check .
uv run pyright src tests
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py tests/unit/test_union.py
git commit -m "feat(tree): select_variant mutation for UnionNode"
```

---

### Task 16: Public API surface + comprehensive smoke test + README update

**Why:** All new node types and builders should be importable from `pydantic_studio` without diving into submodules. A comprehensive smoke test exercises the full Phase 2 type matrix end-to-end so we'd catch any regression in a single run.

**Files:**
- Modify: `src/pydantic_studio/__init__.py` (re-export new public names)
- Modify: `tests/unit/test_smoke.py` (extend or replace with kitchen-sink schema)
- Modify: `README.md` (Phase 2 example covering enum / list / dict / union)

- [ ] **Step 1: Re-export from `pydantic_studio/__init__.py`**

Replace the body of `src/pydantic_studio/__init__.py` with:

```python
"""pydantic-studio: interactive editor for Pydantic models."""

from __future__ import annotations

__version__ = "0.0.1"

from pydantic_studio.exceptions import (
    CancelledByUser,
    NoBuilderError,
    PydanticStudioError,
    ValidationFailedError,
)
from pydantic_studio.tree.builder import (
    NodeBuilder,
    build_form_tree,
    default_registry,
    reset_default_registry,
)
from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    EnumNode,
    FloatNode,
    FormNode,
    FormTree,
    GroupNode,
    IntNode,
    LiteralNode,
    MappingNode,
    SequenceNode,
    StringNode,
    UnionNode,
)
from pydantic_studio.tree.validation import ValidationResult


def register_builder(builder: NodeBuilder) -> None:
    """Register a custom NodeBuilder into the global default registry.

    The new builder is *prepended*, so it overrides any prior builder
    that matches the same type.
    """
    default_registry().register(builder)


__all__ = [
    "BoolNode",
    "CancelledByUser",
    "DecimalNode",
    "EnumNode",
    "FloatNode",
    "FormNode",
    "FormTree",
    "GroupNode",
    "IntNode",
    "LiteralNode",
    "MappingNode",
    "NoBuilderError",
    "NodeBuilder",
    "PydanticStudioError",
    "SequenceNode",
    "StringNode",
    "UnionNode",
    "ValidationFailedError",
    "ValidationResult",
    "__version__",
    "build_form_tree",
    "register_builder",
    "reset_default_registry",
]
```

- [ ] **Step 2: Extend the smoke test**

Replace `tests/unit/test_smoke.py` with a kitchen-sink test:

```python
"""Smoke test covering the full Phase 2 type matrix in one schema."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

from annotated_types import Ge
from pydantic import BaseModel, Field

from pydantic_studio import (
    EnumNode,
    GroupNode,
    IntNode,
    LiteralNode,
    MappingNode,
    SequenceNode,
    StringNode,
    UnionNode,
    build_form_tree,
)


class Tier(Enum):
    BASIC = "basic"
    PRO = "pro"


class Sub(BaseModel):
    label: str
    weight: Decimal = Decimal("1.00")


class Kitchen(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    age: Annotated[int, Ge(0)] = 0
    tier: Tier = Tier.BASIC
    log_level: Literal["debug", "info", "warn"] = "info"
    tags: list[str] = []
    flags: set[str] = set()
    coords: tuple[int, int] = (0, 0)
    settings: dict[str, int] = {}
    sub: Sub = Sub(label="default")
    primary: int | str = 0
    nickname: str | None = None


def test_kitchen_schema_builds_with_correct_node_types() -> None:
    tree = build_form_tree(Kitchen)
    assert isinstance(tree.root.find("name"), StringNode)
    assert isinstance(tree.root.find("age"), IntNode)
    assert isinstance(tree.root.find("tier"), EnumNode)
    assert isinstance(tree.root.find("log_level"), LiteralNode)
    assert isinstance(tree.root.find("tags"), SequenceNode)
    assert isinstance(tree.root.find("flags"), SequenceNode)
    assert isinstance(tree.root.find("coords"), SequenceNode)
    assert isinstance(tree.root.find("settings"), MappingNode)
    assert isinstance(tree.root.find("sub"), GroupNode)
    assert isinstance(tree.root.find("primary"), UnionNode)
    # Optional[str] demotes to StringNode with required=False.
    nick = tree.root.find("nickname")
    assert isinstance(nick, StringNode)
    assert nick.required is False


def test_kitchen_constraint_passes_through_to_nodes() -> None:
    tree = build_form_tree(Kitchen)
    name = tree.root.find("name")
    assert isinstance(name, StringNode)
    assert name.min_length == 1
    assert name.max_length == 50
    age = tree.root.find("age")
    assert isinstance(age, IntNode)
    assert age.ge == 0


def test_kitchen_round_trip_to_instance() -> None:
    tree = build_form_tree(
        Kitchen,
        existing={
            "name": "alice",
            "age": 30,
            "tier": Tier.PRO,
            "log_level": "warn",
            "tags": ["x", "y"],
            "flags": {"a"},
            "coords": (1, 2),
            "settings": {"k": 1},
            "sub": {"label": "L"},
            "primary": "hello",
            "nickname": "ali",
        },
    )
    instance = tree.to_instance()
    assert instance.name == "alice"
    assert instance.age == 30
    assert instance.tier == Tier.PRO
    assert instance.log_level == "warn"
    assert instance.tags == ["x", "y"]
    assert instance.flags == {"a"}
    assert instance.coords == (1, 2)
    assert instance.settings == {"k": 1}
    assert instance.sub.label == "L"
    assert instance.primary == "hello"
    assert instance.nickname == "ali"


def test_kitchen_mutation_smoke() -> None:
    """Each major mutation runs and round-trips under undo/redo."""
    tree = build_form_tree(Kitchen)
    tree.set_value("name", "bob")
    tree.add_item("tags", "first")
    tree.add_entry("settings", "k", 42)
    tree.select_variant("primary", 1, seed="from-union")
    instance = tree.to_instance()
    assert instance.name == "bob"
    assert instance.tags == ["first"]
    assert instance.settings == {"k": 42}
    assert instance.primary == "from-union"
    # Walk all four mutations back.
    for _ in range(4):
        assert tree.undo() is True
```

- [ ] **Step 3: Update README**

Open `README.md` and replace the Phase 1 example with one that exercises the new types. Keep it short — README should fit on one screen:

```markdown
# pydantic-studio

Interactive editor for Pydantic models. Generate and edit `config.yaml` /
`config.toml` / `config.json` against a schema.

## Status

Phase 2 (Type Coverage) — alpha. Programmatic API only; CLI / TUI / Web
coming in later phases.

## Quick example (programmatic)

```python
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree


class Tier(Enum):
    BASIC = "basic"
    PRO = "pro"


class Settings(BaseModel):
    name: str = Field(min_length=1)
    tier: Tier = Tier.BASIC
    log_level: Literal["debug", "info", "warn"] = "info"
    tags: list[str] = []
    settings: dict[str, int] = {}
    primary: int | str = 0
    nickname: str | None = None


tree = build_form_tree(Settings, existing={"name": "alice"})
result = tree.set_value("name", "bob")
assert result.ok

tree.add_item("tags", "first-tag")
tree.add_entry("settings", "timeout", 30)
tree.select_variant("primary", 1, seed="hello")

instance = tree.to_instance()  # Settings(name='bob', tags=['first-tag'], ...)
```

## Supported types

Phase 2 adds: `Enum`, `Literal[...]`, `list[T]` / `set[T]` / `tuple[T, ...]`,
fixed-length `tuple[T1, T2, ...]`, `dict[K, V]`, true unions (`int | str`),
and Optional (`T | None`). Pydantic v2 constrained types (`constr`,
`conint`, ...) are supported via the metadata extractor.
```

- [ ] **Step 4: Run the smoke test — must pass**

Run: `uv run pytest tests/unit/test_smoke.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all Phase 2 tests green (estimate ~60+ new tests added across T1-T16, total ~160).

- [ ] **Step 6: Lint + types**

```
uv run ruff check .
uv run pyright src tests
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/pydantic_studio/__init__.py tests/unit/test_smoke.py README.md
git commit -m "feat: phase-2 public API + comprehensive smoke test + README update"
```

---

## Phase 2 wrap-up

After all 16 tasks land:

1. Verify on the merged branch: `uv run pytest -q && uv run ruff check . && uv run pyright src tests`.
2. Merge to `main` with `--no-ff` (matches Phase 1's strategy):
   ```
   git checkout main
   git merge --no-ff feature/phase-2-type-coverage -m "merge: Phase 2 — Type coverage (T1-T16)"
   ```
3. Tag: `git tag v0.0.2-phase-2`.
4. Do **not** push (per user's standing instruction — local commits + merge only).

---

## Self-review checklist

After writing this plan I re-read the spec section 5 and section 14, and the Phase 1 reviewer's priority list. Result of the check:

**Spec coverage (section 5.1 + 14):**
- ✓ Form Tree extension with EnumNode/LiteralNode/SequenceNode/MappingNode/UnionNode (T7-T15)
- ✓ Annotated unwrapping (T5) — vendored predicates from promptantic
- ✓ Constrained types via metadata extractor (T6) — no separate task needed because Pydantic v2 desugars to Annotated
- ✓ Sequence/Mapping/Union mutations (T12, T13, T15) — spec section 5.3 lists `add_item`, `remove_item`, `select_variant`; we add `insert_item`, `move_item`, `add_entry`, `remove_entry`, `rename_key` as obvious extensions
- ✗ Datetime / Network / Special types — **deferred to Plan 3** (folded with YAML I/O), as documented in the plan-series overview

**Phase 1 reviewer priorities:**
- ✓ Annotated-unwrapping layer (T5)
- ✓ Plumb `field_info.metadata` → node constraint fields (T6)
- ✓ Resolve `set_value` contract to return `ValidationResult` (T4)
- ✓ Recursive None filtering (T3)
- ✓ `reset_default_registry()` test helper (T1)
- ✓ Housekeeping: `uv_build<0.12` (T1)

**Placeholder scan:** Searched the plan for "TBD", "TODO", "implement later", "fill in", "similar to". None found. Every code step has full code and every command step has the exact command + expected output.

**Type consistency:** Spot-checked names that recur across tasks:
- `SequenceNode.origin` is `"list"|"set"|"tuple"|"tuple_fixed"` consistently across T9/T10/T11/T12.
- `_resolve_type_name` is defined once in T12 and reused in T13 and T15.
- `_fq()` helper appears in T10, T13, T14 — same shape, intentionally local to each module to avoid an import dependency between unrelated builder modules.
- `ValidationResult.ok()` / `.fail()` / `.success()` consistent with Phase 1's definition.

**Risks called out:**
- T9/T10 `_build_items` rebuilds children with synthetic `FieldInfo(annotation=item_type)` — this loses any constraints the parent declared on the **container** (e.g., `MinLen` on `list[str]` is on the container, not the items). This is correct behavior; the constraints land on the SequenceNode itself via `extract_constraints` in the builder.
- T14's UnionBuilder pre-selection by `isinstance` may misroute when variant types overlap (e.g., `int | bool` — but bool is an int subclass). Plan 2 ships the simpler ordering-based behavior; if it bites, a follow-up fix lands as part of Plan 3.

End of plan.





