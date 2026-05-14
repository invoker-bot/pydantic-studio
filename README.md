# pydantic-studio

**Interactive editor for Pydantic models.** Generate and edit `config.yaml` /
`config.toml` / `config.json` against a strongly-typed schema, with three
frontends sharing a single form-state model: a Textual TUI, an HTMX-driven
local web app, and a CLI shorthand.

[![status](https://img.shields.io/badge/status-alpha-blue)](#status)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](#install)
[![tests](https://img.shields.io/badge/tests-416%20passing-brightgreen)](#development)

---

## Why?

Hand-editing config files is error-prone. Pydantic schemas already encode
the contract — types, constraints, defaults, descriptions. pydantic-studio
turns that schema into an editor, with format round-trip that preserves
your hand-written comments.

## Status

**v0.1.0 — Alpha.** All 9 implementation phases are merged on master.
Production code paths are exercised by 416 tests (unit + integration +
TUI/HTMX smoke). API is stable enough for early adopters; expect
v0.2 to add polish (Tailwind pipeline, theme toggle, status-bar UI)
without breaking the public API.

## Install

```bash
pip install pydantic-studio
# or
uv add pydantic-studio
```

For `EmailStr` support, install with the `email` extra:

```bash
pip install 'pydantic-studio[email]'
```

## Quick start

### Programmatic

```python
from pydantic import BaseModel, Field, HttpUrl, SecretStr
from pydantic_studio import build_form_tree, save_yaml


class AppSettings(BaseModel):
    name: str = Field(default="prod", description="Service identifier")
    port: int = Field(default=8080, ge=1, le=65535, description="Listening port")
    api_url: HttpUrl = Field(default=HttpUrl("https://api.example.com"))
    api_key: SecretStr = Field(default=SecretStr("change-me"))


tree = build_form_tree(AppSettings)
tree.set_value("port", 9090)
save_yaml(tree, "config.yaml")
```

```yaml
# Service identifier
name: prod
# Listening port
port: 9090
api_url: https://api.example.com
api_key: change-me
```

### CLI

```bash
# Stub a fresh config from defaults
pydantic-studio fill myapp.config:AppSettings --out config.yaml

# Validate without launching anything
pydantic-studio check myapp.config:AppSettings config.yaml

# Print the validated model
pydantic-studio run myapp.config:AppSettings config.yaml

# Open the Textual TUI
pydantic-studio edit myapp.config:AppSettings config.yaml

# Or the HTMX-driven browser UI
pydantic-studio edit --frontend web myapp.config:AppSettings config.yaml
```

Format is auto-detected from extension (`.yaml` / `.yml` / `.toml` / `.json`).

### Textual TUI

| Key | Action |
|---|---|
| `Ctrl+S` | Save (writes via `save_yaml`; refuses on validation failure) |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo |
| `Ctrl+Q` | Quit (confirms if dirty) |

### Browser UI

`--frontend web` boots a local FastAPI app on a random free port and
opens your browser. Edits POST to HTMX endpoints; the preview pane
updates live. Closing the tab triggers a 30-second heartbeat timeout
(configurable via `run_html_app(..., heartbeat_timeout_seconds=...)`)
and the server shuts down.

## Type coverage

| Family | Types |
|---|---|
| Primitives | `str`, `int`, `float`, `bool`, `Decimal` |
| Choices | `Enum`, `Literal[...]` |
| Containers | `list[T]`, `set[T]`, `tuple[T, ...]`, `tuple[T1, T2, ...]`, `dict[K, V]` |
| Unions | `T \| U`, `Optional[T]` |
| Temporal | `datetime`, `date`, `time`, `timedelta` |
| Network | `IPv4Address`, `IPv6Address`, `IPv4Network`, `IPv6Network`, `AnyUrl`/`HttpUrl`/`FileUrl`, `EmailStr` |
| Special | `pathlib.Path`, `uuid.UUID`, `SecretStr`, `SecretBytes`, `re.Pattern`, `bytes` |
| Constraints | Pydantic v2 `Annotated` constraints (`ge`/`le`/`min_length`/`pattern`/etc.) — auto-wired |

Add custom types via `register_builder(MyBuilder())`.

## File-format support

| Format | Read | Write | User-comment round-trip |
|---|---|---|---|
| YAML | `ruamel.yaml` | `ruamel.yaml` | ✓ |
| TOML | `tomllib` (stdlib) | `tomlkit` | description comments only |
| JSON | stdlib `json` | `model_dump_json(indent=2)` | n/a (JSON has no comments) |

```python
from pydantic_studio import load_config, save_config

tree = load_config("config.toml", AppSettings)   # picks parser by extension
tree.set_value("port", 9090)
save_config(tree, "config.toml")                 # picks writer by extension
```

Format-specific helpers — `load_yaml` / `save_yaml`, `load_toml` /
`save_toml`, `load_json` / `save_json`, `save_draft_yaml` (skips
validation for mid-edit drafts) — are also exported.

## Public API surface

```python
from pydantic_studio import (
    # Tree construction
    build_form_tree, FormTree, FormNode,
    # 24 node types
    StringNode, IntNode, FloatNode, BoolNode, DecimalNode,
    DatetimeNode, DateNode, TimeNode, TimedeltaNode,
    IpAddressNode, IpNetworkNode, UrlNode, EmailNode,
    PathNode, UuidNode, SecretNode, PatternNode, BytesNode,
    EnumNode, LiteralNode, SequenceNode, MappingNode, UnionNode, GroupNode,
    # I/O
    load_config, save_config,
    load_yaml, save_yaml, save_draft_yaml,
    load_toml, save_toml,
    load_json, save_json,
    # Drafts
    save_draft, load_draft, delete_draft, find_draft, draft_newer_than,
    # Renderers
    StudioApp, run_app,           # Textual TUI
    StudioServer, run_html_app,   # HTML/HTMX
    # Registry
    Registry, NodeBuilder, register_builder,
    default_registry, reset_default_registry,
    # Validation + exceptions
    ValidationResult,
    PydanticStudioError, NoBuilderError,
    CancelledByUser, ValidationFailedError,
)
```

## Drafts (auto-save + recovery)

```python
from pydantic_studio import find_draft, load_draft, save_draft, delete_draft

# Mid-session
save_draft(tree, ".pydantic-studio.draft.json")

# On the next launch
existing = find_draft(".")
if existing is not None:
    tree = load_draft(existing, MyConfig)
    # ... user resumes editing ...
    delete_draft(existing)  # on successful submit
```

`save_draft_yaml(tree, path)` is the YAML equivalent — it skips
`to_instance()` validation so partial trees can persist mid-edit.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Textual TUI │ HTML browser │ CLI │  ← renderers          │
│ (StudioApp) │ (StudioServer)│     │     (frontends)       │
└──────┬───────────┬────────────┬──┘                        │
       │           │            │                            │
       ▼           ▼            ▼                            │
┌──────────────────────────────────────────────────────────┐│
│  FormTree (canonical state)                               ││
│  • 24 node types, discriminated by `kind`                 ││
│  • path-addressed mutations (set_value / add_item / …)    ││
│  • snapshot ring for undo / redo                          ││
│  • validate-first contract                                ││
└──────────────────────┬───────────────────────────────────┘│
                       │                                    │
                       ▼                                    │
┌──────────────────────────────────────────────────────────┐│
│  I/O layer                                                ││
│  • load_config / save_config (extension dispatch)         ││
│  • YAML / TOML / JSON specific helpers                    ││
│  • Draft persistence                                      ││
└──────────────────────────────────────────────────────────┘│
                                                            │
   Type registry (NodeBuilder Protocol) — extend with       │
   `register_builder(MyBuilder())` for custom Pydantic      │
   types the default registry doesn't recognize.            │
```

The full architecture doc is at `docs/site/architecture.md`. Run
`uv run mkdocs serve` to read it locally.

## Development

```bash
git clone https://github.com/pydantic-studio/pydantic-studio
cd pydantic-studio
uv sync

# Tests
uv run pytest -q                          # 416 tests
uv run pytest tests/unit/test_yaml_io.py  # focused

# Lint
uv run ruff check
uv run pyright src/pydantic_studio       # production code only

# Docs
uv run mkdocs serve                       # 127.0.0.1:8000
uv run mkdocs build --strict              # also covered by test_docs_build.py
```

Project conventions are documented in [`CLAUDE.md`](CLAUDE.md) — the
guide for AI-assisted development sessions, but useful for any
contributor.

## Frontend development (Phase 2+)

The Textual TUI and CLI are pure Python — `uv sync && uv run python examples/02_server_config.py tui` is enough.

The web renderer is a React SPA built with Vite, source under `frontend/`. End users do NOT need Node — `pip install pydantic-studio` ships the pre-built bundle. To modify the SPA:

```bash
cd frontend
corepack enable && corepack prepare pnpm@9 --activate   # one-time
pnpm install
pnpm dev              # Vite dev server with HMR; proxies /api/* to FastAPI on :8000
# in another terminal:
uv run python examples/02_server_config.py web
# then open http://localhost:5173 (Vite's port; not the FastAPI port)

# To refresh the committed bundle:
pnpm build            # or frontend/scripts/build.sh
git add ../src/pydantic_studio/renderers/html/static/dist
```

The bundled output (`src/pydantic_studio/renderers/html/static/dist/`) is committed to the repo so CI and downstream users don't need a Node toolchain.

## License

MIT.
