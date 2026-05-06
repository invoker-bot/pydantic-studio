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
