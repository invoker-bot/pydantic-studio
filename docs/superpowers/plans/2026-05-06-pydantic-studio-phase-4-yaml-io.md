# pydantic-studio — Phase 4: YAML I/O + Phase-3 Housekeeping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add YAML config-file I/O via `ruamel.yaml` round-trip mode (load + smart write with user-comment preservation + auto-generated description comments) and three new CLI subcommands (`fill`, `run`, `check`) that exercise it. Also fold in 4 small Phase-3 follow-up fixes flagged by the Final Reviewer.

**Architecture:** A new `src/pydantic_studio/io/yaml.py` module wraps `ruamel.yaml.YAML(typ='rt')`. `load(path, schema)` parses the file into a `CommentedMap`, builds a `FormTree` from the values, and stashes the source map on the tree for later merge. `save(tree, path)` writes a new schema-ordered `CommentedMap` whose values come from `tree.to_python()` and whose comments come either from the stashed source (preserve user comments) or from `FieldInfo.description` (smart-comment defaults for new keys). New CLI subcommands import this module to provide schema-driven YAML stub generation, validation, and pretty-printing.

**Tech Stack:** Python 3.11+, Pydantic v2, ruamel.yaml ≥0.18 (round-trip mode preserves comments + key order).

**Scope note:** Plan 4 ships YAML only — TOML and JSON I/O are Plan 6 per the spec implementation order (§14). Renderer phases (Textual / HTML) follow as Plans 5 / 7. The CLI's `edit` and `fill --llm` subcommands wait for the renderer phase.

**Out-of-scope (deferred):**
- TOML / JSON I/O writers (Plan 6)
- `pydantic-studio edit` (needs Textual / HTML renderer)
- `${ENV_VAR}` secret-handling templates (deferred to a later security pass; v0.0.4 emits SecretStr values in plaintext, matching how SecretNode stores them in snapshots — caveat already documented in `nodes.py`)
- Draft auto-save integration with YAML files (existing `draft_save` keeps using JSON; YAML-as-draft is unnecessary complication)

---

## File Structure

**New files (3):**
- `src/pydantic_studio/io/__init__.py` — re-exports `load_yaml` and `save_yaml`
- `src/pydantic_studio/io/yaml.py` — `load_yaml(path, schema) -> FormTree` and `save_yaml(tree, path) -> None`
- `src/pydantic_studio/types/utils.py` — shared `field_default(field_info)` helper (T2 housekeeping)
- `tests/unit/test_yaml_io.py` — coverage for load + save + round-trip + smart comments
- `tests/unit/test_cli_yaml.py` — coverage for the three new CLI subcommands

**Modified files:**
- `pyproject.toml` — add `ruamel.yaml>=0.18` dependency
- `src/pydantic_studio/__init__.py` — export `load_yaml` / `save_yaml`
- `src/pydantic_studio/cli.py` — add `fill`, `run`, `check` subcommands; fix the `k_node.value` pyright false positive (T4 housekeeping); add `version` test target if not already implicit (T5 housekeeping)
- `src/pydantic_studio/tree/nodes.py` — `SecretNode.to_python` adds isinstance asserts for pyright narrowing (T3 housekeeping)
- `src/pydantic_studio/types/primitives.py` / `temporal.py` / `network.py` / `special.py` — replace local `_default(field_info)` with `from pydantic_studio.types.utils import field_default` (T2 housekeeping)
- `src/pydantic_studio/types/choices.py` / `unions.py` — replace inline `field_info.get_default(call_default_factory=True)` + `PydanticUndefined` check with the shared `field_default` helper (T2 housekeeping)
- `tests/unit/test_cli.py` — add `test_version_subcommand_prints_version` (T5 housekeeping)
- `tests/fixtures/schemas.py` — add 1-2 schemas tailored for YAML golden tests (small, with descriptions)
- `tests/fixtures/golden/` (NEW directory) — sample YAML files for round-trip tests
- `README.md` — Phase 4 section: YAML example + CLI demo
- `src/pydantic_studio/tree/builder.py` — UNCHANGED in this plan (all builder registrations stable)

**Why a separate `io/` package:** Plans 6 (`io/toml.py`) and the not-yet-numbered JSON writer phase will share this module structure. Establishing `io/` now keeps later phases' diffs scoped to one new file each.

**Why `types/utils.py` instead of `types/_helpers.py`:** existing modules in this repo follow the convention that utility-named modules don't begin with underscore (e.g., `metadata.py`, `annotated.py`, `registry.py` all expose helper-like content under public names). `utils.py` matches that convention.

---

## Branch Convention

Work on `feature/phase-4-yaml-io` branched from `master`. User standing instruction: **commit + merge only — DO NOT push.** Tag at the final feature commit (`v0.0.4-phase-4`) before the `--no-ff` merge to master.

---

## Pre-flight assumptions

- Master is at the merge of Phase 3 (commit `84ebab3`).
- 319 tests pass on master.
- ruff is clean.
- Pyright reports 12 errors in production code (2 carried from Phase 2; 6 introduced by Phase 3's SecretNode + CLI). Plan 4's housekeeping closes 6 of those 12.

If any of these assumptions doesn't hold, stop and flag it before proceeding.

---

### Task 1: Branch setup

**Files:** (no source changes — git only)

- [ ] **Step 1: Create feature branch from master**

```bash
git checkout master
git status  # Expected: clean
git checkout -b feature/phase-4-yaml-io
```

- [ ] **Step 2: Verify Phase-3 baseline**

```bash
uv run pytest -q
```

Expected: 319 passed.

```bash
uv run ruff check
```

Expected: All checks passed.

- [ ] **Step 3: Capture pyright baseline**

```bash
uv run pyright src/pydantic_studio 2>&1 | tail -3
```

Expected: 12 errors. Note this number — Plan 4's T2-T5 should reduce it to 6.

---

### Task 2: Housekeeping #1 — extract `field_default` to `types/utils.py`

**Why:** `_default(field_info)` is duplicated identically across `primitives.py`, `temporal.py`, `network.py`, `special.py`, and inlined in `choices.py` and `unions.py`. Phase 3's Final Reviewer flagged this as a deferred Minor; before Plan 4 adds more code that touches builders, extract the helper.

**Files:**
- Create: `src/pydantic_studio/types/utils.py`
- Modify: `src/pydantic_studio/types/primitives.py` (replace `_default` with import)
- Modify: `src/pydantic_studio/types/temporal.py` (same)
- Modify: `src/pydantic_studio/types/network.py` (same)
- Modify: `src/pydantic_studio/types/special.py` (same)
- Modify: `src/pydantic_studio/types/choices.py` (replace inline `field_info.get_default(...)` with `field_default`)
- Modify: `src/pydantic_studio/types/unions.py` (replace inline call with `field_default`)
- Test: rely on existing test suite — extraction is pure refactor

- [ ] **Step 1: Create `src/pydantic_studio/types/utils.py`**

```python
"""Shared helpers for type builders.

Currently exports ``field_default`` — the canonical "give me the field's
default, normalized to None if Pydantic considers it undefined" function
that every builder needs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def field_default(field_info: FieldInfo) -> Any:
    """Return ``field_info``'s default value, or ``None`` if undefined.

    Pydantic uses ``PydanticUndefined`` as the sentinel for "no default";
    builders work with concrete values + None, so we normalize here.
    Calls the default factory if present, since the field exists exactly
    when the factory has run successfully.
    """
    d = field_info.get_default(call_default_factory=True)
    return None if d is PydanticUndefined else d
```

- [ ] **Step 2: Replace `_default` in `primitives.py`**

Open `src/pydantic_studio/types/primitives.py`. Find the existing `_default` definition (typically near the top of the module after imports). Delete it. Add the import:

```python
from pydantic_studio.types.utils import field_default
```

Replace every call to `_default(field_info)` with `field_default(field_info)` throughout the file (use search-and-replace).

- [ ] **Step 3: Replace `_default` in `temporal.py`**

Same pattern as Step 2 — delete the local `_default` function and the now-orphaned `from pydantic_core import PydanticUndefined` import (if it's only used by `_default`). Replace calls.

- [ ] **Step 4: Replace `_default` in `network.py`**

Same pattern.

- [ ] **Step 5: Replace `_default` in `special.py`**

Same pattern.

- [ ] **Step 6: Replace inline default-extraction in `choices.py`**

Open `src/pydantic_studio/types/choices.py`. Find lines that look like:

```python
default = field_info.get_default(call_default_factory=True)
if default is PydanticUndefined:
    default = None
```

Replace with:

```python
default = field_default(field_info)
```

Add the import `from pydantic_studio.types.utils import field_default` at the top. Remove `from pydantic_core import PydanticUndefined` if no longer used elsewhere in the file.

- [ ] **Step 7: Replace inline default-extraction in `unions.py`**

Same as Step 6.

- [ ] **Step 8: Run full test suite**

```bash
uv run pytest -q
```

Expected: 319 passed (no regression — pure refactor).

- [ ] **Step 9: Verify ruff is clean**

```bash
uv run ruff check
```

Expected: All checks passed. If `F401 PydanticUndefined imported but unused` fires anywhere, drop the unused import.

- [ ] **Step 10: Commit**

```bash
git add src/pydantic_studio/types/utils.py src/pydantic_studio/types/primitives.py src/pydantic_studio/types/temporal.py src/pydantic_studio/types/network.py src/pydantic_studio/types/special.py src/pydantic_studio/types/choices.py src/pydantic_studio/types/unions.py
git commit -m "refactor(types): extract shared field_default helper to types/utils.py"
```

---

### Task 3: Housekeeping #2 — SecretNode pyright narrowing

**Why:** `SecretNode.to_python` has two `SecretStr(self.value)` / `SecretBytes(self.value)` calls where pyright can't narrow `self.value: str | bytes | None` after `if self.secret_kind == "str"` (the discriminator is a sibling field, not a `Literal` on the value itself). Adding an `isinstance` assert closes 2 of the 12 pyright errors at zero runtime cost.

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py` — `SecretNode.to_python` method
- Test: existing tests in `tests/unit/test_special.py::TestSecretNode` cover the runtime behavior

- [ ] **Step 1: Locate `SecretNode.to_python`**

Open `src/pydantic_studio/tree/nodes.py` and find `SecretNode.to_python`. The current body is roughly:

```python
    def to_python(self) -> Any:
        from pydantic import SecretBytes, SecretStr

        if self.value is None:
            return None
        if self.secret_kind == "str":
            return SecretStr(self.value)
        return SecretBytes(self.value)
```

- [ ] **Step 2: Add isinstance asserts to satisfy pyright**

Replace the body with:

```python
    def to_python(self) -> Any:
        from pydantic import SecretBytes, SecretStr

        if self.value is None:
            return None
        if self.secret_kind == "str":
            assert isinstance(self.value, str), (
                f"SecretNode(secret_kind='str').value must be str, got {type(self.value).__name__}"
            )
            return SecretStr(self.value)
        assert isinstance(self.value, (bytes, bytearray)), (
            f"SecretNode(secret_kind='bytes').value must be bytes, got {type(self.value).__name__}"
        )
        return SecretBytes(self.value)
```

These asserts encode the invariant that `validate_value` enforces at write time. Pyright uses them for type narrowing; at runtime they document the precondition.

Note: ruff's `S101` rule flags `assert` in production code. Check `pyproject.toml`'s `[tool.ruff.lint.select]` — `S101` isn't in the current selection (`["E", "F", "I", "B", "UP", "PT", "RUF", "TC", "SIM"]`), so the asserts won't trigger. If a future ruff config adds S, switch to explicit `if/raise TypeError` instead.

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_special.py::TestSecretNode -v
```

Expected: All tests pass (the asserts hold for every legitimate code path).

- [ ] **Step 4: Run pyright**

```bash
uv run pyright src/pydantic_studio 2>&1 | tail -3
```

Expected: 10 errors (down from 12 — the 2 SecretNode errors are gone).

- [ ] **Step 5: Verify ruff**

```bash
uv run ruff check
```

Expected: All checks passed.

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py
git commit -m "fix(types): SecretNode.to_python — narrow self.value via isinstance for pyright"
```

---

### Task 4: Housekeeping #3 — CLI `k_node.value` pyright false positive

**Why:** `MappingNode.entries` is annotated `list[tuple[AnyNode, AnyNode]]`, so the CLI's `_walk` method sees `k_node: AnyNode` and pyright reports 4 errors (`Cannot access attribute "value"` for SequenceNode/MappingNode/UnionNode/GroupNode). In practice MappingNode keys are always primitive nodes (StringNode/IntNode), but the type system doesn't know. A `cast` or local annotation fixes it.

**Files:**
- Modify: `src/pydantic_studio/cli.py` — the `_walk` function's `MappingNode` branch

- [ ] **Step 1: Locate the offending line**

Open `src/pydantic_studio/cli.py` and find the `_walk` function. Look for the MappingNode branch:

```python
    elif isinstance(node, MappingNode):
        for k_node, v_node in node.entries:
            entry_branch = branch.add(f"[cyan]entry[/cyan] :: {k_node.value!r}")
            _walk(v_node, entry_branch)
```

The `k_node.value` access triggers the false positive.

- [ ] **Step 2: Add a cast to silence pyright**

Replace the loop body with:

```python
    elif isinstance(node, MappingNode):
        for k_node, v_node in node.entries:
            # MappingNode keys are always primitive nodes (StringNode/IntNode/etc.),
            # which all have a `.value` attribute. The discriminated union doesn't
            # narrow here, so suppress pyright with a getattr fallback.
            key_repr = repr(getattr(k_node, "value", k_node.name))
            entry_branch = branch.add(f"[cyan]entry[/cyan] :: {key_repr}")
            _walk(v_node, entry_branch)
```

`getattr(k_node, "value", k_node.name)` is type-safe (every FormNode has `.name`) and falls back gracefully if a future MappingNode somehow holds a non-primitive key.

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_cli.py -v
```

Expected: All CLI tests pass.

- [ ] **Step 4: Run pyright**

```bash
uv run pyright src/pydantic_studio 2>&1 | tail -3
```

Expected: 6 errors (down from 10 — the 4 cli.py errors are gone).

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/cli.py
git commit -m "fix(cli): use getattr fallback for MappingNode key in _walk to satisfy pyright"
```

---

### Task 5: Housekeeping #4 — `version` subcommand test

**Why:** Phase 3's T18 added a `version` subcommand to the CLI as a workaround for typer's single-vs-multi-command quirk. It has no test. A 5-line test closes that coverage gap.

**Files:**
- Modify: `tests/unit/test_cli.py` — add `test_version_subcommand_prints_version`

- [ ] **Step 1: Read the existing `version` command**

Open `src/pydantic_studio/cli.py` and find the `version` command. It typically looks like:

```python
@app.command()
def version() -> None:
    """Print the installed pydantic-studio version."""
    from pydantic_studio import __version__
    typer.echo(__version__)
```

If the implementation differs (e.g., prints "pydantic-studio X.Y.Z" instead of just "X.Y.Z"), adjust the test below to match.

- [ ] **Step 2: Add the test**

In `tests/unit/test_cli.py`, append to the `TestShow` class OR add a new class `TestVersion` after it:

```python
class TestVersion:
    def test_version_subcommand_prints_version(self) -> None:
        from pydantic_studio import __version__

        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output
```

The test verifies that whatever the version command prints, the current `__version__` string appears in the output. That's robust against minor changes to the print format.

- [ ] **Step 3: Run the test**

```bash
uv run pytest tests/unit/test_cli.py::TestVersion -v
```

Expected: 1 PASS.

- [ ] **Step 4: Run full suite**

```bash
uv run pytest -q
```

Expected: 320 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_cli.py
git commit -m "test(cli): cover the version subcommand"
```

---

### Task 6: Add `ruamel.yaml` dependency

**Why:** All YAML I/O work depends on `ruamel.yaml`'s round-trip mode. Add the dep + verify it imports.

**Files:**
- Modify: `pyproject.toml` — add to `dependencies`

- [ ] **Step 1: Update `pyproject.toml`**

Modify the `dependencies` block:

```toml
dependencies = [
  "pydantic>=2.7",
  "typer>=0.12",
  "rich>=13",
  "ruamel.yaml>=0.18",
]
```

- [ ] **Step 2: Sync deps**

```bash
uv sync
```

Expected: `ruamel.yaml` and its transitive `ruamel.yaml.clib` are installed.

- [ ] **Step 3: Smoke check the import**

```bash
uv run python -c "from ruamel.yaml import YAML; y = YAML(typ='rt'); print('OK')"
```

Expected: `OK`.

- [ ] **Step 4: Run full suite (no regressions)**

```bash
uv run pytest -q
```

Expected: 320 passed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: add ruamel.yaml>=0.18 dependency for YAML I/O"
```

---

### Task 7: `load_yaml` — parse YAML file into FormTree

**Why:** Loading is the entry point. We use `ruamel.yaml.YAML(typ='rt')` to get a `CommentedMap`, then pass it as the `existing` data to `build_form_tree`. The CommentedMap is also stashed on the resulting tree so `save_yaml` can preserve user comments later.

**Design choice — `CommentedMap` is a `dict` subclass:** Pass it directly to `build_form_tree` without conversion. Phase 2's existing builders work with any dict-like, including CommentedMap.

**Files:**
- Create: `src/pydantic_studio/io/__init__.py`
- Create: `src/pydantic_studio/io/yaml.py` — `load_yaml` only (save_yaml in Tasks 8-9)
- Create: `tests/unit/test_yaml_io.py`
- Modify: `src/pydantic_studio/__init__.py` — export `load_yaml`
- Modify: `src/pydantic_studio/tree/nodes.py` — add a private `_yaml_source` field on FormTree (CommentedMap | None)
- Modify: `tests/fixtures/schemas.py` — add `Server` schema for YAML golden tests

- [ ] **Step 1: Add a fixture schema for YAML tests**

Append to `tests/fixtures/schemas.py`:

```python
class Server(BaseModel):
    """Minimal schema with descriptions for YAML golden tests."""

    name: str = Field(default="prod", description="Service identifier")
    port: int = Field(default=8080, description="Listening port", ge=1, le=65535)
    debug: bool = Field(default=False, description="Enable debug logging")
```

(The `Field` import should already be present at the top of the fixtures file from earlier phases.)

- [ ] **Step 2: Write failing tests**

Create `tests/unit/test_yaml_io.py`:

```python
"""Tests for YAML I/O — load + save + round-trip + smart comments."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree, load_yaml
from tests.fixtures.schemas import Server


class TestLoadYaml:
    def test_load_basic_file(self, tmp_path: Path) -> None:
        src = tmp_path / "config.yaml"
        src.write_text(
            "name: prod\n"
            "port: 8080\n"
            "debug: true\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        instance = tree.to_instance()
        assert instance.name == "prod"
        assert instance.port == 8080
        assert instance.debug is True

    def test_load_empty_file_yields_defaults(self, tmp_path: Path) -> None:
        src = tmp_path / "empty.yaml"
        src.write_text("", encoding="utf-8")
        tree = load_yaml(src, Server)
        instance = tree.to_instance()
        # All defaults applied.
        assert instance.name == "prod"
        assert instance.port == 8080
        assert instance.debug is False

    def test_load_preserves_source_for_round_trip(self, tmp_path: Path) -> None:
        src = tmp_path / "config.yaml"
        src.write_text(
            "# top-level comment\n"
            "name: alpha  # inline comment\n"
            "port: 9090\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        # _yaml_source must be a CommentedMap (or at least a dict containing the data).
        assert tree.yaml_source is not None
        assert tree.yaml_source.get("name") == "alpha"

    def test_load_unknown_field_is_dropped_silently(
        self, tmp_path: Path
    ) -> None:
        """Per spec O-1: unknown fields drop with a stderr warning by default.
        For now we drop silently in v0.0.4; --strict mode comes in a later
        release. Verify the unknown field doesn't reach the FormTree."""
        src = tmp_path / "config.yaml"
        src.write_text(
            "name: prod\n"
            "port: 8080\n"
            "unknown_field: ignored\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        # FormTree only knows about schema fields.
        assert {f.name for f in tree.root.fields} == {"name", "port", "debug"}

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError):
            load_yaml(src, Server)

    def test_load_malformed_yaml_raises(self, tmp_path: Path) -> None:
        from ruamel.yaml import YAMLError

        src = tmp_path / "bad.yaml"
        src.write_text(
            "name: prod\n"
            "port: [unclosed\n",
            encoding="utf-8",
        )
        with pytest.raises(YAMLError):
            load_yaml(src, Server)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_yaml_io.py::TestLoadYaml -v
```

Expected: All FAIL — `ImportError: cannot import name 'load_yaml' from 'pydantic_studio'`.

- [ ] **Step 4: Add a `yaml_source` field to FormTree**

Open `src/pydantic_studio/tree/nodes.py` and find the `FormTree` class. After the existing fields (e.g., after `draft_path`), add:

```python
    # Stashed source CommentedMap for round-trip save (preserves comments).
    # Excluded from JSON snapshots — re-populated only via load_yaml.
    yaml_source: Any = Field(default=None, exclude=True, repr=False)
```

Notes:
- `exclude=True` means `model_dump_json` skips it (so snapshots don't try to serialize a CommentedMap, which has no JSON representation).
- `repr=False` keeps the field out of `__repr__` so debugging output stays clean.
- The field is `Any`-typed because `CommentedMap` lives in `ruamel.yaml` and we don't want to make that import mandatory at module level — `load_yaml` populates the field; everyone else treats it as opaque.

Verify `Field` is imported at the top of nodes.py from `pydantic`. If not, add it:

```python
from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,  # add if missing
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)
```

- [ ] **Step 5: Create `src/pydantic_studio/io/__init__.py`**

```python
"""Format I/O for pydantic-studio.

Currently exports ``load_yaml`` and ``save_yaml`` (Plan 4). TOML and JSON
writers join in Plan 6.
"""

from __future__ import annotations

from pydantic_studio.io.yaml import load_yaml, save_yaml

__all__ = ["load_yaml", "save_yaml"]
```

(`save_yaml` is added in Tasks 8-9; for this task you can either leave the import broken until Task 8 OR add a stub now. Add a stub:)

Actually for cleaner step ordering — define `save_yaml` as a stub in this task, just enough to make the import work:

```python
# stub — implemented in Tasks 8-9
def save_yaml(*args, **kwargs):  # type: ignore[no-untyped-def]
    raise NotImplementedError("save_yaml lands in Task 8")
```

Place this at the bottom of `yaml.py` (after `load_yaml`).

- [ ] **Step 6: Create `src/pydantic_studio/io/yaml.py`**

```python
"""YAML round-trip I/O via ``ruamel.yaml``.

``load_yaml`` reads a file into a ``CommentedMap`` (preserves comments
and key order), builds a ``FormTree`` from the values, and stashes the
CommentedMap on the tree for ``save_yaml`` to use as a comment source.

``save_yaml`` (Tasks 8-9) writes a schema-ordered CommentedMap whose
values come from ``tree.to_python()`` and whose comments come from the
stashed source (preserving user comments) or from ``FieldInfo.description``
(auto-generated for new keys).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML

from pydantic_studio import build_form_tree

if TYPE_CHECKING:
    from pydantic import BaseModel

    from pydantic_studio.tree.nodes import FormTree


def _yaml() -> YAML:
    """Build a ruamel YAML instance configured for round-trip I/O."""
    y = YAML(typ="rt")
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def load_yaml(path: Path, schema: type[BaseModel]) -> FormTree:
    """Load a YAML file into a FormTree bound to ``schema``.

    Args:
        path: Path to a YAML file. Must exist; missing files raise
            FileNotFoundError. Malformed YAML raises ruamel.yaml.YAMLError.
        schema: A Pydantic BaseModel subclass — drives field-level
            type construction.

    Returns:
        FormTree with values populated from the file. Fields absent from
        the file get their schema defaults. Fields in the file but not in
        the schema are dropped (silent in v0.0.4; --strict mode comes later).
        ``tree.yaml_source`` carries the parsed CommentedMap for save_yaml's
        comment-preservation pass.
    """
    path = Path(path)
    yaml = _yaml()
    with path.open("r", encoding="utf-8") as f:
        cm: Any = yaml.load(f)
    if cm is None:  # empty file
        cm = {}
    # CommentedMap is a dict subclass — pass directly to build_form_tree.
    # Unknown keys are filtered automatically because GroupBuilder iterates
    # only over schema fields.
    tree = build_form_tree(schema, existing=dict(cm))
    tree.yaml_source = cm
    return tree


# Stub — implemented in Tasks 8-9.
def save_yaml(tree: FormTree, path: Path) -> None:
    raise NotImplementedError("save_yaml lands in Task 8")
```

Note: `dict(cm)` creates a plain dict from the CommentedMap before passing to `build_form_tree`. This ensures any builders that introspect the dict type don't get tripped up by CommentedMap's extra metadata.

- [ ] **Step 7: Export `load_yaml` and `save_yaml` from the package**

In `src/pydantic_studio/__init__.py`, add the imports:

```python
from pydantic_studio.io import load_yaml, save_yaml
```

And add to `__all__`:

```python
    "load_yaml",
    "save_yaml",
```

(Place alphabetically.)

- [ ] **Step 8: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_yaml_io.py::TestLoadYaml -v
```

Expected: 6 PASS.

If `test_load_unknown_field_is_dropped_silently` fails, the GroupBuilder may be raising on unknown keys instead of filtering. Check `src/pydantic_studio/types/models.py::GroupBuilder.build`. In Phase 2 it should iterate `schema.model_fields` and pull each from `existing` — extra keys in `existing` are ignored.

- [ ] **Step 9: Run full suite**

```bash
uv run pytest -q
```

Expected: 326 passed (320 + 6 new).

- [ ] **Step 10: Verify ruff**

```bash
uv run ruff check
```

- [ ] **Step 11: Commit**

```bash
git add src/pydantic_studio/io/__init__.py src/pydantic_studio/io/yaml.py src/pydantic_studio/tree/nodes.py src/pydantic_studio/__init__.py tests/unit/test_yaml_io.py tests/fixtures/schemas.py
git commit -m "feat(io): load_yaml — parse YAML into FormTree via ruamel round-trip"
```

---

### Task 8: `save_yaml` for new files (auto-generate description comments)

**Why:** When the target file doesn't exist, `save_yaml` builds a fresh `CommentedMap` from `tree.to_python()`, attaches description comments from `FieldInfo.description`, and writes atomically (temp file + rename, per spec §12).

**Files:**
- Modify: `src/pydantic_studio/io/yaml.py` — implement `save_yaml` for the new-file case
- Modify: `tests/unit/test_yaml_io.py` — add `TestSaveYamlNewFile`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_yaml_io.py`:

```python
class TestSaveYamlNewFile:
    """save_yaml when no source file exists — must auto-generate
    description comments from the schema."""

    def test_save_creates_file_with_values(self, tmp_path: Path) -> None:
        from pydantic_studio import save_yaml

        tree = build_form_tree(Server)
        out = tmp_path / "config.yaml"
        save_yaml(tree, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        # Default values appear.
        assert "prod" in content
        assert "8080" in content

    def test_save_emits_description_comments(self, tmp_path: Path) -> None:
        from pydantic_studio import save_yaml

        tree = build_form_tree(Server)
        out = tmp_path / "config.yaml"
        save_yaml(tree, out)
        content = out.read_text(encoding="utf-8")
        # Each field's description should appear as a comment.
        assert "Service identifier" in content
        assert "Listening port" in content
        assert "Enable debug logging" in content

    def test_save_preserves_schema_field_order(self, tmp_path: Path) -> None:
        from pydantic_studio import save_yaml

        tree = build_form_tree(Server)
        out = tmp_path / "config.yaml"
        save_yaml(tree, out)
        content = out.read_text(encoding="utf-8")
        # Per spec §10.1 rule #1: schema definition order, not arbitrary.
        # Server defines name → port → debug.
        i_name = content.index("name:")
        i_port = content.index("port:")
        i_debug = content.index("debug:")
        assert i_name < i_port < i_debug

    def test_save_round_trip_load_back(self, tmp_path: Path) -> None:
        """Save a tree, reload it, confirm the FormTree state matches."""
        tree = build_form_tree(Server)
        tree.set_value("port", 9999)
        out = tmp_path / "config.yaml"
        from pydantic_studio import save_yaml

        save_yaml(tree, out)
        reloaded = load_yaml(out, Server)
        instance = reloaded.to_instance()
        assert instance.port == 9999
        assert instance.name == "prod"  # default unchanged

    def test_save_atomic_temp_rename(self, tmp_path: Path) -> None:
        """A failed write must not corrupt an existing file. We test the
        atomicity by writing twice and checking no .tmp leftovers."""
        from pydantic_studio import save_yaml

        tree = build_form_tree(Server)
        out = tmp_path / "config.yaml"
        save_yaml(tree, out)
        save_yaml(tree, out)
        # No temp files left behind.
        leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp-")]
        assert leftovers == []

    def test_save_creates_parent_directory(self, tmp_path: Path) -> None:
        """Like draft_save, save_yaml should create parent dirs as needed."""
        from pydantic_studio import save_yaml

        tree = build_form_tree(Server)
        out = tmp_path / "nested" / "subdir" / "config.yaml"
        save_yaml(tree, out)
        assert out.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_yaml_io.py::TestSaveYamlNewFile -v
```

Expected: All FAIL with `NotImplementedError: save_yaml lands in Task 8`.

- [ ] **Step 3: Implement `save_yaml` for the new-file path**

Open `src/pydantic_studio/io/yaml.py`. Replace the stub `save_yaml` with:

```python
import os
import tempfile

from pydantic.fields import FieldInfo
from ruamel.yaml.comments import CommentedMap


def save_yaml(tree: FormTree, path: Path) -> None:
    """Write a FormTree to a YAML file with smart-comment generation.

    Behavior:
    - If ``path`` does not exist: builds a new CommentedMap from
      ``tree.to_python()`` with description comments derived from each
      field's ``FieldInfo.description``.
    - If ``path`` exists OR ``tree.yaml_source`` carries a stashed
      CommentedMap (loaded via ``load_yaml``): preserves user-edited
      comments. (Implemented in Task 9 — for now this branch is identical
      to the new-file branch.)

    The write is atomic: writes to a temp file in the same directory,
    then ``os.replace``s into place. Parent directories are created as
    needed (mirroring ``draft_save``).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    schema = tree.schema_class
    if schema is None:
        msg = "tree.schema_class is None; cannot derive description comments"
        raise ValueError(msg)

    cm = _build_commented_map(tree.to_python(), schema)
    yaml = _yaml()

    fd, tmp = tempfile.mkstemp(prefix=".tmp-yaml-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(cm, f)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _build_commented_map(
    data: dict[str, Any], schema: type[BaseModel]
) -> CommentedMap:
    """Construct a CommentedMap whose keys follow ``schema``'s definition
    order and whose entries carry description comments.

    Nested BaseModel fields recurse — their nested CommentedMaps also get
    description comments per the nested schema's FieldInfo.
    """
    cm = CommentedMap()
    for field_name, field_info in schema.model_fields.items():
        if field_name not in data:
            continue
        value = data[field_name]
        nested_schema = _nested_schema_class(field_info)
        if isinstance(value, dict) and nested_schema is not None:
            cm[field_name] = _build_commented_map(value, nested_schema)
        else:
            cm[field_name] = value
        if field_info.description:
            # Place description as a comment BEFORE the key.
            cm.yaml_set_comment_before_after_key(
                field_name,
                before=field_info.description,
            )
    return cm


def _nested_schema_class(field_info: FieldInfo) -> type[BaseModel] | None:
    """If ``field_info`` is a BaseModel field, return the model class.
    Otherwise return None.

    Used by ``_build_commented_map`` to recurse into nested groups for
    description-comment generation.
    """
    from pydantic import BaseModel

    annotation = field_info.annotation
    if annotation is None:
        return None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None
```

Note: `cm.yaml_set_comment_before_after_key(key, before=text)` is the ruamel.yaml API for placing a comment line above a specific key. The `before` argument is the comment text (without the leading `#`).

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_yaml_io.py::TestSaveYamlNewFile -v
```

Expected: 6 PASS.

If `test_save_emits_description_comments` fails, double-check that `yaml_set_comment_before_after_key`'s output includes the description text. ruamel.yaml may prepend `# ` automatically or require it manually — adjust the call if needed. A defensive variant:

```python
            cm.yaml_set_comment_before_after_key(
                field_name,
                before=f"{field_info.description}",
            )
```

If the comment appears as `# Service identifier`, you're good. If it appears as `# # Service identifier` (double-hash), drop the leading `#` from the `before=` argument.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
```

Expected: 332 passed.

- [ ] **Step 6: Verify ruff**

```bash
uv run ruff check
```

- [ ] **Step 7: Commit**

```bash
git add src/pydantic_studio/io/yaml.py tests/unit/test_yaml_io.py
git commit -m "feat(io): save_yaml writes new files with auto-generated description comments + atomic rename"
```

---

### Task 9: `save_yaml` preserves user comments on edit

**Why:** Per spec §10.1 rule #3, "User comments on existing fields = preserved verbatim if the field still exists". When the source CommentedMap is available (either via the file already existing OR via `tree.yaml_source` from a previous `load_yaml`), we copy comments forward instead of regenerating them from `FieldInfo.description`.

**Algorithm:** for each field in the schema, if the source has a comment for that key, use it; otherwise use the description comment. Drop keys not in the schema (rule #4 — with stderr warning, deferred to v0.0.5; for v0.0.4 silent drop).

**Files:**
- Modify: `src/pydantic_studio/io/yaml.py` — extend `save_yaml` and `_build_commented_map`
- Modify: `tests/unit/test_yaml_io.py` — add `TestSaveYamlPreservesComments`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_yaml_io.py`:

```python
class TestSaveYamlPreservesComments:
    """When a source file or yaml_source exists, save_yaml must preserve
    user-edited comments on fields that still exist in the schema."""

    def test_user_comment_survives_round_trip(self, tmp_path: Path) -> None:
        from pydantic_studio import save_yaml

        # User-authored YAML with a custom comment.
        src = tmp_path / "config.yaml"
        src.write_text(
            "# my custom note about the service\n"
            "name: prod\n"
            "port: 8080\n"
            "debug: false\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        tree.set_value("port", 9090)
        save_yaml(tree, src)

        content = src.read_text(encoding="utf-8")
        # User comment must still appear.
        assert "my custom note about the service" in content
        # Updated value applied.
        assert "9090" in content
        assert "8080" not in content

    def test_unknown_field_is_dropped_on_save(self, tmp_path: Path) -> None:
        """Per spec §10.1 rule #4 — fields no longer in the schema get
        dropped on save."""
        from pydantic_studio import save_yaml

        src = tmp_path / "config.yaml"
        src.write_text(
            "name: prod\n"
            "port: 8080\n"
            "obsolete_field: gone\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        save_yaml(tree, src)
        content = src.read_text(encoding="utf-8")
        assert "obsolete_field" not in content
        assert "gone" not in content

    def test_save_to_existing_file_without_load(self, tmp_path: Path) -> None:
        """If the user calls save_yaml with a tree that was NOT loaded from
        the target path but the path already exists, comments from the file
        should still be preserved (re-load on save semantics)."""
        from pydantic_studio import save_yaml

        # Pre-existing file with a comment.
        src = tmp_path / "config.yaml"
        src.write_text(
            "# pre-existing comment\n"
            "name: alpha\n"
            "port: 7777\n",
            encoding="utf-8",
        )

        # Build a fresh tree (NOT loaded from the file).
        tree = build_form_tree(Server)
        tree.set_value("port", 9090)
        save_yaml(tree, src)

        content = src.read_text(encoding="utf-8")
        assert "pre-existing comment" in content
        assert "9090" in content

    def test_inline_comment_preserved(self, tmp_path: Path) -> None:
        """Inline (end-of-line) comments must also survive."""
        from pydantic_studio import save_yaml

        src = tmp_path / "config.yaml"
        src.write_text(
            "name: prod  # production deployment\n"
            "port: 8080  # standard HTTP\n"
            "debug: false\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        tree.set_value("port", 9090)
        save_yaml(tree, src)

        content = src.read_text(encoding="utf-8")
        assert "production deployment" in content
        assert "standard HTTP" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_yaml_io.py::TestSaveYamlPreservesComments -v
```

Expected: All FAIL — `save_yaml` currently regenerates comments from scratch.

- [ ] **Step 3: Extend `save_yaml` to load source comments**

Modify `save_yaml` in `src/pydantic_studio/io/yaml.py`:

```python
def save_yaml(tree: FormTree, path: Path) -> None:
    """Write a FormTree to a YAML file with smart-comment generation.

    Resolves the source CommentedMap in this priority order:
    1. ``tree.yaml_source`` (set by ``load_yaml``)
    2. The current contents of ``path`` (if it exists)
    3. None (write a fresh map with description comments)

    User comments from the source are preserved on fields that still
    exist in the schema. New fields get description comments from
    ``FieldInfo.description``. Fields removed from the schema are dropped.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    schema = tree.schema_class
    if schema is None:
        msg = "tree.schema_class is None; cannot derive description comments"
        raise ValueError(msg)

    source: CommentedMap | None = None
    if tree.yaml_source is not None:
        source = tree.yaml_source
    elif path.exists():
        yaml_loader = _yaml()
        with path.open("r", encoding="utf-8") as f:
            loaded = yaml_loader.load(f)
        if isinstance(loaded, CommentedMap):
            source = loaded

    cm = _build_commented_map(tree.to_python(), schema, source)
    yaml = _yaml()

    fd, tmp = tempfile.mkstemp(prefix=".tmp-yaml-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(cm, f)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
```

Update `_build_commented_map` to take the source and copy comments forward:

```python
def _build_commented_map(
    data: dict[str, Any],
    schema: type[BaseModel],
    source: CommentedMap | None = None,
) -> CommentedMap:
    """Construct a CommentedMap with keys in schema definition order.

    Comment selection per key:
    1. If ``source`` has a user comment on this key, copy it forward.
    2. Otherwise, fall back to ``FieldInfo.description``.
    3. If neither, the key gets no comment.

    Nested BaseModel fields recurse — the nested source (if any) is
    threaded through.
    """
    cm = CommentedMap()
    for field_name, field_info in schema.model_fields.items():
        if field_name not in data:
            continue
        value = data[field_name]
        nested_schema = _nested_schema_class(field_info)
        nested_source: CommentedMap | None = None
        if (
            source is not None
            and field_name in source
            and isinstance(source[field_name], CommentedMap)
        ):
            nested_source = source[field_name]

        if isinstance(value, dict) and nested_schema is not None:
            cm[field_name] = _build_commented_map(
                value, nested_schema, nested_source
            )
        else:
            cm[field_name] = value

        # Copy the source comment if present, else use the description.
        copied = _copy_comment_if_present(source, cm, field_name)
        if not copied and field_info.description:
            cm.yaml_set_comment_before_after_key(
                field_name,
                before=field_info.description,
            )
    return cm


def _copy_comment_if_present(
    source: CommentedMap | None, target: CommentedMap, key: str
) -> bool:
    """If ``source`` has any comments associated with ``key``, copy them
    onto ``target``. Returns True if a comment was copied.

    ruamel.yaml stores comments on the parent CommentedMap in ``ca.items``
    (a dict keyed by child name → list of CommentToken). We don't try to
    parse the structure — we just copy the entry over.
    """
    if source is None or key not in source:
        return False
    src_ca = getattr(source, "ca", None)
    if src_ca is None:
        return False
    src_items = src_ca.items.get(key)
    if not src_items:
        return False
    # Ensure the target's ca.items dict exists, then copy.
    target.ca.items[key] = src_items
    return True
```

Note: ruamel.yaml's comment storage is on `CommentedMap.ca.items[key]`, a list of `CommentToken` objects. Copying the list reference forward is the simplest way to preserve every kind of comment (before, inline, after) without parsing structure.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_yaml_io.py::TestSaveYamlPreservesComments -v
```

Expected: 4 PASS.

If `test_user_comment_survives_round_trip` fails because the comment is duplicated (description AND user comment appear), the issue is that `_copy_comment_if_present` returned True but `_build_commented_map` still added the description fallback. Re-check the `if not copied and field_info.description:` guard.

If `test_inline_comment_preserved` fails — inline comments live in the same `ca.items[key]` list but at a different index. Copying the whole list (as we do) should cover both before-key and inline comments. If only one survives, the copy mechanism may need to be more granular; in that case use `target.ca.items[key] = list(src_items)` to detach the lists.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
```

Expected: 336 passed.

- [ ] **Step 6: Verify ruff**

```bash
uv run ruff check
```

- [ ] **Step 7: Commit**

```bash
git add src/pydantic_studio/io/yaml.py tests/unit/test_yaml_io.py
git commit -m "feat(io): save_yaml preserves user comments on edit (round-trip via source CommentedMap)"
```

---

### Task 10: CLI `fill` subcommand — emit YAML stub

**Why:** `pydantic-studio fill <module:Class> [--out FILE]` writes a default-populated YAML stub for the schema. This is the primary "give me a starter config" workflow.

**Files:**
- Modify: `src/pydantic_studio/cli.py` — add `fill` command
- Modify: `tests/unit/test_cli.py` — add `TestFill`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_cli.py`:

```python
class TestFill:
    def test_fill_emits_stub_to_stdout(self) -> None:
        result = runner.invoke(app, ["fill", "tests.fixtures.schemas:Server"])
        assert result.exit_code == 0
        # Schema fields appear in the stdout YAML.
        assert "name:" in result.output
        assert "port:" in result.output
        # Description comments appear.
        assert "Service identifier" in result.output

    def test_fill_writes_to_out_file(self, tmp_path) -> None:
        out = tmp_path / "config.yaml"
        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Server", "--out", str(out)],
        )
        assert result.exit_code == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "name:" in content
        assert "Listening port" in content

    def test_fill_unknown_schema_errors(self) -> None:
        result = runner.invoke(app, ["fill", "nosuch:Foo"])
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_cli.py::TestFill -v
```

Expected: All FAIL — no `fill` command.

- [ ] **Step 3: Implement `fill`**

In `src/pydantic_studio/cli.py`, add (after the existing `show` and `version` commands):

```python
@app.command()
def fill(
    target: str = typer.Argument(  # noqa: B008
        ..., help="module:Class identifier of the Pydantic schema."
    ),
    out: Path | None = typer.Option(  # noqa: B008
        None,
        "--out",
        "-o",
        help="Path to write the YAML stub. If omitted, write to stdout.",
    ),
) -> None:
    """Emit a YAML stub populated with the schema's defaults.

    With ``--out FILE``, writes to that path with description comments.
    Without ``--out``, writes to stdout.
    """
    import io

    from pydantic_studio import build_form_tree, save_yaml

    schema = _load_schema(target)
    tree = build_form_tree(schema)
    if out is not None:
        save_yaml(tree, out)
        typer.echo(f"Wrote {out}")
        return
    # Stdout path: write to a temp file then echo its contents (avoids
    # duplicating save_yaml's CommentedMap-building logic). Use io.StringIO
    # via the YAML object directly.
    from pydantic_studio.io.yaml import _build_commented_map, _yaml

    schema_class = tree.schema_class
    if schema_class is None:
        typer.secho(
            "FormTree.schema_class is None — cannot render YAML",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    cm = _build_commented_map(tree.to_python(), schema_class, None)
    buf = io.StringIO()
    _yaml().dump(cm, buf)
    typer.echo(buf.getvalue(), nl=False)
```

The `Path | None` annotation requires `from pathlib import Path` at the top of the module — verify (it should already be imported from earlier work; if not, add it).

The `# noqa: B008` comments suppress ruff's "function call in default argument" warning, which fires for typer's `Argument`/`Option` defaults — this is the canonical typer pattern.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli.py::TestFill -v
```

Expected: 3 PASS.

- [ ] **Step 5: Manual smoke test**

```bash
uv run pydantic-studio fill tests.fixtures.schemas:Server
```

Expected output (formatted YAML with description comments):

```yaml
# Service identifier
name: prod
# Listening port
port: 8080
# Enable debug logging
debug: false
```

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -q
```

Expected: 339 passed.

- [ ] **Step 7: Verify ruff**

```bash
uv run ruff check
```

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): fill subcommand — emit YAML stub from schema defaults"
```

---

### Task 11: CLI `run` and `check` subcommands

**Why:** `run` loads a YAML file, validates against the schema, prints the resulting model. `check` does the same but stays silent on success — exits non-zero only when validation fails. Both are the building blocks of CI integration ("does my config still parse?").

**Files:**
- Modify: `src/pydantic_studio/cli.py` — add `run` and `check`
- Modify: `tests/unit/test_cli.py` — add `TestRun` + `TestCheck`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_cli.py`:

```python
class TestRun:
    def test_run_prints_validated_model(self, tmp_path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "name: prod\n"
            "port: 8080\n"
            "debug: true\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["run", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code == 0
        # The model dump appears in stdout.
        assert "name='prod'" in result.output or "name: prod" in result.output
        assert "8080" in result.output
        assert "debug=True" in result.output or "debug: true" in result.output.lower()

    def test_run_validation_failure_exits_nonzero(self, tmp_path) -> None:
        cfg = tmp_path / "bad.yaml"
        cfg.write_text(
            "name: prod\n"
            "port: 99999\n"  # exceeds Server.port's le=65535
            "debug: false\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["run", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code != 0
        # Useful: surface the field that failed.
        assert "port" in result.output.lower()


class TestCheck:
    def test_check_silent_on_valid(self, tmp_path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "name: prod\n"
            "port: 8080\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["check", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code == 0
        # Output should be brief — just an OK marker, not the full model.
        # The exact text is up to the implementation; verify it's short.
        assert len(result.output) < 200

    def test_check_invalid_exits_nonzero(self, tmp_path) -> None:
        cfg = tmp_path / "bad.yaml"
        cfg.write_text(
            "name: prod\n"
            "port: -5\n",  # below Server.port's ge=1
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["check", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_cli.py::TestRun tests/unit/test_cli.py::TestCheck -v
```

Expected: All FAIL — `run` and `check` don't exist.

- [ ] **Step 3: Implement both commands**

In `src/pydantic_studio/cli.py`, append:

```python
@app.command()
def run(
    target: str = typer.Argument(..., help="module:Class identifier."),  # noqa: B008
    file: Path = typer.Argument(..., help="Path to a YAML config file."),  # noqa: B008
) -> None:
    """Load a YAML file, validate against the schema, print the model dump."""
    from pydantic import ValidationError

    from pydantic_studio import load_yaml
    from pydantic_studio.exceptions import ValidationFailedError

    schema = _load_schema(target)
    try:
        tree = load_yaml(file, schema)
        instance = tree.to_instance()
    except (ValidationError, ValidationFailedError) as e:
        typer.secho(f"Validation failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    typer.echo(repr(instance))


@app.command()
def check(
    target: str = typer.Argument(..., help="module:Class identifier."),  # noqa: B008
    file: Path = typer.Argument(..., help="Path to a YAML config file."),  # noqa: B008
) -> None:
    """Load a YAML file and validate it against the schema. Silent on success."""
    from pydantic import ValidationError

    from pydantic_studio import load_yaml
    from pydantic_studio.exceptions import ValidationFailedError

    schema = _load_schema(target)
    try:
        tree = load_yaml(file, schema)
        tree.to_instance()
    except (ValidationError, ValidationFailedError) as e:
        typer.secho(f"{file}: validation failed", fg=typer.colors.RED, err=True)
        for line in str(e).splitlines():
            typer.echo(f"  {line}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo(f"{file}: OK")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_cli.py::TestRun tests/unit/test_cli.py::TestCheck -v
```

Expected: 4 PASS.

If `test_run_validation_failure_exits_nonzero` fails because `port=99999` somehow validates (the YAML loader might coerce), check that `Server.port`'s `le=65535` is enforced. Pydantic's `Field(le=65535)` should reject 99999 cleanly.

- [ ] **Step 5: Manual smoke**

```bash
echo "name: prod
port: 8080
debug: true" > /tmp/cfg.yaml
uv run pydantic-studio run tests.fixtures.schemas:Server /tmp/cfg.yaml
```

Expected: prints `Server(name='prod', port=8080, debug=True)` (or similar — exact `repr` depends on Pydantic version).

```bash
uv run pydantic-studio check tests.fixtures.schemas:Server /tmp/cfg.yaml
```

Expected: `/tmp/cfg.yaml: OK`.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -q
```

Expected: 343 passed.

- [ ] **Step 7: Verify ruff**

```bash
uv run ruff check
```

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): run + check subcommands for YAML validation"
```

---

### Task 12: README + version bump v0.0.4

**Why:** Plan 4 ships v0.0.4. Update version strings; document YAML I/O + new CLI subcommands.

**Files:**
- Modify: `pyproject.toml` — `version = "0.0.4"`
- Modify: `src/pydantic_studio/__init__.py` — `__version__ = "0.0.4"`
- Modify: `README.md` — append Phase 4 section

- [ ] **Step 1: Bump versions**

In `pyproject.toml`: change `version = "0.0.3"` to `version = "0.0.4"`.
In `src/pydantic_studio/__init__.py`: change `__version__ = "0.0.3"` to `__version__ = "0.0.4"`.

- [ ] **Step 2: Update README**

Append to `README.md` (after the existing Phase 3 section):

````markdown
## YAML I/O (v0.0.4)

Pydantic Studio now reads and writes YAML config files using `ruamel.yaml`'s round-trip mode. User-edited comments survive an edit; new files get auto-generated description comments from your schema's `Field(description=...)` annotations.

### Generate a stub

```bash
$ uv run pydantic-studio fill mypkg.config:AppSettings --out config.yaml
$ cat config.yaml
# The API URL
api_url: https://api.example.com
# Listening port
port: 8080
# Enable debug logging
debug: false
```

### Load + edit + save

```python
from pathlib import Path
from pydantic_studio import load_yaml, save_yaml
from mypkg.config import AppSettings

tree = load_yaml(Path("config.yaml"), AppSettings)
tree.set_value("port", 9090)
save_yaml(tree, Path("config.yaml"))
# User comments preserved; port now 9090.
```

### Validate without parsing

```bash
$ uv run pydantic-studio check mypkg.config:AppSettings config.yaml
config.yaml: OK

$ uv run pydantic-studio run mypkg.config:AppSettings config.yaml
AppSettings(api_url='https://api.example.com', port=8080, debug=False)
```

### What's not in v0.0.4

- TOML / JSON I/O (Plan 6)
- `pydantic-studio edit` (waits on the renderer phase)
- `${ENV_VAR}` secret-handling templates (deferred to a security pass)

### Smart writer rules

When generating YAML:
1. Field order matches the schema definition (not the file's existing order).
2. Description comments come from `Field(description=...)`.
3. User comments on existing fields are preserved verbatim.
4. Fields removed from the schema are dropped silently (this becomes a stderr warning in a later release).
````

- [ ] **Step 3: Run final test suite + ruff + pyright**

```bash
uv run pytest -q
uv run ruff check
uv run pyright src/pydantic_studio 2>&1 | tail -3
```

Expected: 343 passed; ruff clean; pyright at 6 errors (the 6 closed by T2-T5 stay closed; the 6 carried-over Phase-2 errors persist).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/pydantic_studio/__init__.py README.md
git commit -m "docs: README + version bump for v0.0.4"
```

---

### Task 13: Merge ceremony

**Why:** Tag at the feature tip, `--no-ff` merge to master, delete the feature branch. **DO NOT push** (per user's standing instruction).

- [ ] **Step 1: Verify clean state**

```bash
git status
git log --oneline -5
```

Expected: clean working tree; recent commits include the version bump and YAML/CLI work.

- [ ] **Step 2: Tag the feature tip**

```bash
git tag v0.0.4-phase-4
```

- [ ] **Step 3: Merge to master with --no-ff**

```bash
git checkout master
git merge --no-ff feature/phase-4-yaml-io -m "merge: Phase 4 — YAML I/O + Phase-3 housekeeping"
```

- [ ] **Step 4: Verify final tests on master**

```bash
uv run pytest -q
```

Expected: 343 passed.

- [ ] **Step 5: Delete the feature branch (local only)**

```bash
git branch -d feature/phase-4-yaml-io
```

- [ ] **Step 6: Show final state**

```bash
git log --oneline -10
git tag --list 'v0.0.*'
```

Expected: tag `v0.0.4-phase-4` reachable via the merge commit's second parent. **Do not push.**

---

## Phase 4 — Self-Review Notes

Spec coverage:

| Spec § | Requirement | Task(s) |
|---|---|---|
| § 10 (Format I/O) | YAML read+write via ruamel typ='rt' | T6, T7, T8, T9 |
| § 10.1 #1 (field order) | Schema definition order on save | T8 (`_build_commented_map` iterates `schema.model_fields`) |
| § 10.1 #2 (description comments) | From `FieldInfo.description` | T8 |
| § 10.1 #3 (preserve user comments) | Round-trip via source CommentedMap | T9 |
| § 10.1 #4 (drop deleted fields) | Silent drop in v0.0.4; stderr warning deferred | T9 (silent) |
| § 8 (CLI) | `fill | run | check` subcommands | T10, T11 |
| § 12 (atomic write) | temp file + os.replace | T8 |
| Phase-3 follow-ups | 4 housekeeping items from Final Reviewer | T2, T3, T4, T5 |

Items intentionally deferred to later plans:
- TOML / JSON I/O writers (Plan 6)
- `pydantic-studio edit` (Plan 5+ once renderer ships)
- `${ENV_VAR}` SecretStr templates (security pass)
- Stderr warning for dropped fields on save (rule §10.1 #4 — currently silent)
- Pyright CI baseline assertion (process change; defer to a dedicated CI cleanup release)

Likely failure modes:
- **ruamel.yaml comment API quirks**: `yaml_set_comment_before_after_key` may emit double-`#`. T8 step 4 includes a defensive fallback.
- **CommentedMap in nested groups**: ruamel preserves nested CommentedMap structure on read; T9's `_copy_comment_if_present` walks one level and `_build_commented_map`'s recursion threads `nested_source` for deeper levels. If round-trip drops comments inside nested groups, the recursion is the place to debug.
- **Atomic temp file on Windows**: `os.replace` works cross-platform but the temp file is in the SAME directory as the target. Verify `tmp_path` test fixtures don't accidentally drop a `.tmp-yaml-*` file.

Verification commands (run at end of plan):

```bash
uv run pytest -q                                # 343 passed
uv run ruff check                              # All checks passed
uv run pyright src/pydantic_studio 2>&1 | tail -3  # 6 errors (Phase 2 carryover only)
uv run pydantic-studio --help                  # Lists show, version, fill, run, check
```

---

**End of Plan 4.**
