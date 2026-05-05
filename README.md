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
