# pydantic-studio — Phase 9: Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Ship the final v0.1 docs site with mkdocs-material + mkdocstrings: tutorial, architecture overview, API reference, example schemas. Bump version to 0.1.0 to mark the v0.1 milestone.

**Architecture:** A `docs/site/` tree (mkdocs source) with `mkdocs.yml` at repo root configuring mkdocs-material. mkdocstrings generates API reference from existing docstrings. Tutorial walks through building a config editor end-to-end. Example schemas live under `docs/site/examples/` with corresponding markdown commentary.

**Tech Stack:** mkdocs-material, mkdocstrings[python], pymdown-extensions (already transitively pulled by mkdocs-material).

**Out-of-scope (post-v0.1):** Demo gif/screencast, full publishing to GitHub Pages, mkdocs-gen-files for fully-automated nav, multi-language docs.

---

## File Structure

**New:**
- `mkdocs.yml` — site config
- `docs/site/index.md` — landing page
- `docs/site/tutorial.md` — quickstart tutorial
- `docs/site/architecture.md` — design overview
- `docs/site/api.md` — mkdocstrings-rendered API
- `docs/site/cli.md` — CLI command reference
- `docs/site/examples/index.md` — examples landing
- `docs/site/examples/server-config.md` — first example
- `docs/site/examples/multi-format.md` — TOML/JSON/YAML
- `tests/unit/test_docs_build.py` — verifies mkdocs builds without errors

**Modified:**
- `pyproject.toml` — add `mkdocs-material`, `mkdocstrings[python]` to dev deps; bump version to 0.1.0
- `src/pydantic_studio/__init__.py` — `__version__ = "0.1.0"`
- `README.md` — final v0.1 release notes + link to docs site
- `.gitignore` — `site/` (mkdocs build output)

---

### Task 1: Branch + mkdocs deps

- [ ] **Step 1: Branch**

```bash
git checkout master
git checkout -b feature/phase-9-documentation
uv run pytest -q  # 415 baseline
```

- [ ] **Step 2: Add mkdocs deps**

In `pyproject.toml`, add to the dev group:

```toml
[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "pytest-cov",
  "email-validator>=2",
  "mkdocs-material>=9.5",
  "mkdocstrings[python]>=0.27",
]
```

- [ ] **Step 3: Sync + smoke**

```bash
uv sync
uv run mkdocs --version  # confirms binary works
```

- [ ] **Step 4: Add site/ to .gitignore**

In `.gitignore`, append:

```
# mkdocs build output
site/
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "build: add mkdocs-material + mkdocstrings dev deps for Phase 9 docs site"
```

---

### Task 2: mkdocs scaffold + nav

**Files:**
- Create: `mkdocs.yml`
- Create: `docs/site/index.md`

- [ ] **Step 1: Create mkdocs.yml**

```yaml
site_name: pydantic-studio
site_description: Interactive editor for Pydantic models
site_url: https://pydantic-studio.example  # placeholder; update for real publish
repo_url: https://github.com/pydantic-studio/pydantic-studio
docs_dir: docs/site

theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.sections
    - navigation.tabs
    - navigation.top
    - content.code.copy

nav:
  - Home: index.md
  - Tutorial: tutorial.md
  - Architecture: architecture.md
  - CLI: cli.md
  - Examples:
      - examples/index.md
      - Server config: examples/server-config.md
      - Multi-format I/O: examples/multi-format.md
  - API Reference: api.md

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_source: false
            show_root_heading: true
            show_root_full_path: false
            members_order: source

markdown_extensions:
  - admonition
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.details
  - pymdownx.snippets
  - tables
  - toc:
      permalink: true
```

- [ ] **Step 2: Create index.md**

Create `docs/site/index.md`:

```markdown
# pydantic-studio

**Interactive editor for Pydantic models.** Generate and edit `config.yaml` /
`config.toml` / `config.json` against a strongly-typed schema, with three
frontends sharing a single form-state model:

- A **Textual TUI** — `pydantic-studio edit mypkg:Config config.yaml`
- An **HTML browser app** — `pydantic-studio edit --frontend web mypkg:Config config.yaml`
- A **CLI shorthand** — `pydantic-studio fill | run | check`

## Why?

Hand-editing config files is error-prone. Pydantic schemas already encode
the contract — types, constraints, defaults, descriptions. pydantic-studio
turns that schema into an editor.

## Install

```bash
pip install pydantic-studio
# or
uv add pydantic-studio
```

## Quick start

```python
from pydantic import BaseModel, Field
from pydantic_studio import build_form_tree, save_yaml


class AppSettings(BaseModel):
    name: str = Field(default="prod", description="Service identifier")
    port: int = Field(default=8080, ge=1, le=65535, description="Listening port")


tree = build_form_tree(AppSettings)
tree.set_value("port", 9090)
save_yaml(tree, "config.yaml")
```

```yaml
# Service identifier
name: prod
# Listening port
port: 9090
```

Continue to the [tutorial](tutorial.md) for the full walkthrough.
```

- [ ] **Step 3: Smoke build**

```bash
uv run mkdocs build --strict 2>&1 | tail -10
```

The strict flag fails on broken links — for now, it's expected to fail because tutorial.md / architecture.md / etc. don't exist yet. That's fine — Tasks 3-7 fix this.

For Task 2's commit, run a non-strict build to verify mkdocs.yml parses:

```bash
uv run mkdocs build 2>&1 | tail -5
```

Expected: warnings about missing files (tutorial.md etc.) but no parse errors.

- [ ] **Step 4: Commit**

```bash
git add mkdocs.yml docs/site/index.md
git commit -m "docs: mkdocs scaffold — site config + landing page"
```

---

### Task 3: Tutorial page

**Files:**
- Create: `docs/site/tutorial.md`

- [ ] **Step 1: Create tutorial.md**

```markdown
# Tutorial

A complete walkthrough: define a schema, edit it, save it, reload it.

## 1. Define the schema

Any Pydantic v2 BaseModel works. Use `Field(description=...)` to attach
descriptions that surface as comments in YAML output and help text in the
UI.

```python
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field, HttpUrl, SecretStr


class AppSettings(BaseModel):
    name: str = Field(default="prod", description="Service identifier")
    port: int = Field(default=8080, ge=1, le=65535, description="Listening port")
    api_url: HttpUrl = Field(
        default=HttpUrl("https://api.example.com"),
        description="Upstream API endpoint",
    )
    api_key: SecretStr = Field(
        default=SecretStr("change-me"),
        description="API key (kept secret in dumps)",
    )
    home: Path = Field(
        default=Path("/srv/app"),
        description="Working directory",
    )
    started_at: datetime = Field(
        default=datetime(2026, 5, 6, 12, 0),
        description="Launch timestamp",
    )
```

## 2. Build a form tree

```python
from pydantic_studio import build_form_tree

tree = build_form_tree(AppSettings)
```

The tree is a Pydantic-validated hierarchy mirroring `AppSettings`'s
fields. Each leaf is a typed Node (`StringNode`, `IntNode`, `UrlNode`,
`SecretNode`, etc.).

## 3. Mutate via path-addressed API

```python
result = tree.set_value("name", "staging")
assert result.ok

# Cross-field validation runs at submit time, not on every set_value.
tree.set_value("port", 9090)
```

## 4. Save as YAML

```python
from pydantic_studio import save_yaml

save_yaml(tree, "config.yaml")
```

```yaml
# Service identifier
name: staging
# Listening port
port: 9090
# Upstream API endpoint
api_url: https://api.example.com
# API key (kept secret in dumps)
api_key: change-me
# Working directory
home: /srv/app
# Launch timestamp
started_at: '2026-05-06T12:00:00'
```

## 5. Reload + edit + save

```python
from pydantic_studio import load_yaml

tree = load_yaml("config.yaml", AppSettings)
tree.set_value("port", 9091)
save_yaml(tree, "config.yaml")
# User comments preserved on round-trip; only changed values are updated.
```

## 6. Format-agnostic dispatch

```python
from pydantic_studio import save_config, load_config

save_config(tree, "config.toml")  # extension picks TOML
save_config(tree, "config.json")  # → JSON
tree2 = load_config("config.toml", AppSettings)
```

## 7. Materialize to instance

```python
instance = tree.to_instance()  # validates + returns AppSettings
print(instance.api_url)        # → HttpUrl('https://api.example.com/')
```

If validation fails (required fields unset, constraints violated),
`tree.to_instance()` raises `ValidationFailedError` listing every
problem.

## 8. Launch the TUI

```bash
$ uv run pydantic-studio edit mypkg.config:AppSettings config.yaml
```

`Ctrl+S` saves, `Ctrl+Z`/`Ctrl+Y` undo/redo, `Ctrl+Q` quits (with
confirmation if you have unsaved changes).

## 9. Launch the browser UI

```bash
$ uv run pydantic-studio edit --frontend web mypkg.config:AppSettings config.yaml
```

A FastAPI app opens on `127.0.0.1:<random_free_port>`, your default
browser navigates to it, and the page renders the same three-region
layout. Edits POST to HTMX endpoints; the preview pane updates live.

## Next steps

- [Architecture](architecture.md) — how the form tree, renderers, and I/O fit together.
- [Examples](examples/index.md) — bigger schemas, draft recovery, custom NodeBuilders.
- [API Reference](api.md) — every public symbol.
- [CLI](cli.md) — every subcommand and flag.
```

- [ ] **Step 2: Commit**

```bash
git add docs/site/tutorial.md
git commit -m "docs: tutorial page — schema → edit → save round-trip"
```

---

### Task 4: Architecture page

**Files:**
- Create: `docs/site/architecture.md`

- [ ] **Step 1: Create architecture.md**

```markdown
# Architecture

pydantic-studio has three layers, in dependency order from the bottom up:

## Form tree — the canonical state

The `FormTree` is a Pydantic v2 hierarchy mirroring the user's schema.
Every field is a `FormNode` subclass (24 of them total): `StringNode`,
`IntNode`, `EnumNode`, `SequenceNode`, `MappingNode`, `UnionNode`,
`GroupNode`, etc. The discriminator is the `kind` field; nested nodes
form a tree rooted at a `GroupNode`.

**The tree is the single source of truth.** Renderers translate user
intent into mutations (`tree.set_value("path.to.field", value)`) and
translate tree state into pixels — they own no canonical state.

Mutations follow a **validate-first contract**: `set_value()` runs the
node's `validate_value()` first; on failure, no mutation occurs and the
returned `ValidationResult.fail(errors)` reports the issue. On success,
a snapshot is pushed to the undo ring before the mutation.

## I/O — format-aware load/save

YAML round-trip (`load_yaml` / `save_yaml`) uses `ruamel.yaml.YAML(typ='rt')`
to preserve user-edited comments. New keys get description comments from
`Field(description=...)`. Smart writer rules in spec §10.1 — schema-order
field emission, drop-deleted-fields, etc.

TOML round-trip uses stdlib `tomllib` (read) + `tomlkit` (write). JSON
uses stdlib `json` + `model_dump_json(indent=2)`. The
`load_config`/`save_config` dispatchers pick the right format based on
file extension.

## Renderers — frontends

Three first-class renderers share the same FormTree mutation API:

- **Textual TUI** (`pydantic_studio.renderers.textual_`) — `StudioApp` +
  `EditorScreen` + per-node-kind widgets. Tested via `App.run_test()`
  and `Pilot`.
- **HTML browser** (`pydantic_studio.renderers.html`) — FastAPI server
  + Jinja2 templates + HTMX-driven swaps. Heartbeat polling detects
  abandoned tabs.
- **CLI shorthand** (`pydantic_studio.cli`) — `fill`, `run`, `check`,
  `edit`, `show`, `version`. Uses typer.

Adding a 4th renderer (e.g., a Tk desktop app) means implementing one
new module under `renderers/`. The tree stays untouched.

## Cross-frontend identity

A **path** identifies any node in the tree (e.g.,
`database.replicas[2].host`). Both renderers send the same path strings;
the tree's `set_value` and friends resolve them. A draft saved from web
can be resumed in TUI, and vice versa, because the persisted format is
the FormTree's own JSON dump.

## Type registry

Each Pydantic type is built into the tree by a `NodeBuilder`. The
default registry knows 26 builders (one per type family — primitive,
choice, sequence, mapping, union, datetime, network, special). Users
can extend via `register_builder(MyCustomBuilder())` to support types
the default registry doesn't recognize.

## Snapshots + draft persistence

Every mutation pushes a snapshot (`tree.model_dump_json()` bytes) to a
bounded ring buffer. `tree.undo()` / `tree.redo()` restore from
snapshots.

The `tree.draft` module persists the full tree to
`<cwd>/.pydantic-studio.draft.json` for crash recovery. On startup, CLI
commands check for a newer draft via `find_draft()` +
`draft_newer_than()` and prompt to resume.

## Validation

Field-level validation runs on every mutation via
`FormNode.validate_value()`. Cross-field validation (Pydantic
`@model_validator`) runs only at submit time via `tree.to_instance()`,
so users can stage incomplete state without errors.
```

- [ ] **Step 2: Commit**

```bash
git add docs/site/architecture.md
git commit -m "docs: architecture page — three-layer overview"
```

---

### Task 5: API reference + CLI reference

**Files:**
- Create: `docs/site/api.md`
- Create: `docs/site/cli.md`

- [ ] **Step 1: Create api.md (mkdocstrings auto-render)**

```markdown
# API Reference

## Core

::: pydantic_studio.build_form_tree

::: pydantic_studio.FormTree

::: pydantic_studio.FormNode

## I/O

::: pydantic_studio.load_config
::: pydantic_studio.save_config
::: pydantic_studio.load_yaml
::: pydantic_studio.save_yaml
::: pydantic_studio.load_toml
::: pydantic_studio.save_toml
::: pydantic_studio.load_json
::: pydantic_studio.save_json
::: pydantic_studio.save_draft_yaml

## Drafts

::: pydantic_studio.save_draft
::: pydantic_studio.load_draft
::: pydantic_studio.delete_draft
::: pydantic_studio.find_draft
::: pydantic_studio.draft_newer_than

## Renderers

::: pydantic_studio.StudioApp
::: pydantic_studio.run_app
::: pydantic_studio.StudioServer
::: pydantic_studio.run_html_app

## Registry

::: pydantic_studio.Registry
::: pydantic_studio.NodeBuilder
::: pydantic_studio.register_builder
::: pydantic_studio.default_registry
::: pydantic_studio.reset_default_registry

## Exceptions

::: pydantic_studio.PydanticStudioError
::: pydantic_studio.NoBuilderError
::: pydantic_studio.CancelledByUser
::: pydantic_studio.ValidationFailedError

## Validation results

::: pydantic_studio.ValidationResult
```

- [ ] **Step 2: Create cli.md**

```markdown
# CLI Reference

```bash
pydantic-studio --help
```

## Commands

### `show <module:Class>`

Inspect a schema's form-tree shape.

```bash
$ pydantic-studio show mypkg.config:AppSettings
AppSettings
├── name (str)
├── port (int)
└── api_url (url)
```

### `fill <module:Class> [--out FILE]`

Emit a config stub populated with defaults. Writes YAML to stdout if
`--out` is omitted; format inferred from extension otherwise.

```bash
$ pydantic-studio fill mypkg.config:AppSettings --out config.yaml
$ pydantic-studio fill mypkg.config:AppSettings --out config.toml
$ pydantic-studio fill mypkg.config:AppSettings --out config.json
```

### `run <module:Class> <file>`

Load a file, validate, print the model dump.

```bash
$ pydantic-studio run mypkg.config:AppSettings config.yaml
AppSettings(name='prod', port=8080, ...)
```

Exits non-zero if validation fails.

### `check <module:Class> <file>`

Same as `run` but silent on success — for CI integration.

```bash
$ pydantic-studio check mypkg.config:AppSettings config.yaml
config.yaml: OK
```

### `edit <module:Class> [<file>] [--frontend tui|web]`

Launch an interactive editor. `tui` (default) launches the Textual UI;
`web` boots the FastAPI HTML renderer in your default browser.

```bash
$ pydantic-studio edit mypkg.config:AppSettings config.yaml
$ pydantic-studio edit --frontend web mypkg.config:AppSettings config.yaml
```

If `<file>` exists, it's loaded; otherwise a fresh tree is built from
the schema's defaults. On save, the tree is materialized via
`to_instance()` and written via `save_config` (extension picks format).

### `version`

```bash
$ pydantic-studio version
pydantic-studio 0.1.0
```

## Exit codes

- `0` — success
- `1` — validation failure (`run` / `check` / `edit`)
- `2` — argument or schema-resolution error
```

- [ ] **Step 3: Verify build**

```bash
uv run mkdocs build 2>&1 | tail -10
```

Expected: warnings about missing examples/* but no errors.

- [ ] **Step 4: Commit**

```bash
git add docs/site/api.md docs/site/cli.md
git commit -m "docs: API + CLI reference pages (mkdocstrings auto-rendered)"
```

---

### Task 6: Examples pages

**Files:**
- Create: `docs/site/examples/index.md`
- Create: `docs/site/examples/server-config.md`
- Create: `docs/site/examples/multi-format.md`

- [ ] **Step 1: Create examples/index.md**

```markdown
# Examples

- [Server config](server-config.md) — a typical web service settings schema with nested groups, lists, and secrets.
- [Multi-format I/O](multi-format.md) — round-trip the same config through YAML, TOML, and JSON.
```

- [ ] **Step 2: Create examples/server-config.md**

```markdown
# Example: Server config

A schema with nested BaseModels, a list of replicas, an enum, and a
secret.

```python
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, SecretStr


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class Replica(BaseModel):
    host: str = Field(description="Replica hostname or IP")
    port: int = Field(default=5432, description="Replica port")


class Database(BaseModel):
    primary: Replica = Field(description="Primary database replica")
    read_replicas: list[Replica] = Field(
        default_factory=list,
        description="Read-only replicas for query offload",
    )
    password: SecretStr = Field(description="Connection password")


class Logging(BaseModel):
    level: LogLevel = Field(default=LogLevel.INFO, description="Log verbosity")
    format: Literal["json", "text"] = Field(default="text", description="Log format")


class ServerConfig(BaseModel):
    name: str = Field(description="Service identifier")
    api_url: HttpUrl = Field(description="Upstream API endpoint")
    database: Database
    logging: Logging = Field(default_factory=Logging)
```

## Generate a stub

```bash
$ pydantic-studio fill mypkg.server:ServerConfig --out server.yaml
```

```yaml
# Service identifier
name: ?
# Upstream API endpoint
api_url: ?
database:
  primary:
    # Replica hostname or IP
    host: ?
    # Replica port
    port: 5432
  # Read-only replicas for query offload
  read_replicas: []
  # Connection password
  password: ?
logging:
  # Log verbosity
  level: info
  # Log format
  format: text
```

(Required fields without defaults appear as `?`; you fill them in.)

## Edit interactively

```bash
$ pydantic-studio edit --frontend web mypkg.server:ServerConfig server.yaml
```

The sidebar shows the GroupNode hierarchy:

- ServerConfig
  - database
  - logging

Click a group to focus its fields. Add replicas with `+ Add` on the
`read_replicas` row.

## Validate

```bash
$ pydantic-studio check mypkg.server:ServerConfig server.yaml
server.yaml: OK
```
```

- [ ] **Step 3: Create examples/multi-format.md**

```markdown
# Example: Multi-format I/O

The same FormTree round-trips cleanly through YAML, TOML, and JSON.

```python
from pydantic import BaseModel, Field
from pydantic_studio import build_form_tree, save_config, load_config


class Settings(BaseModel):
    name: str = Field(default="prod", description="Service identifier")
    port: int = Field(default=8080, description="Listening port")


tree = build_form_tree(Settings)
tree.set_value("port", 9090)

save_config(tree, "config.yaml")
save_config(tree, "config.toml")
save_config(tree, "config.json")
```

The dispatcher picks the format from the extension. Each file:

```yaml
# config.yaml — comments preserved on edit
# Service identifier
name: prod
# Listening port
port: 9090
```

```toml
# config.toml — comments preserved
# Service identifier
name = "prod"
# Listening port
port = 9090
```

```json
{
  "name": "prod",
  "port": 9090
}
```

(JSON has no comments — accepted limitation.)

## Round-trip

```python
yaml_tree = load_config("config.yaml", Settings)
toml_tree = load_config("config.toml", Settings)
json_tree = load_config("config.json", Settings)

yaml_tree.to_instance() == toml_tree.to_instance() == json_tree.to_instance()
```

## Format-specific helpers

If you want to bypass dispatch:

```python
from pydantic_studio import (
    load_yaml, save_yaml,
    load_toml, save_toml,
    load_json, save_json,
)
```
```

- [ ] **Step 4: Verify strict build**

```bash
uv run mkdocs build --strict 2>&1 | tail -10
```

Expected: builds cleanly. If broken links, fix them.

- [ ] **Step 5: Commit**

```bash
git add docs/site/examples
git commit -m "docs: example pages — server config + multi-format I/O"
```

---

### Task 7: Test that mkdocs builds

**Why:** A test that runs `mkdocs build --strict` keeps docs from rotting unnoticed.

**Files:**
- Create: `tests/unit/test_docs_build.py`

- [ ] **Step 1: Test**

Create `tests/unit/test_docs_build.py`:

```python
"""Smoke test: mkdocs builds without errors or broken links."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_mkdocs_strict_build(tmp_path: Path) -> None:
    """mkdocs build --strict succeeds (catches broken links + missing pages)."""
    if shutil.which("mkdocs") is None:
        pytest.skip("mkdocs not on PATH (dev dep not synced)")

    site_dir = tmp_path / "site"
    result = subprocess.run(  # noqa: S603
        ["mkdocs", "build", "--strict", "-f", str(REPO_ROOT / "mkdocs.yml"),
         "-d", str(site_dir)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        pytest.fail(
            f"mkdocs build --strict failed:\nSTDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )
    # The output should at least include the index.
    assert (site_dir / "index.html").exists()
```

The `# noqa: S603` suppresses ruff's "subprocess-without-shell-equals-true" warning if S is enabled (it isn't currently, but defensive).

- [ ] **Step 2: Run + commit**

```bash
uv run pytest tests/unit/test_docs_build.py -v
uv run pytest -q
git add tests/unit/test_docs_build.py
git commit -m "test(docs): smoke test that mkdocs builds with --strict"
```

If the test fails because mkdocs isn't installed, that's expected on machines without dev deps — the `pytest.skip` clause handles it. On the dev branch we should have mkdocs available.

If `mkdocs build --strict` fails on broken links, audit the markdown for orphan references. The strict mode is exactly to catch them.

---

### Task 8: README + version bump v0.1.0

- [ ] **Step 1: Bump versions**

`pyproject.toml`: `version = "0.1.0"`.
`src/pydantic_studio/__init__.py`: `__version__ = "0.1.0"`.

Also update the classifier:

```toml
classifiers = [
  "Development Status :: 3 - Alpha",
  ...
]
```

(Was Pre-Alpha; now Alpha for v0.1.)

- [ ] **Step 2: Update README to point at the docs site**

In `README.md`, add a prominent "Docs" link near the top. Replace the existing `## Status` section:

```markdown
## Status

**v0.1.0 — Alpha.** All eight implementation phases complete:

| Phase | Feature | Tag |
|---|---|---|
| 1 | Form Tree | v0.0.1-phase-1 |
| 2 | Type coverage 1 | v0.0.2-phase-2 |
| 3 | Type coverage 2 + show CLI | v0.0.3-phase-3 |
| 4 | YAML I/O + fill/run/check CLI | v0.0.4-phase-4 |
| 5 | Textual TUI | v0.0.5-phase-5 |
| 6 | HTML browser renderer | v0.0.6-phase-6 |
| 7 | TOML + JSON I/O | v0.0.7-phase-7 |
| 8 | Polish (drafts, heartbeat, quit prompt) | v0.0.8-phase-8 |
| 9 | Documentation | v0.1.0 |

📖 **Docs:** Run `uv run mkdocs serve` to read the full tutorial /
architecture / API reference / examples locally on `127.0.0.1:8000`.
```

- [ ] **Step 3: Run final checks**

```bash
uv run pytest -q
uv run ruff check
uv run mkdocs build --strict 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: README + version bump for v0.1.0 (final v0.1 alpha release)"
```

---

### Task 9: Merge ceremony

```bash
git tag v0.1.0-phase-9
git tag v0.1.0  # marks the first proper alpha release
git checkout master
git merge --no-ff feature/phase-9-documentation -m "merge: Phase 9 — Documentation site (v0.1.0 alpha)"
uv run pytest -q
git branch -d feature/phase-9-documentation
git tag --list 'v0.*'
```

Do not push.

---

**End of Plan 9. End of v0.1 implementation.**
