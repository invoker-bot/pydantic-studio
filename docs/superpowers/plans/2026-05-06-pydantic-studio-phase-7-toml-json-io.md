# pydantic-studio — Phase 7: TOML + JSON I/O Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add TOML and JSON readers/writers symmetric to Phase-4's YAML I/O, plus a format-dispatch layer that picks the right loader/writer based on path extension. Also add a `--format` flag to the existing CLI commands (`fill`, `run`, `check`) so users can override extension inference.

**Architecture:** New `io/toml.py` mirrors `io/yaml.py`'s API (`load_toml(path, schema)`, `save_toml(tree, path)`). New `io/json_.py` (note trailing underscore — `json` is taken by stdlib) mirrors the same for JSON. A new `io/dispatch.py` exports `load_config(path, schema)` and `save_config(tree, path)` that pick the format from the path extension (`.yaml`/`.yml` → YAML, `.toml` → TOML, `.json` → JSON). CLI commands gain a `--format` option that overrides extension detection.

**Tech Stack:** `tomllib` (stdlib) for TOML reads, `tomlkit>=0.13` for TOML writes (preserves comments + key order). JSON uses stdlib `json` for reads and `pydantic.model_dump_json(indent=2)` for writes.

**Spec note:** Per spec §10:
- TOML: tomlkit round-trip preserves comments + key order
- JSON: no comments (accepted limitation per spec line 451)

**Out-of-scope (deferred to Plan 8):** TOML's smart-writer rules for nested arrays of tables (spec O-6: "Spike test in Phase 6. Fallback: JSON-flavoured TOML output without comments preserved."). For Plan 7 we use tomlkit's straightforward dict-to-document conversion + per-key description comments. If a complex nested-array-of-tables schema breaks, document and defer.

---

## File Structure

**New (5):**
- `src/pydantic_studio/io/toml.py` — `load_toml`, `save_toml`
- `src/pydantic_studio/io/json_.py` — `load_json`, `save_json`
- `src/pydantic_studio/io/dispatch.py` — `load_config`, `save_config`, `_format_for_path`
- `tests/unit/test_toml_io.py`
- `tests/unit/test_json_io.py`
- `tests/unit/test_dispatch.py`

**Modified:**
- `src/pydantic_studio/io/__init__.py` — re-export new fns
- `src/pydantic_studio/__init__.py` — export public API
- `src/pydantic_studio/cli.py` — `--format` option on fill/run/check
- `pyproject.toml` — add `tomlkit>=0.13`
- `README.md` — Phase 7 section

---

### Task 1: Branch + tomlkit dependency

- [ ] **Step 1: Branch + verify**

```bash
git checkout master
git checkout -b feature/phase-7-toml-json-io
uv run pytest -q  # 378 baseline
uv run ruff check
```

- [ ] **Step 2: Add tomlkit**

In `pyproject.toml` `dependencies`:

```toml
dependencies = [
  "pydantic>=2.7",
  "typer>=0.12",
  "rich>=13",
  "ruamel.yaml>=0.18",
  "textual>=0.85",
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "jinja2>=3.1",
  "httpx>=0.27",
  "tomlkit>=0.13",
]
```

- [ ] **Step 3: Sync + smoke**

```bash
uv sync
uv run python -c "import tomllib; import tomlkit; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add tomlkit>=0.13 dependency for Phase 7 TOML I/O"
```

---

### Task 2: TOML I/O (load_toml + save_toml)

**Files:**
- Create: `src/pydantic_studio/io/toml.py`
- Create: `tests/unit/test_toml_io.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_toml_io.py`:

```python
"""Tests for TOML I/O — load + save."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import Server


class TestLoadToml:
    def test_load_basic_file(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml

        src = tmp_path / "config.toml"
        src.write_text(
            'name = "prod"\n'
            "port = 8080\n"
            "debug = true\n",
            encoding="utf-8",
        )
        tree = load_toml(src, Server)
        instance = tree.to_instance()
        assert instance.name == "prod"
        assert instance.port == 8080
        assert instance.debug is True

    def test_load_empty_file_yields_defaults(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml

        src = tmp_path / "empty.toml"
        src.write_text("", encoding="utf-8")
        tree = load_toml(src, Server)
        instance = tree.to_instance()
        assert instance.name == "prod"

    def test_load_unknown_field_dropped(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml

        src = tmp_path / "config.toml"
        src.write_text(
            'name = "prod"\n'
            "port = 8080\n"
            'unknown_field = "ignored"\n',
            encoding="utf-8",
        )
        tree = load_toml(src, Server)
        assert {f.name for f in tree.root.fields} == {"name", "port", "debug"}

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml

        with pytest.raises(FileNotFoundError):
            load_toml(tmp_path / "nope.toml", Server)


class TestSaveToml:
    def test_save_creates_file_with_values(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import save_toml

        out = tmp_path / "out.toml"
        tree = build_form_tree(Server)
        save_toml(tree, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "prod" in content
        assert "8080" in content

    def test_save_round_trip(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml, save_toml

        tree = build_form_tree(Server)
        tree.set_value("port", 9090)
        out = tmp_path / "out.toml"
        save_toml(tree, out)
        reloaded = load_toml(out, Server)
        instance = reloaded.to_instance()
        assert instance.port == 9090

    def test_save_emits_description_comments(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import save_toml

        out = tmp_path / "out.toml"
        tree = build_form_tree(Server)
        save_toml(tree, out)
        content = out.read_text(encoding="utf-8")
        assert "Service identifier" in content
        assert "Listening port" in content
```

- [ ] **Step 2: Run — expect FAIL**

```bash
uv run pytest tests/unit/test_toml_io.py -v
```

- [ ] **Step 3: Implement io/toml.py**

Create `src/pydantic_studio/io/toml.py`:

```python
"""TOML round-trip I/O via tomllib (read) + tomlkit (write).

``load_toml`` parses a file into a dict + builds a FormTree. ``save_toml``
emits a tomlkit Document with description comments derived from each
field's ``FieldInfo.description``.
"""

from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomlkit
from tomlkit import comment, document, nl

from pydantic_studio.tree.builder import build_form_tree

if TYPE_CHECKING:
    from pydantic import BaseModel
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.nodes import FormTree


def load_toml(path: str | Path, schema: type[BaseModel]) -> FormTree:
    """Load a TOML file into a FormTree bound to ``schema``.

    Args:
        path: Path to a TOML file.
        schema: Pydantic BaseModel subclass.

    Returns:
        FormTree populated from the file.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
    """
    path = Path(path)
    with path.open("rb") as f:
        data = tomllib.load(f)
    return build_form_tree(schema, existing=data)


def save_toml(tree: FormTree, path: str | Path) -> None:
    """Write a FormTree to a TOML file with description comments.

    Tree is materialized via ``to_instance()`` (mirrors save_yaml's contract).
    Comments come from ``FieldInfo.description``.

    Raises:
        ValidationFailedError: If the tree fails validation.
        ValueError: If schema_class is None.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    schema = tree.schema_class
    if schema is None:
        msg = "tree.schema_class is None; cannot derive description comments"
        raise ValueError(msg)

    instance = tree.to_instance()
    data = instance.model_dump(mode="json")
    doc = _build_document(data, schema)

    fd, tmp = tempfile.mkstemp(prefix=".tmp-toml-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _build_document(data: dict[str, Any], schema: type[BaseModel]) -> Any:
    """Construct a tomlkit Document with description comments per key."""
    doc = document()
    for field_name, field_info in schema.model_fields.items():
        if field_name not in data:
            continue
        value = data[field_name]
        nested_schema = _nested_schema_class(field_info)
        if isinstance(value, dict) and nested_schema is not None:
            doc.add(field_name, _build_document(value, nested_schema))
        else:
            if field_info.description:
                doc.add(comment(field_info.description))
            doc.add(field_name, value)
    return doc


def _nested_schema_class(field_info: FieldInfo) -> type[BaseModel] | None:
    from pydantic import BaseModel

    annotation = field_info.annotation
    if annotation is None:
        return None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/unit/test_toml_io.py -v
uv run pytest -q  # 385 passed
uv run ruff check
git add src/pydantic_studio/io/toml.py tests/unit/test_toml_io.py
git commit -m "feat(io): TOML load + save via tomllib/tomlkit with description comments"
```

---

### Task 3: JSON I/O (load_json + save_json)

**Files:**
- Create: `src/pydantic_studio/io/json_.py` (trailing underscore — avoids stdlib collision)
- Create: `tests/unit/test_json_io.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_json_io.py`:

```python
"""Tests for JSON I/O — load + save."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import Server


class TestLoadJson:
    def test_load_basic_file(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import load_json

        src = tmp_path / "config.json"
        src.write_text(
            '{"name": "prod", "port": 8080, "debug": true}\n',
            encoding="utf-8",
        )
        tree = load_json(src, Server)
        instance = tree.to_instance()
        assert instance.name == "prod"
        assert instance.port == 8080
        assert instance.debug is True

    def test_load_empty_object_yields_defaults(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import load_json

        src = tmp_path / "empty.json"
        src.write_text("{}", encoding="utf-8")
        tree = load_json(src, Server)
        instance = tree.to_instance()
        assert instance.name == "prod"

    def test_load_unknown_field_dropped(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import load_json

        src = tmp_path / "config.json"
        src.write_text(
            '{"name": "prod", "port": 8080, "extra": "ignored"}',
            encoding="utf-8",
        )
        tree = load_json(src, Server)
        assert {f.name for f in tree.root.fields} == {"name", "port", "debug"}


class TestSaveJson:
    def test_save_creates_file_with_values(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import save_json

        out = tmp_path / "out.json"
        tree = build_form_tree(Server)
        save_json(tree, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "prod" in content
        assert "8080" in content

    def test_save_round_trip(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import load_json, save_json

        tree = build_form_tree(Server)
        tree.set_value("port", 9090)
        out = tmp_path / "out.json"
        save_json(tree, out)
        reloaded = load_json(out, Server)
        instance = reloaded.to_instance()
        assert instance.port == 9090

    def test_save_uses_indent_two(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import save_json

        out = tmp_path / "out.json"
        tree = build_form_tree(Server)
        save_json(tree, out)
        content = out.read_text(encoding="utf-8")
        # Indented JSON has newlines + leading spaces.
        assert "\n  " in content
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement io/json_.py**

Create `src/pydantic_studio/io/json_.py`:

```python
"""JSON load + save for pydantic-studio.

JSON does not preserve comments (spec line 451 — accepted limitation).
``save_json`` uses ``model_dump_json(indent=2, by_alias=True)``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_studio.tree.builder import build_form_tree

if TYPE_CHECKING:
    from pydantic import BaseModel

    from pydantic_studio.tree.nodes import FormTree


def load_json(path: str | Path, schema: type[BaseModel]) -> FormTree:
    """Load a JSON file into a FormTree bound to ``schema``.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        json.JSONDecodeError: if the file is malformed.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        msg = f"expected JSON object at top level, got {type(data).__name__}"
        raise ValueError(msg)
    return build_form_tree(schema, existing=data)


def save_json(tree: FormTree, path: str | Path) -> None:
    """Write a FormTree to a JSON file with indent=2.

    Raises:
        ValidationFailedError: if the tree is incomplete/invalid.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    instance = tree.to_instance()
    payload = instance.model_dump_json(indent=2, by_alias=True)

    fd, tmp = tempfile.mkstemp(prefix=".tmp-json-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/unit/test_json_io.py -v
uv run pytest -q  # 391 passed
uv run ruff check
git add src/pydantic_studio/io/json_.py tests/unit/test_json_io.py
git commit -m "feat(io): JSON load + save via stdlib json + model_dump_json"
```

---

### Task 4: Format-dispatch loader / writer

**Files:**
- Create: `src/pydantic_studio/io/dispatch.py`
- Modify: `src/pydantic_studio/io/__init__.py`
- Create: `tests/unit/test_dispatch.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_dispatch.py`:

```python
"""Tests for the format-dispatch load_config / save_config helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from pydantic_studio import build_form_tree
from pydantic_studio.io.dispatch import _format_for_path, load_config, save_config
from tests.fixtures.schemas import Server


class TestFormatForPath:
    def test_yaml(self) -> None:
        assert _format_for_path(Path("x.yaml")) == "yaml"
        assert _format_for_path(Path("x.yml")) == "yaml"

    def test_toml(self) -> None:
        assert _format_for_path(Path("x.toml")) == "toml"

    def test_json(self) -> None:
        assert _format_for_path(Path("x.json")) == "json"

    def test_unknown_extension_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot infer format"):
            _format_for_path(Path("x.xml"))


class TestDispatcher:
    def test_save_load_yaml(self, tmp_path: Path) -> None:
        out = tmp_path / "x.yaml"
        tree = build_form_tree(Server)
        save_config(tree, out)
        reloaded = load_config(out, Server)
        assert reloaded.to_instance().name == "prod"

    def test_save_load_toml(self, tmp_path: Path) -> None:
        out = tmp_path / "x.toml"
        tree = build_form_tree(Server)
        save_config(tree, out)
        reloaded = load_config(out, Server)
        assert reloaded.to_instance().name == "prod"

    def test_save_load_json(self, tmp_path: Path) -> None:
        out = tmp_path / "x.json"
        tree = build_form_tree(Server)
        save_config(tree, out)
        reloaded = load_config(out, Server)
        assert reloaded.to_instance().name == "prod"

    def test_explicit_format_override(self, tmp_path: Path) -> None:
        # File has no extension; we pass the format explicitly.
        out = tmp_path / "config"
        tree = build_form_tree(Server)
        save_config(tree, out, format="yaml")
        reloaded = load_config(out, Server, format="yaml")
        assert reloaded.to_instance().name == "prod"
```

- [ ] **Step 2: Implement dispatch.py**

Create `src/pydantic_studio/io/dispatch.py`:

```python
"""Format-dispatch wrappers for load/save based on path extension."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pydantic import BaseModel

    from pydantic_studio.tree.nodes import FormTree


_Format = Literal["yaml", "toml", "json"]
_EXT_MAP: dict[str, _Format] = {
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
}


def _format_for_path(path: Path) -> _Format:
    ext = path.suffix.lower()
    fmt = _EXT_MAP.get(ext)
    if fmt is None:
        msg = (
            f"cannot infer format from extension {ext!r} on path {path}; "
            f"pass format= explicitly"
        )
        raise ValueError(msg)
    return fmt


def load_config(
    path: str | Path,
    schema: type[BaseModel],
    *,
    format: _Format | None = None,
) -> FormTree:
    """Load a config file into a FormTree, picking parser by extension.

    Args:
        path: file path
        schema: Pydantic BaseModel subclass
        format: optional explicit format override ("yaml"/"toml"/"json")

    Returns:
        FormTree populated from the file.
    """
    path = Path(path)
    fmt = format or _format_for_path(path)
    if fmt == "yaml":
        from pydantic_studio.io.yaml import load_yaml

        return load_yaml(path, schema)
    if fmt == "toml":
        from pydantic_studio.io.toml import load_toml

        return load_toml(path, schema)
    from pydantic_studio.io.json_ import load_json

    return load_json(path, schema)


def save_config(
    tree: FormTree,
    path: str | Path,
    *,
    format: _Format | None = None,
) -> None:
    """Save a FormTree to a config file, picking writer by extension.

    Args:
        tree: FormTree to serialize
        path: target file
        format: optional explicit format override
    """
    path = Path(path)
    fmt = format or _format_for_path(path)
    if fmt == "yaml":
        from pydantic_studio.io.yaml import save_yaml

        save_yaml(tree, path)
        return
    if fmt == "toml":
        from pydantic_studio.io.toml import save_toml

        save_toml(tree, path)
        return
    from pydantic_studio.io.json_ import save_json

    save_json(tree, path)
```

- [ ] **Step 3: Update io/__init__.py**

```python
"""Format I/O for pydantic-studio."""

from __future__ import annotations

from pydantic_studio.io.dispatch import load_config, save_config
from pydantic_studio.io.json_ import load_json, save_json
from pydantic_studio.io.toml import load_toml, save_toml
from pydantic_studio.io.yaml import load_yaml, save_yaml

__all__ = [
    "load_config",
    "load_json",
    "load_toml",
    "load_yaml",
    "save_config",
    "save_json",
    "save_toml",
    "save_yaml",
]
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/unit/test_dispatch.py -v
uv run pytest -q  # 398 passed
uv run ruff check
git add src/pydantic_studio/io tests/unit/test_dispatch.py
git commit -m "feat(io): load_config + save_config dispatch by extension"
```

---

### Task 5: CLI --format flag on fill/run/check

**Files:**
- Modify: `src/pydantic_studio/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/test_cli.py` (at end of file):

```python
class TestFillFormats:
    def test_fill_emits_toml(self, tmp_path) -> None:
        out = tmp_path / "out.toml"
        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Server", "--out", str(out)],
        )
        assert result.exit_code == 0
        content = out.read_text(encoding="utf-8")
        # TOML uses `key = value`.
        assert "name =" in content or 'name = "prod"' in content

    def test_fill_emits_json(self, tmp_path) -> None:
        out = tmp_path / "out.json"
        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Server", "--out", str(out)],
        )
        assert result.exit_code == 0
        content = out.read_text(encoding="utf-8")
        # JSON has braces.
        assert content.lstrip().startswith("{")
        assert '"name"' in content


class TestRunFormats:
    def test_run_loads_toml(self, tmp_path) -> None:
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            'name = "prod"\nport = 8080\ndebug = true\n',
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["run", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code == 0
        assert "prod" in result.output

    def test_run_loads_json(self, tmp_path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(
            '{"name": "prod", "port": 8080, "debug": true}\n',
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["run", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code == 0
        assert "prod" in result.output
```

- [ ] **Step 2: Update CLI to use load_config/save_config**

In `src/pydantic_studio/cli.py`, replace the existing `fill` / `run` / `check` commands' bodies to use the dispatch helpers.

For `fill`:

```python
@app.command()
def fill(
    target: str = typer.Argument(..., help="module:Class identifier."),
    out: Path | None = typer.Option(  # noqa: B008
        None,
        "--out",
        "-o",
        help="Path to write the stub. Format inferred from extension. If omitted, write YAML to stdout.",
    ),
) -> None:
    """Emit a config stub populated with the schema's defaults."""
    import io as _io

    from pydantic_studio import build_form_tree
    from pydantic_studio.io.dispatch import save_config

    schema = _load_schema(target)
    tree = build_form_tree(schema)
    if out is not None:
        save_config(tree, out)
        typer.echo(f"Wrote {out}")
        return
    # Stdout path: YAML (matches v0.0.4 default).
    from pydantic_studio.io.yaml import _build_commented_map, _yaml

    schema_class = tree.schema_class
    if schema_class is None:
        typer.secho(
            "FormTree.schema_class is None — cannot render YAML",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    instance = tree.to_instance()
    data = instance.model_dump(mode="python")
    cm = _build_commented_map(data, schema_class, None)
    buf = _io.StringIO()
    _yaml().dump(cm, buf)
    typer.echo(buf.getvalue(), nl=False)
```

For `run`:

```python
@app.command()
def run(
    target: str = typer.Argument(..., help="module:Class identifier."),
    file: Path = typer.Argument(..., help="Path to a config file (extension picks format)."),  # noqa: B008
) -> None:
    """Load a config file, validate against the schema, print the model dump."""
    from pydantic import ValidationError

    from pydantic_studio.exceptions import ValidationFailedError
    from pydantic_studio.io.dispatch import load_config

    schema = _load_schema(target)
    try:
        tree = load_config(file, schema)
        instance = tree.to_instance()
    except (ValidationError, ValidationFailedError) as e:
        typer.secho(f"Validation failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    typer.echo(repr(instance))
```

For `check`:

```python
@app.command()
def check(
    target: str = typer.Argument(..., help="module:Class identifier."),
    file: Path = typer.Argument(..., help="Path to a config file (extension picks format)."),  # noqa: B008
) -> None:
    """Load + validate. Silent on success."""
    from pydantic import ValidationError

    from pydantic_studio.exceptions import ValidationFailedError
    from pydantic_studio.io.dispatch import load_config

    schema = _load_schema(target)
    try:
        tree = load_config(file, schema)
        tree.to_instance()
    except (ValidationError, ValidationFailedError) as e:
        typer.secho(f"{file}: validation failed", fg=typer.colors.RED, err=True)
        for line in str(e).splitlines():
            typer.echo(f"  {line}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo(f"{file}: OK")
```

For `edit` (Phase 5/6's existing `edit`): also switch to load_config:

```python
    if file is not None and file.exists():
        from pydantic_studio.io.dispatch import load_config

        tree = load_config(file, schema)
    else:
        tree = build_form_tree(schema)
```

(Keep the `if frontend == "tui" / "web"` dispatch from Phase 6.)

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/test_cli.py -v
uv run pytest -q  # 402 passed
uv run ruff check
git add src/pydantic_studio/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): fill/run/check/edit dispatch by file extension via load_config/save_config"
```

---

### Task 6: Public API + version + README

**Files:**
- Modify: `src/pydantic_studio/__init__.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] **Step 1: Bump version + add exports**

`pyproject.toml`: `version = "0.0.7"`.
`src/pydantic_studio/__init__.py`: `__version__ = "0.0.7"`. Add imports:

```python
from pydantic_studio.io import (
    load_config,
    load_json,
    load_toml,
    load_yaml,
    save_config,
    save_json,
    save_toml,
    save_yaml,
)
```

(Replace the existing `from pydantic_studio.io import load_yaml, save_yaml` line.)

Add to `__all__` (alphabetically):

```
"load_config", "load_json", "load_toml", "load_yaml",
"save_config", "save_json", "save_toml", "save_yaml",
```

- [ ] **Step 2: Update README**

Append to `README.md` (after Phase 6 section):

````markdown
## TOML + JSON I/O (v0.0.7)

```bash
$ uv run pydantic-studio fill mypkg.config:AppSettings --out config.toml
$ uv run pydantic-studio fill mypkg.config:AppSettings --out config.json
$ uv run pydantic-studio run mypkg.config:AppSettings config.toml
```

Format inferred from extension. Programmatic API:

```python
from pydantic_studio import load_config, save_config

tree = load_config("config.toml", AppSettings)
tree.set_value("port", 9090)
save_config(tree, "config.toml")  # writes TOML preserving comments
```

Or call format-specific helpers directly: `load_toml`/`save_toml`, `load_json`/`save_json`.

### Format support matrix

| Format | Read | Write | Comments preserved on edit |
|---|---|---|---|
| YAML  | ruamel.yaml | ruamel.yaml | ✓ (Phase 4) |
| TOML  | tomllib (stdlib) | tomlkit | description comments only (Phase 7); v0.0.8 polishes user-comment preservation |
| JSON  | stdlib json | model_dump_json(indent=2) | n/a (JSON has no comments) |
````

- [ ] **Step 3: Run + commit**

```bash
uv run pytest -q  # 402 passed
uv run ruff check
git add -A
git commit -m "docs: README + version bump for v0.0.7"
```

---

### Task 7: Merge ceremony

```bash
git tag v0.0.7-phase-7
git checkout master
git merge --no-ff feature/phase-7-toml-json-io -m "merge: Phase 7 — TOML + JSON I/O + format-dispatch CLI"
uv run pytest -q
git branch -d feature/phase-7-toml-json-io
```

Do not push.

---

**End of Plan 7.**
