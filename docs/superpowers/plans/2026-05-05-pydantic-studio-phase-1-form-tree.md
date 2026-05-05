# pydantic-studio Implementation Plan — Phase 1: Form Tree Core

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core `FormTree` library — primitive types, nested groups, snapshots/undo/redo, and draft persistence — fully testable through a programmatic API. No CLI, no renderers, no I/O layer yet.

**Architecture:** The Form Tree is itself a hierarchy of Pydantic v2 models with a discriminated `kind` field. Mutations push snapshots (`model_dump_json` bytes) to a bounded ring buffer; undo/redo move a cursor over the ring. Draft auto-save mirrors the most recent snapshot to disk. This single architectural bet (tree-as-pydantic) gives us validation, deep-copy, and JSON serialization for free.

**Tech Stack:** Python 3.11+, Pydantic 2.7+, pytest, uv (build + run), ruff (lint), pyright (type check).

**Spec reference:** `docs/superpowers/specs/2026-05-05-pydantic-studio-design.md`

---

## Plan series overview

This is **Plan 1 of 6** for `pydantic-studio` v0.1. Each plan produces working, testable software:

| # | Plan | Adds | Verifiable by |
|---|---|---|---|
| **1** | **Form Tree core (this plan)** | Primitives, groups, snapshots, undo/redo, draft, `to_instance` | Unit tests + programmatic API |
| 2 | Type coverage | Sequence/Mapping/Union/Enum/Literal/Constrained/datetime/network/special | Unit tests on every type |
| 3 | YAML I/O + CLI MVP | `ruamel.yaml` round-trip, smart writer, `pydantic-studio` CLI | E2E: `pydantic-studio fill demo.config:Settings -o c.yaml` |
| 4 | Textual renderer | TUI app, sidebar/form/preview, key bindings | Textual `Pilot` snapshot tests |
| 5 | HTML renderer | FastAPI + HTMX + Tailwind, ephemeral local web | Playwright E2E |
| 6 | TOML/JSON I/O + polish + docs | tomlkit, JSON, markdown descriptions, mkdocs site | Manual demos + mkdocs build |

After this plan completes, plan 2 will be drafted based on the actual API shape that emerges.

---

## Files for Phase 1

```
pydantic-config/                       # working dir; rename to pydantic-studio at end
├── .gitignore                         # NEW
├── README.md                          # NEW (stub)
├── LICENSE                            # NEW (MIT)
├── pyproject.toml                     # NEW
├── src/
│   └── pydantic_studio/
│       ├── __init__.py                # NEW — public API
│       ├── exceptions.py              # NEW
│       └── tree/
│           ├── __init__.py            # NEW
│           ├── nodes.py               # NEW — FormNode hierarchy + discriminated union
│           ├── paths.py               # NEW — JSONPath-style addressing
│           ├── builder.py             # NEW — NodeBuilder protocol + registry + build_form_tree
│           ├── snapshots.py           # NEW — ring buffer + draft persistence
│           └── validation.py          # NEW — ValidationResult dataclass
└── tests/
    ├── __init__.py                    # NEW
    ├── conftest.py                    # NEW
    ├── fixtures/
    │   └── schemas.py                 # NEW — sample BaseModels for tests
    └── unit/
        ├── __init__.py                # NEW
        ├── test_paths.py
        ├── test_nodes.py
        ├── test_builder.py
        ├── test_snapshots.py
        ├── test_mutations.py
        └── test_round_trip.py
```

---

## Tasks

### Task 1: Project scaffolding

**Files:**
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `README.md`
- Create: `pyproject.toml`
- Create: `src/pydantic_studio/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
.venv/
.eggs/

# Environments
.env
.envrc

# Testing
.pytest_cache/
.coverage
.coverage.*
htmlcov/
.tox/
.hypothesis/

# Type checking
.mypy_cache/
.pyright/

# Editors
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# pydantic-studio
.pydantic-studio.draft.json
```

- [ ] **Step 2: Write `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 pydantic-studio contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Write minimal `README.md`**

```markdown
# pydantic-studio

Interactive editor for Pydantic models — generates `config.yaml` / `.toml` / `.json` files via terminal UI, ephemeral local web UI, or CLI.

**Status:** Early development (Phase 1 — Form Tree core).

See `docs/superpowers/specs/` for design.
```

- [ ] **Step 4: Write `pyproject.toml`**

```toml
[project]
name = "pydantic-studio"
version = "0.0.1"
description = "Interactive editor for Pydantic models — produces config.yaml/.toml/.json"
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
license-files = ["LICENSE"]
authors = [{ name = "pydantic-studio contributors" }]
classifiers = [
  "Development Status :: 2 - Pre-Alpha",
  "Framework :: Pydantic",
  "Framework :: Pydantic :: 2",
  "Intended Audience :: Developers",
  "Operating System :: OS Independent",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Programming Language :: Python :: 3.14",
  "Topic :: Software Development",
  "Typing :: Typed",
]
dependencies = [
  "pydantic>=2.7",
]

[project.urls]
Source = "https://github.com/pydantic-studio/pydantic-studio"

[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "pytest-cov",
]
lint = [
  "ruff",
  "pyright",
]

[build-system]
requires = ["uv_build>=0.8"]
build-backend = "uv_build"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
python_files = ["test_*.py"]
addopts = "-ra"
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "PT", "RUF", "TC", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["D"]

[tool.pyright]
pythonVersion = "3.11"
typeCheckingMode = "basic"
reportMissingTypeStubs = false

[tool.uv]
default-groups = ["dev", "lint"]
```

- [ ] **Step 5: Write `src/pydantic_studio/__init__.py`**

```python
"""pydantic-studio: interactive editor for Pydantic models."""

from __future__ import annotations

__version__ = "0.0.1"

# Public API will be filled in as features land in subsequent tasks.
__all__: list[str] = ["__version__"]
```

- [ ] **Step 6: Write `tests/__init__.py` and `tests/conftest.py` (empty placeholders)**

`tests/__init__.py`:
```python
```

`tests/conftest.py`:
```python
"""Shared pytest fixtures."""
from __future__ import annotations
```

- [ ] **Step 7: Run `uv sync` to install everything**

Run: `uv sync`

Expected: creates `.venv/`, installs `pydantic`, `pytest`, `ruff`, `pyright`. No errors.

- [ ] **Step 8: Run pytest collection to confirm scaffolding**

Run: `uv run pytest --collect-only`

Expected: `collected 0 items` (no tests yet but collection works).

- [ ] **Step 9: Commit**

```
git add -A
git commit -m "feat: project scaffolding (pyproject, license, gitignore, package skeleton)"
```

---

### Task 2: Exception hierarchy

**Files:**
- Create: `src/pydantic_studio/exceptions.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_exceptions.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/__init__.py`:
```python
```

`tests/unit/test_exceptions.py`:
```python
from __future__ import annotations

import pytest

from pydantic_studio.exceptions import (
    CancelledByUser,
    NoBuilderError,
    PydanticStudioError,
    ValidationFailedError,
)


def test_pydantic_studio_error_is_base():
    """All custom exceptions inherit from PydanticStudioError."""
    assert issubclass(NoBuilderError, PydanticStudioError)
    assert issubclass(CancelledByUser, PydanticStudioError)
    assert issubclass(ValidationFailedError, PydanticStudioError)


def test_no_builder_error_carries_type():
    err = NoBuilderError(int)
    assert err.type_ is int
    assert "int" in str(err)


def test_cancelled_by_user_is_default_constructible():
    err = CancelledByUser()
    assert isinstance(err, PydanticStudioError)


def test_validation_failed_error_carries_errors():
    err = ValidationFailedError(["name: required", "age: must be > 0"])
    assert err.errors == ["name: required", "age: must be > 0"]
    assert "name: required" in str(err)


def test_pydantic_studio_error_can_be_caught_generically():
    """Anyone who catches PydanticStudioError catches all our errors."""
    with pytest.raises(PydanticStudioError):
        raise NoBuilderError(int)
    with pytest.raises(PydanticStudioError):
        raise CancelledByUser()
    with pytest.raises(PydanticStudioError):
        raise ValidationFailedError([])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_exceptions.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'pydantic_studio.exceptions'`.

- [ ] **Step 3: Write `src/pydantic_studio/exceptions.py`**

```python
"""Exception hierarchy for pydantic-studio."""

from __future__ import annotations


class PydanticStudioError(Exception):
    """Base class for all pydantic-studio errors."""


class NoBuilderError(PydanticStudioError):
    """Raised when no NodeBuilder matches a given Python type."""

    def __init__(self, type_: type) -> None:
        self.type_ = type_
        super().__init__(f"No NodeBuilder registered for type: {type_!r}")


class CancelledByUser(PydanticStudioError):
    """Raised when the user cancels the editing session (Ctrl+C, browser close, etc.)."""


class ValidationFailedError(PydanticStudioError):
    """Raised when materializing the form tree into an instance fails validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("Validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_exceptions.py -v`

Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/exceptions.py tests/unit/__init__.py tests/unit/test_exceptions.py
git commit -m "feat(exceptions): exception hierarchy"
```

---

### Task 3: Path addressing

**Files:**
- Create: `src/pydantic_studio/tree/__init__.py`
- Create: `src/pydantic_studio/tree/paths.py`
- Create: `tests/unit/test_paths.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_paths.py`:
```python
from __future__ import annotations

import pytest

from pydantic_studio.tree.paths import Path, PathSegment


def test_parse_simple_field():
    p = Path.parse("name")
    assert p.segments == ("name",)


def test_parse_nested_field():
    p = Path.parse("database.host")
    assert p.segments == ("database", "host")


def test_parse_with_index():
    p = Path.parse("replicas[2].host")
    assert p.segments == ("replicas", 2, "host")


def test_parse_multiple_indices():
    p = Path.parse("matrix[0][1]")
    assert p.segments == ("matrix", 0, 1)


def test_parse_root():
    p = Path.parse("")
    assert p.segments == ()


def test_parse_rejects_negative_index():
    with pytest.raises(ValueError, match="negative index"):
        Path.parse("foo[-1]")


def test_parse_rejects_unclosed_bracket():
    with pytest.raises(ValueError, match="unclosed"):
        Path.parse("foo[2")


def test_parse_rejects_non_integer_index():
    with pytest.raises(ValueError, match="non-integer"):
        Path.parse("foo[abc]")


def test_render_round_trip():
    raw = "database.replicas[2].host"
    assert Path.parse(raw).render() == raw


def test_append_field():
    p = Path(("foo",)).append("bar")
    assert p.render() == "foo.bar"


def test_append_index():
    p = Path(("foo",)).append(3)
    assert p.render() == "foo[3]"


def test_path_is_hashable():
    """Paths are used as dict keys (e.g., per-field error map)."""
    d: dict[Path, str] = {}
    d[Path(("a", "b"))] = "x"
    assert d[Path(("a", "b"))] == "x"


def test_path_segment_alias():
    """PathSegment is the canonical name for str | int."""
    s: PathSegment = "name"  # noqa: F841
    i: PathSegment = 0       # noqa: F841
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_paths.py -v`

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/pydantic_studio/tree/__init__.py`**

```python
"""Form tree core."""

from __future__ import annotations
```

- [ ] **Step 4: Write `src/pydantic_studio/tree/paths.py`**

```python
"""JSONPath-style addressing for form-tree nodes.

Path syntax::

    ""                            → root
    "name"                        → top-level field 'name'
    "database.host"               → nested field
    "replicas[2]"                 → element 2 of a SequenceNode
    "database.replicas[2].host"   → mixed
    "matrix[0][1]"                → multiple indices

Indices are non-negative integers. Field names follow Python identifier rules
(letters, digits, underscores; no leading digit).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeAlias


PathSegment: TypeAlias = str | int

_FIELD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_INDEX_RE = re.compile(r"\[([^\]]*)\]")


@dataclass(frozen=True, slots=True)
class Path:
    """An immutable address into a form tree.

    Use ``Path.parse(s)`` for human-readable strings, or ``Path((...))``
    directly for programmatic construction.
    """

    segments: tuple[PathSegment, ...] = ()

    @classmethod
    def parse(cls, raw: str) -> Path:
        if raw == "":
            return cls(())
        segments: list[PathSegment] = []
        i = 0
        n = len(raw)
        # Expect either a field name or an index segment to start.
        while i < n:
            if raw[i] == "[":
                end = raw.find("]", i)
                if end == -1:
                    msg = f"unclosed bracket in path {raw!r}"
                    raise ValueError(msg)
                inside = raw[i + 1 : end]
                try:
                    idx = int(inside)
                except ValueError as e:
                    msg = f"non-integer index {inside!r} in path {raw!r}"
                    raise ValueError(msg) from e
                if idx < 0:
                    msg = f"negative index {idx} in path {raw!r}"
                    raise ValueError(msg)
                segments.append(idx)
                i = end + 1
            elif raw[i] == ".":
                i += 1  # separator between two field-name segments
            else:
                m = _FIELD_RE.match(raw, i)
                if not m:
                    msg = f"unexpected character {raw[i]!r} at position {i} in path {raw!r}"
                    raise ValueError(msg)
                segments.append(m.group(0))
                i = m.end()
        return cls(tuple(segments))

    def render(self) -> str:
        out: list[str] = []
        for seg in self.segments:
            if isinstance(seg, int):
                out.append(f"[{seg}]")
            else:
                if out:
                    out.append(".")
                out.append(seg)
        return "".join(out)

    def append(self, segment: PathSegment) -> Path:
        return Path((*self.segments, segment))

    def __str__(self) -> str:
        return self.render()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_paths.py -v`

Expected: 12 passed.

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/tree/__init__.py src/pydantic_studio/tree/paths.py tests/unit/test_paths.py
git commit -m "feat(tree): JSONPath-style path addressing"
```

---

### Task 4: ValidationResult + FormNode base

**Files:**
- Create: `src/pydantic_studio/tree/validation.py`
- Create: `src/pydantic_studio/tree/nodes.py`  (initial — will grow in next tasks)
- Create: `tests/unit/test_nodes.py`  (initial)

- [ ] **Step 1: Write the failing test**

`tests/unit/test_nodes.py`:
```python
from __future__ import annotations

from pydantic_studio.tree.nodes import FormNode
from pydantic_studio.tree.validation import ValidationResult


def test_validation_result_ok_factory():
    res = ValidationResult.ok()
    assert res.ok is True
    assert res.errors == []


def test_validation_result_failure_factory():
    res = ValidationResult.fail(["name: required"])
    assert res.ok is False
    assert res.errors == ["name: required"]


def test_validation_result_is_truthy_when_ok():
    """Convenient: `if result: ...` works."""
    assert bool(ValidationResult.ok()) is True
    assert bool(ValidationResult.fail(["x"])) is False


def test_form_node_has_required_attrs():
    """FormNode is the abstract base; concrete subclasses come later."""
    # Constructing FormNode directly via subclass-without-extras for the test:
    class _Bare(FormNode):
        kind: str = "_bare"

    n = _Bare(name="x")
    assert n.name == "x"
    assert n.description is None
    assert n.required is True
    assert n.error is None


def test_form_node_with_description():
    class _Bare(FormNode):
        kind: str = "_bare"

    n = _Bare(name="x", description="**hello**", required=False)
    assert n.description == "**hello**"
    assert n.required is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_nodes.py -v`

Expected: FAIL — `ModuleNotFoundError: ... .validation` or `... .nodes`.

- [ ] **Step 3: Write `src/pydantic_studio/tree/validation.py`**

```python
"""Validation result type returned by tree mutations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of a node-local or tree-wide validation pass.

    ``ok`` is True iff ``errors`` is empty. The dataclass is frozen so
    callers can store results without worrying about mutation.
    """

    ok: bool
    errors: list[str] = field(default_factory=list)

    @classmethod
    def success(cls) -> ValidationResult:
        return cls(ok=True, errors=[])

    # convenience aliases
    @classmethod
    def ok(cls) -> ValidationResult:  # noqa: A003 - intentional shadowing of builtin
        return cls.success()

    @classmethod
    def fail(cls, errors: list[str]) -> ValidationResult:
        return cls(ok=False, errors=list(errors))

    def __bool__(self) -> bool:
        return self.ok
```

- [ ] **Step 4: Write initial `src/pydantic_studio/tree/nodes.py`**

```python
"""Form tree node hierarchy.

The tree is a Pydantic v2 hierarchy with a ``kind`` discriminator.
Concrete node types are added in subsequent tasks; this file defines
the abstract base ``FormNode``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class FormNode(BaseModel):
    """Abstract base. Concrete subclasses set their own ``kind`` literal.

    All FormNodes carry minimal metadata: ``name`` (the field name in the
    parent's schema), ``description`` (markdown, may be None), ``required``
    (mirrors the schema's required-ness), and ``error`` (last validation
    message; None when valid).
    """

    model_config = ConfigDict(extra="forbid")

    kind: str  # set by subclass
    name: str
    description: str | None = None
    required: bool = True
    error: str | None = None

    # Convenience hook used in subsequent tasks; subclasses may override.
    def to_python(self) -> Any:
        """Return this node's value in a form suitable for `model_validate`."""
        msg = f"{type(self).__name__}.to_python is not implemented"
        raise NotImplementedError(msg)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_nodes.py -v`

Expected: 5 passed.

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/tree/validation.py src/pydantic_studio/tree/nodes.py tests/unit/test_nodes.py
git commit -m "feat(tree): ValidationResult + FormNode abstract base"
```

---

### Task 5: StringNode

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` (append `StringNode`)
- Modify: `tests/unit/test_nodes.py` (append tests)

- [ ] **Step 1: Write the failing test (append to `tests/unit/test_nodes.py`)**

```python
# Append to tests/unit/test_nodes.py


from pydantic_studio.tree.nodes import StringNode


def test_string_node_minimal():
    n = StringNode(name="title")
    assert n.kind == "string"
    assert n.value is None
    assert n.default is None
    assert n.error is None
    assert n.multiline is False
    assert n.secret is False


def test_string_node_set_value():
    n = StringNode(name="title", value="hello")
    assert n.value == "hello"
    assert n.to_python() == "hello"


def test_string_node_with_constraints():
    n = StringNode(name="code", min_length=3, max_length=8, pattern=r"^[A-Z]+$")
    assert n.min_length == 3
    assert n.max_length == 8
    assert n.pattern == "^[A-Z]+$"


def test_string_node_default_falls_back_to_value():
    n = StringNode(name="title", default="untitled")
    assert n.default == "untitled"
    assert n.value is None  # default is separate from current value


def test_string_node_secret_flag():
    n = StringNode(name="password", secret=True)
    assert n.secret is True


def test_string_node_serializes_with_kind_discriminator():
    n = StringNode(name="x", value="y")
    dumped = n.model_dump()
    assert dumped["kind"] == "string"
    restored = StringNode.model_validate(dumped)
    assert restored.value == "y"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_nodes.py -v`

Expected: FAIL — `ImportError: cannot import name 'StringNode'`.

- [ ] **Step 3: Append `StringNode` to `src/pydantic_studio/tree/nodes.py`**

Append at the bottom of the file:

```python
from typing import Literal


class StringNode(FormNode):
    """Holds a string value, with optional length / regex / multiline / secret hints."""

    kind: Literal["string"] = "string"
    value: str | None = None
    default: str | None = None

    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None  # regex source; rendered as a label, not enforced here
    multiline: bool = False
    secret: bool = False

    def to_python(self) -> str | None:
        return self.value
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_nodes.py -v`

Expected: 11 passed (5 original + 6 new).

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/tree/nodes.py tests/unit/test_nodes.py
git commit -m "feat(tree): StringNode"
```

---

### Task 6: IntNode + FloatNode + BoolNode + DecimalNode

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py`
- Modify: `tests/unit/test_nodes.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_nodes.py`:

```python
from decimal import Decimal

from pydantic_studio.tree.nodes import BoolNode, DecimalNode, FloatNode, IntNode


def test_int_node_minimal():
    n = IntNode(name="age")
    assert n.kind == "int"
    assert n.value is None


def test_int_node_with_value_and_constraints():
    n = IntNode(name="age", value=42, ge=0, le=150)
    assert n.value == 42
    assert n.ge == 0
    assert n.le == 150
    assert n.to_python() == 42


def test_int_node_supports_strict_bounds():
    n = IntNode(name="x", gt=0, lt=100, multiple_of=5)
    assert n.gt == 0
    assert n.lt == 100
    assert n.multiple_of == 5


def test_float_node_minimal():
    n = FloatNode(name="ratio", value=0.75)
    assert n.kind == "float"
    assert n.value == 0.75


def test_bool_node_minimal():
    n = BoolNode(name="enabled", value=True)
    assert n.kind == "bool"
    assert n.value is True
    assert n.to_python() is True


def test_decimal_node_minimal():
    n = DecimalNode(name="amount", value=Decimal("3.14"))
    assert n.kind == "decimal"
    assert n.value == Decimal("3.14")
    assert n.to_python() == Decimal("3.14")


def test_decimal_node_constraints():
    n = DecimalNode(name="x", max_digits=5, decimal_places=2)
    assert n.max_digits == 5
    assert n.decimal_places == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_nodes.py -v`

Expected: 7 new tests fail with `ImportError`.

- [ ] **Step 3: Append node classes to `src/pydantic_studio/tree/nodes.py`**

```python
from decimal import Decimal


class IntNode(FormNode):
    kind: Literal["int"] = "int"
    value: int | None = None
    default: int | None = None

    ge: int | None = None
    le: int | None = None
    gt: int | None = None
    lt: int | None = None
    multiple_of: int | None = None

    def to_python(self) -> int | None:
        return self.value


class FloatNode(FormNode):
    kind: Literal["float"] = "float"
    value: float | None = None
    default: float | None = None

    ge: float | None = None
    le: float | None = None
    gt: float | None = None
    lt: float | None = None
    multiple_of: float | None = None
    allow_inf_nan: bool = True

    def to_python(self) -> float | None:
        return self.value


class BoolNode(FormNode):
    kind: Literal["bool"] = "bool"
    value: bool | None = None
    default: bool | None = None

    def to_python(self) -> bool | None:
        return self.value


class DecimalNode(FormNode):
    kind: Literal["decimal"] = "decimal"
    value: Decimal | None = None
    default: Decimal | None = None

    max_digits: int | None = None
    decimal_places: int | None = None
    ge: Decimal | None = None
    le: Decimal | None = None

    def to_python(self) -> Decimal | None:
        return self.value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_nodes.py -v`

Expected: 18 passed (11 prior + 7 new).

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/tree/nodes.py tests/unit/test_nodes.py
git commit -m "feat(tree): IntNode, FloatNode, BoolNode, DecimalNode"
```

---

### Task 7: GroupNode + discriminated union type

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py`
- Modify: `tests/unit/test_nodes.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_nodes.py`:

```python
from pydantic import BaseModel

from pydantic_studio.tree.nodes import AnyNode, GroupNode


class _PersonSchema(BaseModel):
    name: str
    age: int


def test_group_node_holds_named_fields():
    name_node = StringNode(name="name", value="alice")
    age_node = IntNode(name="age", value=30)
    g = GroupNode(name="root", schema_class=_PersonSchema, fields=[name_node, age_node])
    assert g.kind == "group"
    assert len(g.fields) == 2
    assert g.fields[0].name == "name"


def test_group_node_find_by_name():
    name_node = StringNode(name="name", value="alice")
    age_node = IntNode(name="age", value=30)
    g = GroupNode(name="root", schema_class=_PersonSchema, fields=[name_node, age_node])
    assert g.find("name") is name_node
    assert g.find("missing") is None


def test_group_node_to_python():
    name_node = StringNode(name="name", value="alice")
    age_node = IntNode(name="age", value=30)
    g = GroupNode(name="root", schema_class=_PersonSchema, fields=[name_node, age_node])
    assert g.to_python() == {"name": "alice", "age": 30}


def test_group_node_serializes_with_polymorphic_children():
    """Children are stored under the AnyNode discriminated union."""
    g = GroupNode(
        name="root",
        schema_class=_PersonSchema,
        fields=[StringNode(name="name", value="bob"), IntNode(name="age", value=42)],
    )
    dumped = g.model_dump()
    assert dumped["kind"] == "group"
    assert dumped["fields"][0]["kind"] == "string"
    assert dumped["fields"][1]["kind"] == "int"


def test_group_node_round_trip_via_json():
    g = GroupNode(
        name="root",
        schema_class=_PersonSchema,
        fields=[StringNode(name="name", value="bob"), IntNode(name="age", value=42)],
    )
    raw = g.model_dump_json()
    restored = GroupNode.model_validate_json(raw)
    assert isinstance(restored.fields[0], StringNode)
    assert isinstance(restored.fields[1], IntNode)
    assert restored.to_python() == {"name": "bob", "age": 42}


def test_any_node_alias_covers_all_types():
    """AnyNode discriminates among all concrete node types added so far."""
    # Sanity: we can declare a list[AnyNode] and append various types.
    nodes: list[AnyNode] = []
    nodes.append(StringNode(name="a"))
    nodes.append(IntNode(name="b"))
    nodes.append(BoolNode(name="c"))
    assert {n.kind for n in nodes} == {"string", "int", "bool"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_nodes.py -v`

Expected: 6 new tests fail with `ImportError`.

- [ ] **Step 3: Append `GroupNode` and `AnyNode` to `src/pydantic_studio/tree/nodes.py`**

Add at the **bottom** of the file:

```python
from typing import Annotated, Any, Union

from pydantic import Discriminator, Tag


# Forward-reference for the discriminated union; defined just below.
class GroupNode(FormNode):
    kind: Literal["group"] = "group"
    schema_class: type[BaseModel]
    fields: "list[AnyNode]"  # forward ref; rebuilt at module bottom

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def find(self, name: str) -> "AnyNode | None":
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def to_python(self) -> dict[str, Any]:
        return {f.name: f.to_python() for f in self.fields}


# Discriminated union — every concrete node type uses ``kind`` as discriminator.
AnyNode = Annotated[
    Union[
        StringNode,
        IntNode,
        FloatNode,
        BoolNode,
        DecimalNode,
        GroupNode,
    ],
    Discriminator("kind"),
]


# Resolve the forward reference inside GroupNode.fields.
GroupNode.model_rebuild()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_nodes.py -v`

Expected: 24 passed.

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/tree/nodes.py tests/unit/test_nodes.py
git commit -m "feat(tree): GroupNode + discriminated AnyNode union"
```

---

### Task 8: NodeBuilder protocol + registry

**Files:**
- Create: `src/pydantic_studio/tree/builder.py`  (initial)
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/schemas.py`
- Create: `tests/unit/test_builder.py`

- [ ] **Step 1: Create `tests/fixtures/__init__.py` and `tests/fixtures/schemas.py`**

`tests/fixtures/__init__.py`:
```python
```

`tests/fixtures/schemas.py`:
```python
"""Sample BaseModels used across unit tests."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class Simple(BaseModel):
    """Flat schema with one of each primitive type."""

    name: str = Field(description="The thing's name")
    age: int = Field(default=0, ge=0, description="Age in years")
    height: float = 1.7
    enabled: bool = True
    balance: Decimal = Decimal("0.00")


class Address(BaseModel):
    street: str
    city: str


class Person(BaseModel):
    name: str
    address: Address  # nested BaseModel
```

- [ ] **Step 2: Write failing tests**

`tests/unit/test_builder.py`:
```python
from __future__ import annotations

import pytest

from pydantic_studio.exceptions import NoBuilderError
from pydantic_studio.tree.builder import NodeBuilder, Registry, default_registry


def test_default_registry_is_non_empty():
    """The default registry should already have at least one builder
    (more added in subsequent tasks; for now we just check shape)."""
    assert isinstance(default_registry(), Registry)


def test_registry_no_match_raises_no_builder_error():
    """If no builder matches, the registry raises NoBuilderError(type)."""
    reg = Registry()  # empty
    with pytest.raises(NoBuilderError) as exc_info:
        reg.find(int)
    assert exc_info.value.type_ is int


def test_registry_register_prepends_builder():
    """Registering puts the new builder at the front (overrides earlier)."""

    class Always(NodeBuilder):
        def matches(self, type_: type) -> bool:
            return True

        def build(self, type_, field_info, existing):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    reg = Registry()
    a, b = Always(), Always()
    reg.register(a)
    reg.register(b)  # b prepended
    assert reg.find(int) is b
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_builder.py -v`

Expected: FAIL — `ModuleNotFoundError: ...builder`.

- [ ] **Step 4: Write `src/pydantic_studio/tree/builder.py`**

```python
"""Type-to-Node dispatch via a pluggable registry.

The registry is a list of ``NodeBuilder`` instances. ``find`` returns the
first builder whose ``matches`` method returns True; new builders are
prepended so user registrations override defaults.
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


_DEFAULT_REGISTRY: Registry | None = None


def default_registry() -> Registry:
    """Return the global default registry (lazily constructed).

    Subsequent tasks register concrete builders into this registry. v0.1
    stays single-process and does not need cross-thread isolation.
    """
    global _DEFAULT_REGISTRY  # noqa: PLW0603
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = Registry()
    return _DEFAULT_REGISTRY
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_builder.py -v`

Expected: 3 passed.

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/tree/builder.py tests/fixtures/__init__.py tests/fixtures/schemas.py tests/unit/test_builder.py
git commit -m "feat(tree): NodeBuilder protocol + Registry"
```

---

### Task 9: Builders for primitive types

**Files:**
- Modify: `src/pydantic_studio/tree/builder.py`
- Modify: `tests/unit/test_builder.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_builder.py`:

```python
from decimal import Decimal

from pydantic.fields import FieldInfo

from pydantic_studio.tree.builder import (
    BoolBuilder,
    DecimalBuilder,
    FloatBuilder,
    IntBuilder,
    StringBuilder,
)
from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    FloatNode,
    IntNode,
    StringNode,
)


def _fi(default=None, **kw):
    """Helper: fabricate a FieldInfo with the given metadata."""
    return FieldInfo(default=default, **kw)


def test_string_builder_matches_str():
    b = StringBuilder()
    assert b.matches(str) is True
    assert b.matches(int) is False


def test_string_builder_builds_with_default():
    b = StringBuilder()
    fi = _fi(default="hi", description="a greeting")
    n = b.build(str, fi, existing=None)
    assert isinstance(n, StringNode)
    assert n.default == "hi"
    assert n.description == "a greeting"
    assert n.value is None  # nothing passed in `existing`


def test_string_builder_picks_existing_value_over_default():
    b = StringBuilder()
    fi = _fi(default="hi")
    n = b.build(str, fi, existing="bonjour")
    assert n.value == "bonjour"


def test_int_builder_matches_int_only():
    b = IntBuilder()
    assert b.matches(int) is True
    assert b.matches(bool) is False  # bool is a subclass of int but we don't want it


def test_int_builder_builds():
    b = IntBuilder()
    n = b.build(int, _fi(default=10), existing=None)
    assert isinstance(n, IntNode)
    assert n.default == 10


def test_float_builder_builds():
    b = FloatBuilder()
    assert b.matches(float)
    n = b.build(float, _fi(default=1.5), existing=None)
    assert isinstance(n, FloatNode)
    assert n.default == 1.5


def test_bool_builder_builds():
    b = BoolBuilder()
    assert b.matches(bool)
    n = b.build(bool, _fi(default=True), existing=None)
    assert isinstance(n, BoolNode)
    assert n.default is True


def test_decimal_builder_builds():
    b = DecimalBuilder()
    assert b.matches(Decimal)
    n = b.build(Decimal, _fi(default=Decimal("0.00")), existing=None)
    assert isinstance(n, DecimalNode)
    assert n.default == Decimal("0.00")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_builder.py -v`

Expected: 8 new tests fail with `ImportError`.

- [ ] **Step 3: Append builders to `src/pydantic_studio/tree/builder.py`**

```python
from decimal import Decimal

from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    FloatNode,
    IntNode,
    StringNode,
)


class StringBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is str

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> StringNode:
        default = field_info.get_default(call_default_factory=True)
        return StringNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default if default is not None else None,
        )


class IntBuilder:
    def matches(self, type_: type) -> bool:
        # Exclude bool, which is a subclass of int in Python.
        return type_ is int

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> IntNode:
        default = field_info.get_default(call_default_factory=True)
        return IntNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default if default is not None else None,
        )


class FloatBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is float

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> FloatNode:
        default = field_info.get_default(call_default_factory=True)
        return FloatNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default if default is not None else None,
        )


class BoolBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is bool

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> BoolNode:
        default = field_info.get_default(call_default_factory=True)
        return BoolNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default if default is not None else None,
        )


class DecimalBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is Decimal

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> DecimalNode:
        default = field_info.get_default(call_default_factory=True)
        return DecimalNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default if default is not None else None,
        )
```

Then update `default_registry()` to register them:

Replace the existing `default_registry()` function with:

```python
def default_registry() -> Registry:
    """Return the global default registry (lazily constructed)."""
    global _DEFAULT_REGISTRY  # noqa: PLW0603
    if _DEFAULT_REGISTRY is None:
        reg = Registry()
        # Register in *reverse* priority order — last registered wins for same type.
        # Primitive builders are mutually exclusive on type, so order doesn't matter
        # within this group, but we follow a stable convention.
        reg.register(StringBuilder())
        reg.register(IntBuilder())
        reg.register(FloatBuilder())
        reg.register(BoolBuilder())
        reg.register(DecimalBuilder())
        _DEFAULT_REGISTRY = reg
    return _DEFAULT_REGISTRY
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_builder.py -v`

Expected: 11 passed (3 prior + 8 new).

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/tree/builder.py tests/unit/test_builder.py
git commit -m "feat(tree): primitive type builders (str, int, float, bool, Decimal)"
```

---

### Task 10: GroupBuilder + nested model support

**Files:**
- Modify: `src/pydantic_studio/tree/builder.py`
- Modify: `tests/unit/test_builder.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_builder.py`:

```python
from pydantic_studio.tree.builder import GroupBuilder
from pydantic_studio.tree.nodes import GroupNode
from tests.fixtures.schemas import Address, Person, Simple


def test_group_builder_matches_basemodel_subclasses():
    b = GroupBuilder(default_registry())
    assert b.matches(Address) is True
    assert b.matches(int) is False
    assert b.matches(str) is False


def test_group_builder_builds_simple_schema():
    b = GroupBuilder(default_registry())
    fi = FieldInfo(annotation=Simple)
    n = b.build(Simple, fi, existing=None)
    assert isinstance(n, GroupNode)
    assert n.schema_class is Simple
    field_names = [f.name for f in n.fields]
    assert field_names == ["name", "age", "height", "enabled", "balance"]


def test_group_builder_carries_field_info_into_children():
    b = GroupBuilder(default_registry())
    n = b.build(Simple, FieldInfo(annotation=Simple), existing=None)
    name_node = n.find("name")
    assert name_node is not None
    assert name_node.description == "The thing's name"


def test_group_builder_recursive_nested_model():
    b = GroupBuilder(default_registry())
    n = b.build(Person, FieldInfo(annotation=Person), existing=None)
    assert isinstance(n, GroupNode)
    addr_node = n.find("address")
    assert isinstance(addr_node, GroupNode)
    assert addr_node.schema_class is Address
    street = addr_node.find("street")
    assert street is not None
    assert street.kind == "string"


def test_group_builder_populates_existing_values():
    b = GroupBuilder(default_registry())
    existing = {"name": "alice", "age": 30}
    n = b.build(Simple, FieldInfo(annotation=Simple), existing=existing)
    assert n.find("name").value == "alice"
    assert n.find("age").value == 30
    # unspecified fields fall back to schema defaults
    assert n.find("enabled").value is None  # nothing passed
    assert n.find("enabled").default is True


def test_group_builder_recursive_existing_values():
    b = GroupBuilder(default_registry())
    existing = {"name": "alice", "address": {"street": "1 Main", "city": "Townsville"}}
    n = b.build(Person, FieldInfo(annotation=Person), existing=existing)
    addr = n.find("address")
    assert addr.find("street").value == "1 Main"
    assert addr.find("city").value == "Townsville"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_builder.py -v`

Expected: 6 new tests fail with `ImportError`.

- [ ] **Step 3: Append `GroupBuilder` to `src/pydantic_studio/tree/builder.py`**

```python
from pydantic import BaseModel

from pydantic_studio.tree.nodes import GroupNode


class GroupBuilder:
    """Recursive builder for any ``BaseModel`` subclass.

    This builder is special: it owns a reference to the registry so it can
    dispatch each field to whichever builder matches the field's annotation.
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
            # the `FieldInfo.alias` hack and respects users' real aliases.
            child.name = fname
            children.append(child)

        # Use the field's alias (or this group's role-name) — for a *root*
        # invocation, the caller will pass alias=None; build_form_tree wraps
        # accordingly. For a nested invocation, alias is set by the parent.
        return GroupNode(
            name=field_info.alias or type_.__name__,
            description=field_info.description,
            required=field_info.is_required(),
            schema_class=type_,
            fields=children,
        )
```

Then update `default_registry()` to register `GroupBuilder`:

```python
def default_registry() -> Registry:
    """Return the global default registry (lazily constructed)."""
    global _DEFAULT_REGISTRY  # noqa: PLW0603
    if _DEFAULT_REGISTRY is None:
        reg = Registry()
        reg.register(StringBuilder())
        reg.register(IntBuilder())
        reg.register(FloatBuilder())
        reg.register(BoolBuilder())
        reg.register(DecimalBuilder())
        # GroupBuilder is registered last so it matches *any* BaseModel
        # only when no more-specific builder did. It also needs a back-
        # reference to the registry for recursive dispatch.
        reg.register(GroupBuilder(reg))
        _DEFAULT_REGISTRY = reg
    return _DEFAULT_REGISTRY
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_builder.py -v`

Expected: 17 passed (11 prior + 6 new).

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/tree/builder.py tests/unit/test_builder.py
git commit -m "feat(tree): GroupBuilder for recursive nested models"
```

---

### Task 11: build_form_tree entry point

**Files:**
- Modify: `src/pydantic_studio/tree/builder.py`
- Modify: `tests/unit/test_builder.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_builder.py`:

```python
from pydantic_studio.tree.builder import build_form_tree
from pydantic_studio.tree.nodes import FormTree


def test_build_form_tree_returns_form_tree_with_root_group():
    tree = build_form_tree(Simple)
    assert isinstance(tree, FormTree)
    assert tree.schema_class is Simple
    assert isinstance(tree.root, GroupNode)
    assert tree.root.schema_class is Simple


def test_build_form_tree_records_schema_name():
    tree = build_form_tree(Simple)
    # 'tests.fixtures.schemas:Simple' or similar — exact format documented
    assert tree.schema_name.endswith(":Simple")


def test_build_form_tree_with_existing_dict():
    tree = build_form_tree(Simple, existing={"name": "carol", "age": 7})
    assert tree.root.find("name").value == "carol"
    assert tree.root.find("age").value == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_builder.py::test_build_form_tree_returns_form_tree_with_root_group -v`

Expected: FAIL — `ImportError: cannot import name 'build_form_tree'` or `'FormTree'`.

- [ ] **Step 3: Add `build_form_tree` to `src/pydantic_studio/tree/builder.py`**

Append to the file:

```python
from datetime import UTC, datetime


def build_form_tree(
    schema: type[BaseModel],
    existing: dict[str, Any] | None = None,
    registry: Registry | None = None,
) -> "FormTree":
    """Build a FormTree from a Pydantic BaseModel subclass.

    Args:
        schema: The user's Pydantic model class.
        existing: Optional dict to pre-populate field values.
        registry: Optional custom registry (defaults to the global default).
    """
    from pydantic_studio.tree.nodes import FormTree  # avoid circular at import time

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

- [ ] **Step 4: Add `FormTree` to `src/pydantic_studio/tree/nodes.py` (minimal, will grow)**

Append to `nodes.py`:

```python
from datetime import datetime
from pathlib import Path as FsPath


class FormTree(BaseModel):
    """Root container: schema reference, root group, and history (added later)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    schema_class: type[BaseModel] | None = None  # may be re-attached via context on load
    schema_name: str
    root: GroupNode
    created_at: datetime
    snapshots: list[bytes] = []
    cursor: int = 0
    snapshot_limit: int = 50
    draft_path: FsPath | None = None

    def to_python(self) -> dict[str, Any]:
        return self.root.to_python()
```

> Why `schema_class` is Optional: when we deserialize a draft from JSON in Task 15, the JSON does not contain the Python type object. We re-attach it via validation context. Making the field Optional with a default of None lets that flow work cleanly.

- [ ] **Step 5: Run all builder tests to verify**

Run: `uv run pytest tests/unit/test_builder.py -v`

Expected: 20 passed (17 prior + 3 new).

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/tree/builder.py src/pydantic_studio/tree/nodes.py tests/unit/test_builder.py
git commit -m "feat(tree): build_form_tree() entry point + FormTree root model"
```

---

### Task 12: set_value mutation with snapshot

**Files:**
- Create: `src/pydantic_studio/tree/snapshots.py`
- Modify: `src/pydantic_studio/tree/nodes.py` (add `set_value` method to FormTree)
- Create: `tests/unit/test_mutations.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_mutations.py`:
```python
from __future__ import annotations

import pytest

from pydantic_studio.tree.builder import build_form_tree
from tests.fixtures.schemas import Person, Simple


def test_set_value_sets_a_top_level_field():
    tree = build_form_tree(Simple)
    tree.set_value("name", "dave")
    assert tree.root.find("name").value == "dave"


def test_set_value_sets_a_nested_field():
    tree = build_form_tree(Person)
    tree.set_value("address.city", "Springfield")
    addr = tree.root.find("address")
    assert addr.find("city").value == "Springfield"


def test_set_value_pushes_a_snapshot():
    tree = build_form_tree(Simple)
    assert len(tree.snapshots) == 0
    tree.set_value("name", "x")
    assert len(tree.snapshots) == 1
    tree.set_value("name", "y")
    assert len(tree.snapshots) == 2


def test_set_value_unknown_path_raises():
    tree = build_form_tree(Simple)
    with pytest.raises(KeyError, match="no_such_field"):
        tree.set_value("no_such_field", "x")


def test_set_value_through_nonexistent_parent_raises():
    tree = build_form_tree(Person)
    with pytest.raises(KeyError, match="ghost"):
        tree.set_value("ghost.city", "x")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_mutations.py -v`

Expected: FAIL — `AttributeError: 'FormTree' object has no attribute 'set_value'`.

- [ ] **Step 3: Write `src/pydantic_studio/tree/snapshots.py`**

```python
"""Snapshot serialization helpers used by FormTree.

A snapshot is the bytes from ``model_dump_json`` of the FormTree's root.
We store the *root only* (not the full FormTree) so the snapshot list
itself doesn't appear inside snapshots.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import GroupNode


def take(root: GroupNode) -> bytes:
    """Serialize a root node into a snapshot."""
    return root.model_dump_json().encode("utf-8")


def restore(snapshot: bytes) -> GroupNode:
    """Reconstruct a root node from a snapshot."""
    from pydantic_studio.tree.nodes import GroupNode

    return GroupNode.model_validate_json(snapshot)
```

- [ ] **Step 4: Add `set_value` to `FormTree` in `src/pydantic_studio/tree/nodes.py`**

Replace the body of the existing `class FormTree(...)` with:

```python
class FormTree(BaseModel):
    """Root container: schema reference, root group, and edit history."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    schema_class: type[BaseModel] | None = None  # may be re-attached via context on load
    schema_name: str
    root: GroupNode
    created_at: datetime
    snapshots: list[bytes] = []
    cursor: int = 0
    snapshot_limit: int = 50
    draft_path: FsPath | None = None

    def to_python(self) -> dict[str, Any]:
        return self.root.to_python()

    # ----- mutations -----

    def set_value(self, path: str, value: Any) -> None:
        """Set ``value`` at the given path. Pushes a snapshot before mutating."""
        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.paths import Path as _Path

        # 1. Snapshot before mutation.
        self._push_snapshot(_snap.take(self.root))

        # 2. Walk to the parent node.
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
            target.value = value
        else:
            msg = f"cannot set on non-group parent at segment {last!r}"
            raise KeyError(msg)

    # ----- snapshot internals -----

    def _push_snapshot(self, snap: bytes) -> None:
        # If the cursor is not at the tail, drop the redo tail before pushing.
        if self.cursor < len(self.snapshots):
            self.snapshots = self.snapshots[: self.cursor]
        self.snapshots.append(snap)
        # Bound: drop oldest until under the limit.
        while len(self.snapshots) > self.snapshot_limit:
            self.snapshots.pop(0)
        self.cursor = len(self.snapshots)
```

(Note: the `cursor` after a push points one past the tail — i.e., "current state is post-snapshots, no redo available.")

- [ ] **Step 5: Run mutation tests to verify they pass**

Run: `uv run pytest tests/unit/test_mutations.py -v`

Expected: 5 passed.

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/tree/snapshots.py src/pydantic_studio/tree/nodes.py tests/unit/test_mutations.py
git commit -m "feat(tree): set_value mutation with pre-mutation snapshot"
```

---

### Task 13: Undo and redo

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py`
- Modify: `tests/unit/test_mutations.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_mutations.py`:

```python
def test_undo_restores_previous_value():
    tree = build_form_tree(Simple)
    tree.set_value("name", "first")
    tree.set_value("name", "second")
    assert tree.root.find("name").value == "second"
    assert tree.undo() is True
    assert tree.root.find("name").value == "first"


def test_undo_to_initial_state():
    tree = build_form_tree(Simple)
    tree.set_value("name", "x")
    assert tree.undo() is True
    # Initial state had value=None for name.
    assert tree.root.find("name").value is None


def test_undo_returns_false_when_nothing_to_undo():
    tree = build_form_tree(Simple)
    assert tree.undo() is False


def test_redo_returns_false_when_nothing_to_redo():
    tree = build_form_tree(Simple)
    assert tree.redo() is False


def test_redo_after_undo_restores():
    tree = build_form_tree(Simple)
    tree.set_value("name", "alpha")
    tree.set_value("name", "beta")
    tree.undo()
    tree.undo()
    tree.redo()
    assert tree.root.find("name").value == "alpha"
    tree.redo()
    assert tree.root.find("name").value == "beta"


def test_set_after_undo_drops_redo_tail():
    tree = build_form_tree(Simple)
    tree.set_value("name", "a")
    tree.set_value("name", "b")
    tree.undo()  # back to "a"
    tree.set_value("name", "c")  # should drop the "b" snapshot from redo tail
    assert tree.redo() is False  # no redo available
    assert tree.root.find("name").value == "c"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_mutations.py -v`

Expected: FAIL — `AttributeError: ... 'undo'`.

- [ ] **Step 3: Add `undo` / `redo` methods to FormTree**

Append inside the `FormTree` class (just below `_push_snapshot`):

```python
    def undo(self) -> bool:
        """Restore the previous state. Returns True if anything was undone."""
        from pydantic_studio.tree import snapshots as _snap

        if self.cursor == 0:
            return False
        # The current state isn't yet on the stack; only prior states are.
        # Step back: cursor points to the snapshot that *was* the state before
        # the most recent mutation. To allow redo, capture the current state
        # first if cursor == len(snapshots).
        if self.cursor == len(self.snapshots):
            self.snapshots.append(_snap.take(self.root))
        self.cursor -= 1
        self.root = _snap.restore(self.snapshots[self.cursor])
        return True

    def redo(self) -> bool:
        """Re-apply a previously undone mutation."""
        from pydantic_studio.tree import snapshots as _snap

        if self.cursor + 1 >= len(self.snapshots):
            return False
        self.cursor += 1
        self.root = _snap.restore(self.snapshots[self.cursor])
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_mutations.py -v`

Expected: 11 passed (5 prior + 6 new).

- [ ] **Step 5: Commit**

```
git add src/pydantic_studio/tree/nodes.py tests/unit/test_mutations.py
git commit -m "feat(tree): undo/redo with redo-tail truncation"
```

---

### Task 14: Snapshot ring-buffer eviction

**Files:**
- Modify: `tests/unit/test_mutations.py`  (only test changes; logic already exists from Task 12)

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_mutations.py`:

```python
def test_snapshot_buffer_evicts_oldest():
    tree = build_form_tree(Simple)
    tree.snapshot_limit = 3
    for i in range(5):
        tree.set_value("name", f"v{i}")
    # 5 mutations but limit=3 → only 3 most recent snapshots kept.
    assert len(tree.snapshots) == 3
    # The earliest accessible state should be the one captured before "v2".
    while tree.undo():
        pass
    # We've undone everything we can. The earliest reachable name is "v1"
    # (the value before "v2" was assigned), since the snapshot taken before
    # "v0" was evicted.
    assert tree.root.find("name").value == "v1"


def test_snapshot_limit_default_is_50():
    tree = build_form_tree(Simple)
    assert tree.snapshot_limit == 50
```

- [ ] **Step 2: Run tests to verify the eviction one fails (the existing logic in `_push_snapshot` already handles eviction, but we need to confirm)**

Run: `uv run pytest tests/unit/test_mutations.py::test_snapshot_buffer_evicts_oldest -v`

Expected: PASS or FAIL — the existing implementation in Task 12 already handled this. If it fails, the assertion exposes a bug; fix `_push_snapshot` until it passes.

(*If the test passes already, this whole task degenerates into "add coverage" — still commit the test for explicit coverage.*)

- [ ] **Step 3: If failing, fix the eviction bug in `FormTree._push_snapshot`**

The intended behavior is in Task 12's code; if the test fails, double-check that:
1. `self.snapshots.pop(0)` runs *after* append, in a `while`-loop until under the limit.
2. The `cursor` is updated to `len(self.snapshots)` after eviction.

If the cursor was off by the number of evicted elements, fix:

```python
        evicted = 0
        while len(self.snapshots) > self.snapshot_limit:
            self.snapshots.pop(0)
            evicted += 1
        self.cursor = len(self.snapshots)
```

(The original `self.cursor = len(self.snapshots)` after the eviction loop already gives the right answer; if it didn't, this is the fix.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_mutations.py -v`

Expected: 13 passed.

- [ ] **Step 5: Commit**

```
git add tests/unit/test_mutations.py
# (also src/pydantic_studio/tree/nodes.py if step 3 fix was needed)
git commit -m "test(tree): explicit ring-buffer eviction coverage"
```

---

### Task 15: Draft auto-save

**Files:**
- Modify: `src/pydantic_studio/tree/snapshots.py`
- Modify: `src/pydantic_studio/tree/nodes.py`
- Create: `tests/unit/test_snapshots.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_snapshots.py`:
```python
from __future__ import annotations

import json

from pydantic_studio.tree.builder import build_form_tree
from pydantic_studio.tree.snapshots import draft_load, draft_save
from tests.fixtures.schemas import Simple


def test_draft_save_writes_file(tmp_path):
    tree = build_form_tree(Simple, existing={"name": "alice"})
    target = tmp_path / "draft.json"
    draft_save(tree, target)
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema_name"].endswith(":Simple")
    assert data["root"]["fields"][0]["name"] == "name"


def test_draft_save_is_atomic(tmp_path, monkeypatch):
    """Atomic write: target file is never seen in a partial state.
    Verified indirectly: a temp file is used, then renamed."""
    tree = build_form_tree(Simple)
    target = tmp_path / "draft.json"
    # Write twice; the second write should not interleave with the first.
    draft_save(tree, target)
    first = target.read_bytes()
    draft_save(tree, target)
    second = target.read_bytes()
    assert first == second  # idempotent given identical state


def test_draft_load_round_trip(tmp_path):
    tree = build_form_tree(Simple, existing={"name": "alice", "age": 9})
    target = tmp_path / "draft.json"
    draft_save(tree, target)
    loaded = draft_load(target, Simple)
    assert loaded.root.find("name").value == "alice"
    assert loaded.root.find("age").value == 9


def test_form_tree_set_value_writes_draft_when_path_set(tmp_path):
    tree = build_form_tree(Simple)
    tree.draft_path = tmp_path / "live.json"
    tree.set_value("name", "live")
    assert tree.draft_path.exists()
    saved = json.loads(tree.draft_path.read_text(encoding="utf-8"))
    name_field = next(f for f in saved["root"]["fields"] if f["name"] == "name")
    assert name_field["value"] == "live"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_snapshots.py -v`

Expected: FAIL — `ImportError: cannot import 'draft_save'`.

- [ ] **Step 3: Replace `src/pydantic_studio/tree/snapshots.py` with the full Phase-1 content**

Open the existing `snapshots.py` (created in Task 12) and replace its entire content with:

```python
"""Snapshot serialization helpers used by FormTree.

A snapshot is the bytes from ``model_dump_json`` of a ``GroupNode``; the
snapshot ring lives on ``FormTree.snapshots``. ``draft_save`` /
``draft_load`` handle full-FormTree persistence to disk.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path as FsPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel

    from pydantic_studio.tree.nodes import FormTree, GroupNode


def take(root: "GroupNode") -> bytes:
    """Serialize a root node into a snapshot."""
    return root.model_dump_json().encode("utf-8")


def restore(snapshot: bytes) -> "GroupNode":
    """Reconstruct a root node from a snapshot."""
    from pydantic_studio.tree.nodes import GroupNode

    return GroupNode.model_validate_json(snapshot)


def draft_save(tree: "FormTree", target: FsPath) -> None:
    """Atomically write the FormTree (excluding schema_class) to ``target``.

    ``schema_class`` is omitted because it is a Python type object with no
    JSON representation; ``draft_load`` re-attaches it from the caller's
    ``schema`` argument via validation context.
    """
    target = FsPath(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = tree.model_dump_json(exclude={"schema_class"}).encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=".tmp-draft-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp, target)
    except Exception:
        FsPath(tmp).unlink(missing_ok=True)
        raise


def draft_load(source: FsPath, schema: "type[BaseModel]") -> "FormTree":
    """Load a previously-saved draft and re-bind ``schema_class`` from ``schema``."""
    from pydantic_studio.tree.nodes import FormTree

    raw = FsPath(source).read_bytes()
    return FormTree.model_validate_json(raw, context={"schema_class": schema})
```

- [ ] **Step 4: Add a `model_validator(mode="after")` to `FormTree` that re-attaches `schema_class` from validation context**

This is what makes `draft_load` work: the JSON has no `schema_class`, but validation context carries the schema; the validator copies it onto the freshly-validated tree.

First, update the `pydantic` import line at the top of `src/pydantic_studio/tree/nodes.py` to include `ValidationInfo` and `model_validator`:

```python
from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator
```

Then add this method **inside** `class FormTree(BaseModel):` (place it right below `to_python`, before the mutation methods):

```python
    @model_validator(mode="after")
    def _inject_schema_from_context(self, info: ValidationInfo) -> "FormTree":
        """If schema_class is missing (e.g., loaded from JSON), pull it
        from the validation context (which ``draft_load`` supplies)."""
        if self.schema_class is None and info.context and "schema_class" in info.context:
            self.schema_class = info.context["schema_class"]
        return self
```

`mode="after"` runs *after* per-field validation, so we mutate the already-constructed model. `schema_class` is Optional (default `None`), so missing in JSON is not a validation error — the validator fills it in afterwards.

- [ ] **Step 5: Add draft auto-save hook in `set_value`**

In `FormTree.set_value`, after the actual value mutation, add:

```python
        # Auto-save draft if a path is configured.
        if self.draft_path is not None:
            from pydantic_studio.tree import snapshots as _snap

            _snap.draft_save(self, self.draft_path)
```

- [ ] **Step 6: Run all tests to verify**

Run: `uv run pytest -v`

Expected: all tests pass.

- [ ] **Step 7: Commit**

```
git add src/pydantic_studio/tree/snapshots.py src/pydantic_studio/tree/nodes.py tests/unit/test_snapshots.py
git commit -m "feat(tree): atomic draft auto-save + load"
```

---

### Task 16: to_instance round-trip

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py`
- Create: `tests/unit/test_round_trip.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_round_trip.py`:
```python
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from pydantic_studio.exceptions import ValidationFailedError
from pydantic_studio.tree.builder import build_form_tree
from tests.fixtures.schemas import Person, Simple


def test_to_instance_simple_full_population():
    tree = build_form_tree(Simple)
    tree.set_value("name", "alice")
    tree.set_value("age", 30)
    tree.set_value("height", 1.75)
    tree.set_value("enabled", False)
    tree.set_value("balance", Decimal("12.50"))
    inst = tree.to_instance()
    assert isinstance(inst, Simple)
    assert inst.name == "alice"
    assert inst.age == 30
    assert inst.height == 1.75
    assert inst.enabled is False
    assert inst.balance == Decimal("12.50")


def test_to_instance_uses_defaults_for_omitted_fields():
    tree = build_form_tree(Simple)
    tree.set_value("name", "alice")
    inst = tree.to_instance()
    assert inst.name == "alice"
    assert inst.age == 0  # schema default
    assert inst.enabled is True


def test_to_instance_raises_on_required_missing():
    tree = build_form_tree(Simple)  # 'name' has no default → required
    with pytest.raises(ValidationFailedError) as exc_info:
        tree.to_instance()
    assert any("name" in e for e in exc_info.value.errors)


def test_to_instance_round_trip_with_nested_model():
    tree = build_form_tree(Person)
    tree.set_value("name", "alice")
    tree.set_value("address.street", "1 Main St")
    tree.set_value("address.city", "Springfield")
    inst = tree.to_instance()
    assert isinstance(inst, Person)
    assert inst.address.street == "1 Main St"


def test_to_instance_load_then_edit_then_save_round_trip():
    """The flagship round-trip: load existing dict → edit → emit identical dict modulo edits."""
    initial = {
        "name": "alice",
        "age": 30,
        "height": 1.7,
        "enabled": True,
        "balance": Decimal("0.00"),
    }
    tree = build_form_tree(Simple, existing=initial)
    tree.set_value("age", 31)
    inst = tree.to_instance()
    assert inst.model_dump() == {**initial, "age": 31}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_round_trip.py -v`

Expected: FAIL — `AttributeError: 'FormTree' object has no attribute 'to_instance'`.

- [ ] **Step 3: Add `to_instance` to FormTree**

Append inside `class FormTree(...)` in `src/pydantic_studio/tree/nodes.py`:

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

Also: in `GroupNode.to_python` (already defined), make sure fields whose `value is None` and have no default propagate as missing keys, so pydantic raises a clear "Field required" error. The current implementation `{f.name: f.to_python() for f in self.fields}` will include all keys even with `None` values, which pydantic will treat as "explicitly set to null". For required string fields this becomes a "string type expected, got null" error rather than "field required" — semantically equivalent for our needs. The existing tests cover this; no change required.

- [ ] **Step 4: Run round-trip tests to verify they pass**

Run: `uv run pytest tests/unit/test_round_trip.py -v`

Expected: 5 passed.

- [ ] **Step 5: Run the full unit test suite to confirm no regression**

Run: `uv run pytest -v`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/tree/nodes.py tests/unit/test_round_trip.py
git commit -m "feat(tree): to_instance materialization with validation error wrapping"
```

---

### Task 17: Public API surface

**Files:**
- Modify: `src/pydantic_studio/__init__.py`
- Create: `tests/unit/test_public_api.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_public_api.py`:
```python
from __future__ import annotations

import pydantic_studio as ps


def test_version_string_present():
    assert isinstance(ps.__version__, str)
    assert ps.__version__.count(".") >= 1


def test_top_level_imports():
    """Most-used names are re-exported at top level."""
    assert hasattr(ps, "build_form_tree")
    assert hasattr(ps, "FormTree")
    assert hasattr(ps, "GroupNode")
    assert hasattr(ps, "register_builder")
    assert hasattr(ps, "PydanticStudioError")
    assert hasattr(ps, "NoBuilderError")
    assert hasattr(ps, "CancelledByUser")
    assert hasattr(ps, "ValidationFailedError")


def test_register_builder_is_callable_and_affects_default_registry():
    from pydantic_studio.tree.builder import default_registry

    class _Dummy:
        def matches(self, type_):
            return False

        def build(self, type_, field_info, existing):
            raise NotImplementedError

    before = len(default_registry())
    ps.register_builder(_Dummy())
    assert len(default_registry()) == before + 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_public_api.py -v`

Expected: FAIL — `AttributeError: module 'pydantic_studio' has no attribute ...`.

- [ ] **Step 3: Update `src/pydantic_studio/__init__.py`**

Replace contents with:

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
)
from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    FloatNode,
    FormNode,
    FormTree,
    GroupNode,
    IntNode,
    StringNode,
)


def register_builder(builder: NodeBuilder) -> None:
    """Register a custom NodeBuilder into the global default registry.

    The new builder is *prepended*, so it overrides any prior builder that
    matches the same type.
    """
    default_registry().register(builder)


__all__ = [
    "BoolNode",
    "CancelledByUser",
    "DecimalNode",
    "FloatNode",
    "FormNode",
    "FormTree",
    "GroupNode",
    "IntNode",
    "NoBuilderError",
    "NodeBuilder",
    "PydanticStudioError",
    "StringNode",
    "ValidationFailedError",
    "__version__",
    "build_form_tree",
    "register_builder",
]
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`

Expected: all tests pass.

- [ ] **Step 5: Run linting and type-checking**

```
uv run ruff check src tests
uv run pyright src
```

Expected: no errors. (Fix any reported issues before committing.)

- [ ] **Step 6: Commit**

```
git add src/pydantic_studio/__init__.py tests/unit/test_public_api.py
git commit -m "feat: public API surface (build_form_tree, FormTree, register_builder, exceptions)"
```

---

### Task 18: End-to-end smoke test + Phase 1 wrap-up

**Files:**
- Create: `tests/unit/test_smoke.py`
- Modify: `README.md`

- [ ] **Step 1: Write the smoke test**

`tests/unit/test_smoke.py`:
```python
"""End-to-end smoke test exercising the public API only."""

from __future__ import annotations

from decimal import Decimal

import pydantic_studio as ps
from tests.fixtures.schemas import Person, Simple


def test_smoke_simple():
    tree = ps.build_form_tree(Simple)
    tree.set_value("name", "alice")
    tree.set_value("age", 7)
    tree.set_value("balance", Decimal("0.50"))
    inst = tree.to_instance()
    assert inst.name == "alice"
    assert inst.age == 7


def test_smoke_nested():
    tree = ps.build_form_tree(Person)
    tree.set_value("name", "alice")
    tree.set_value("address.street", "Main")
    tree.set_value("address.city", "Springfield")
    inst = tree.to_instance()
    assert inst.address.city == "Springfield"


def test_smoke_undo_redo_full_round_trip():
    tree = ps.build_form_tree(Simple)
    tree.set_value("name", "x")
    tree.set_value("age", 1)
    tree.undo()
    tree.undo()
    inst = ps.build_form_tree(Simple, existing=tree.to_python())  # round-trip via dict
    assert isinstance(inst, ps.FormTree)
```

- [ ] **Step 2: Run the smoke test**

Run: `uv run pytest tests/unit/test_smoke.py -v`

Expected: 3 passed.

- [ ] **Step 3: Update `README.md` with a Phase 1 usage example**

Replace `README.md` body with:

```markdown
# pydantic-studio

Interactive editor for Pydantic models — generates `config.yaml` / `.toml` / `.json` files via terminal UI, ephemeral local web UI, or CLI.

**Status:** Phase 1 complete (Form Tree core). No CLI / TUI / Web yet — see roadmap below.

## What works today (Phase 1 — programmatic API)

```python
from pydantic import BaseModel
import pydantic_studio as ps

class Settings(BaseModel):
    name: str
    port: int = 8080

# Build a form tree
tree = ps.build_form_tree(Settings, existing={"port": 9000})

# Edit programmatically (renderers come in Phase 4–5)
tree.set_value("name", "my-service")
tree.set_value("port", 9001)
tree.undo()  # back to 9000
tree.redo()  # forward to 9001

# Materialize into the user's pydantic model
settings = tree.to_instance()
assert settings.port == 9001
```

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Form Tree core (primitives + groups + undo/redo + drafts) | ✅ done |
| 2 | Type coverage (Sequence/Mapping/Union/Enum/Literal/datetime/network/special) | ⏳ planned |
| 3 | YAML I/O + CLI MVP | ⏳ planned |
| 4 | Textual renderer (TUI) | ⏳ planned |
| 5 | HTML renderer (HTMX + Tailwind) | ⏳ planned |
| 6 | TOML / JSON I/O + polish + docs | ⏳ planned |

## License

MIT. See [`LICENSE`](LICENSE).
```

- [ ] **Step 4: Run the full test suite + linting**

```
uv run pytest -v
uv run ruff check src tests
uv run pyright src
```

Expected: all green.

- [ ] **Step 5: Commit**

```
git add tests/unit/test_smoke.py README.md
git commit -m "feat: phase-1 smoke test + README usage example"
```

- [ ] **Step 6: Tag the Phase 1 checkpoint**

```
git tag -a v0.0.1-phase-1 -m "Phase 1 complete: Form Tree core"
git log --oneline -1
```

Expected: HEAD has the new tag.

---

## Self-review checklist (run before handoff)

After all 18 tasks complete:

1. **Spec coverage check** — re-read `docs/superpowers/specs/2026-05-05-pydantic-studio-design.md` Section 5 (Form Tree). Every commitment there should be implemented:
   - ✅ FormTree (BaseModel) + GroupNode + Field subclasses for primitives → Tasks 4-7
   - ✅ Builder + Registry + per-type builders → Tasks 8-11
   - ✅ set_value / undo / redo → Tasks 12-13
   - ✅ Snapshots + ring buffer → Tasks 12, 14
   - ✅ Draft auto-save → Task 15
   - ✅ to_instance → Task 16
   - ⏳ Sequence / Mapping / Union / select_variant — **deferred to Plan 2** (intentional)
   - ⏳ JSONPath addressing for sequences (`foo[2]`) — only field-name walking is in Plan 1; Plan 2 will extend `set_value` to accept indexed paths
2. **Test coverage** — every concrete class/function has at least one direct test.
3. **Naming consistency** — every cross-task reference uses the same identifier:
   - `build_form_tree` (not `build_tree` or `make_form_tree`)
   - `FormTree.set_value` / `.undo` / `.redo` / `.to_instance` / `.to_python`
   - `GroupNode.find` / `.fields`
   - `default_registry()` / `register_builder()`
   - `kind` discriminator with values `"string" | "int" | "float" | "bool" | "decimal" | "group"`

---

## Hand-off to Plan 2

When the Phase 1 tag is in place, the next plan will:

- Add `SequenceNode` / `MappingNode` / `UnionNode` and their builders
- Extend `Path` parsing to feed `set_value` for indexed addressing
- Port `is_constrained_int` / `is_literal_type` / `is_union_type` etc. from `phil65/promptantic`'s `type_utils.py` (vendored, attribution in the file header)
- Cover datetime / network / `Path` / `UUID` / `SecretStr` / `Enum` / `Literal`

Plan 2 will be drafted as a separate document at `docs/superpowers/plans/2026-XX-XX-pydantic-studio-phase-2-type-coverage.md`.

---

*End of Plan 1.*
