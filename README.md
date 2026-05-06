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

## Textual TUI (v0.0.5)

Pydantic Studio now ships a Textual-based terminal UI:

```bash
$ uv run pydantic-studio edit mypkg.config:AppSettings config.yaml
```

The TUI shows three regions:

- **Sidebar** (left): tree of nested groups. Click a group to focus its fields in the editor.
- **Editor** (center): scrollable widgets for each field. TextInput for scalars, Checkbox for bools, Select for Enum/Literal, expandable rows for sequences and mappings, variant picker for unions.
- **Preview** (right): live YAML render — updates after every successful mutation.

### Key bindings

- `Ctrl+S` — save (writes via `save_yaml`; refuses if the tree fails validation)
- `Ctrl+Z` / `Ctrl+Y` — undo / redo
- `Ctrl+Q` — quit (no prompt yet — Plan 6 polish)

### What's not in v0.0.5

- HTML renderer (Plan 6)
- TOML / JSON I/O (Plan 7)
- Light theme + custom theme.css (Plan 8 polish)
- `save_draft_yaml` for partial-tree saves (Plan 6)
- Status-bar widget for error display (currently surfaces via `notify()` toasts)
- Per-Sequence drag-to-reorder (Plan 6)

### Programmatic usage

```python
from pydantic_studio import build_form_tree, StudioApp

tree = build_form_tree(MyConfig)
app = StudioApp(tree=tree, save_path="config.yaml")
app.run()  # blocks until the user quits
```

## HTML Renderer (v0.0.6)

```bash
$ uv run pydantic-studio edit --frontend web mypkg.config:AppSettings config.yaml
```

A FastAPI app boots on `127.0.0.1:<port>`, opens your browser, and shows the same three-region layout as the TUI. Edits POST to HTMX endpoints; the server validates and returns updated preview HTML.

### Routes

| Route | Method | Effect |
|---|---|---|
| `/` | GET | Index page |
| `/field/<path>` | POST | Update a leaf field's value |
| `/seq/<path>/add` | POST | Append item to a SequenceNode |
| `/seq/<path>/remove?index=<i>` | POST | Remove item at index |
| `/map/<path>/add` | POST | Add a placeholder entry to a MappingNode |
| `/map/<path>/remove?index=<i>` | POST | Remove entry at index |
| `/union/<path>/select` | POST | Pick a UnionNode variant |
| `/submit` | POST | `to_instance()` → `save_yaml` → exit |
| `/cancel` | POST | Mark cancelled |
| `/heartbeat` | GET | Keepalive (tab-close detection — Plan 8 polish) |

### What's not in v0.0.6

- Full Tailwind CSS pipeline (Plan 8) — current CSS is minimal hand-written
- Alpine.js sprinkles (Plan 8)
- `/heartbeat` 30s timeout enforcement — currently only tracks last-seen; auto-cancel lands in Plan 8
- Mobile / responsive layout (Plan 8)
- TOML / JSON output (Plan 7)

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

## License

MIT
