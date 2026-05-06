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
