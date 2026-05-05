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

## License

MIT
