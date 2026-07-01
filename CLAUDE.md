# CLAUDE.md — pydantic-studio conventions

This file is the AI-assisted development guide for pydantic-studio. It
captures decisions, patterns, and gotchas accumulated across the 9
implementation phases, so subsequent sessions can be productive
immediately.

## Project at a glance

- **What**: Interactive editor for Pydantic models. Generate and edit
  YAML / TOML / JSON config files against a strongly-typed schema.
- **Status**: v0.4.0 alpha — all 9 implementation phases, the
  task-oriented overhaul, TUI form mode, the React-backed web app, and
  root model variants are merged on master. Current local gate: 1285
  tests: 1234 default tests plus 51 explicit Playwright browser e2e tests, ruff
  clean, pyright clean for production code, `mkdocs build --strict`
  clean, frontend bundle build clean, `uv build` clean, `twine check`
  clean, and wheel/sdist install smoke clean. CI runs the default suite
  on Python 3.11-3.14; browser/package gates run on Python 3.13 and
  include wheel and sdist install smoke gates. Tag-triggered PyPI
  publishing uses GitHub OIDC Trusted Publishing with the `pypi`
  environment, not a repository API-token secret. The same built
  distributions are also published to piesource through an independent
  publish job, then a final result job reports any registry failure.
- **Three frontends**: Textual TUI, FastAPI + bundled React browser app,
  and CLI/console (`fill`/`run`/`check`/`edit`/`show`/`version`).
- **Three formats**: YAML (full round-trip), TOML, JSON.
- **The spec lives at** `docs/superpowers/specs/2026-05-05-pydantic-studio-design.md`.
- **Phase-by-phase plans live at** `docs/superpowers/plans/`.

## Architectural commitment

**The FormTree is the single source of truth.** Renderers translate
user intent into mutations and translate tree state into pixels. They
own no canonical state. Adding a 4th frontend = implementing one new
module under `renderers/`. The tree code does not change.

```
src/pydantic_studio/
├── __init__.py              # Public API surface (~60 exports)
├── cli.py                   # typer commands
├── exceptions.py            # PydanticStudioError + subclasses
├── tree/
│   ├── nodes.py             # 24 node types + FormTree (discriminated union)
│   ├── builder.py           # build_form_tree(schema, existing) + Registry
│   ├── validation.py        # ValidationResult
│   ├── snapshots.py         # snapshot ring + atomic draft_save/draft_load
│   ├── paths.py             # JSONPath-style addressing
│   └── draft.py             # save_draft / load_draft / find_draft / etc.
├── types/
│   ├── registry.py          # NodeBuilder Protocol + Registry class
│   ├── primitives.py        # Str/Int/Float/Bool/Decimal builders
│   ├── anyfield.py          # Any builder
│   ├── temporal.py          # date/datetime/time/timedelta builders
│   ├── network.py           # IP/URL/Email builders
│   ├── special.py           # Path/UUID/Secret/Pattern/Bytes builders
│   ├── choices.py           # Enum/Literal builders
│   ├── sequences.py         # List/Set/Tuple builders
│   ├── mapping.py           # Dict builder
│   ├── unions.py            # Union builder (with model_validate fallback)
│   ├── models.py            # GroupBuilder for nested BaseModel
│   ├── core_schema_fallback.py # fallback builder for supported core schemas
│   ├── annotated.py         # Annotated[...] traversal helpers
│   ├── metadata.py          # constraint extraction (ge, le, etc.)
│   └── utils.py             # field_default helper
├── io/
│   ├── dispatch.py          # load_config / save_config (by extension)
│   ├── yaml.py              # ruamel.yaml round-trip
│   ├── yaml_draft.py        # save_draft_yaml (skips validation)
│   ├── toml.py              # tomllib + tomlkit
│   └── json_.py             # stdlib json
└── renderers/
    ├── textual_/            # Textual TUI
    │   ├── app.py           # StudioApp
    │   ├── studio_screen.py # embeddable StudioScreen
    │   ├── screens.py       # support/legacy screens
    │   └── widgets/         # FieldList + per-kind cells
    └── html/                # FastAPI + React SPA
        ├── server.py        # StudioServer + run_html_app
        ├── routes.py        # SPA shell + /api/* JSON routes
        ├── serialize.py     # FormTree <-> JSON contract for the SPA
        ├── render.py        # legacy YAML preview helpers
        └── static/dist/     # committed Vite production bundle
```

The React/Vite source lives under `frontend/src/`. The committed
production bundle lives under
`src/pydantic_studio/renderers/html/static/dist/` and must be rebuilt
with `cd frontend && pnpm build` whenever SPA source changes.

## Core invariants — DO NOT BREAK

### 1. Validate-first contract

Every mutation routes through methods that **validate before mutating**.
On failure, no mutation occurs. On success, a snapshot is pushed to the
undo ring **before** the value is written.

```python
result = tree.set_value("path.to.field", value)
if not result.ok:
    # tree state UNCHANGED; result.errors lists what went wrong.
    pass
```

This applies to:
- `tree.set_value(path, value)`
- `tree.add_item(path, value)` / `tree.remove_item(path, index)`
- `tree.insert_item(path, index, value)` / `tree.move_item(path, from, to)`
- `tree.add_entry(path, key, value)` / `tree.remove_entry(path, index)`
- `tree.rename_key(path, index, new_key)`
- `tree.select_variant(path, variant_index, seed)`

If you add a new mutation, follow the same pattern: resolve+build first
(can fail), then `_push_snapshot`, then mutate. Never push a snapshot
that wraps a fallible operation downstream — earlier code stamped on
this and Phase 3 housekeeping had to fix it.

### 2. NodeBuilder Protocol

Every Pydantic type maps to one `NodeBuilder` (`matches(type) -> bool`,
`build(type, field_info, existing) -> FormNode`). Builders register in
the default registry; custom types extend via `register_builder(...)`.
**Don't** dispatch on type via if/elif chains in user code — go through
the registry.

### 3. Snapshot serialization round-trip

Every FormNode subclass has to round-trip cleanly through
`model_dump_json` → `model_validate_json`. For nodes whose `value` field
is `Any` (Enum, Union, etc.) this requires `field_serializer` +
`model_validator(mode="after")` pairs that look up the original Python
class via `sys.modules`. See `EnumNode` for the canonical pattern.

If you add a node type with a non-trivial value field, add a snapshot
round-trip test (`raw = node.model_dump_json()` →
`restored = NodeType.model_validate_json(raw)` → `assert restored.value == node.value`).

### 4. Atomic file writes

Every writer (`save_yaml`, `save_toml`, `save_json`, `save_draft_yaml`,
`save_draft`, `tree.snapshots.draft_save`) uses the same pattern:

```python
fd, tmp = tempfile.mkstemp(prefix=".tmp-...", dir=str(path.parent))
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp, path)
except Exception:
    Path(tmp).unlink(missing_ok=True)
    raise
```

`os.replace` is atomic on every platform we target when source + dest
are on the same filesystem (guaranteed by `dir=path.parent`). Don't
hand-roll a different scheme.

### 5a. Parse-on-load symmetry

Loading must be symmetric with saving. ``model_dump`` applies field
serializers, so the tree has to hold *post-validator* (runtime) values:
``GroupBuilder`` runs existing values of fields whose ``Annotated``
metadata carries a transforming validator (``PlainValidator`` /
``BeforeValidator`` / ``WrapValidator``) through
``TypeAdapter(...).validate_python`` before node construction.
``ValidationError`` falls back to the raw value (file-repair UX); any
other exception propagates. Breaking this re-introduces the
double-encryption bug (HFT field report, 2026-06-11): every load→save
cycle re-applied an encrypt serializer to an already-encrypted value.
Corollary: transforming validators are expected to be idempotent on
runtime instances (they already receive instances for TUI-typed
values).

### 5b. Session outcome protocol

``run_app`` returns ``EditOutcome("submitted" | "cancelled")``; only
``submitted`` means the user committed AND the tree validated. Callers
persist on ``submitted`` and abort otherwise. The TUI never exits with
unsaved dirty state without explicit user choice (ConfirmExitScreen).
Don't add exit paths that bypass ``StudioApp._finish``.

### 5. `save_yaml` requires a valid tree

`save_yaml(tree, path)` calls `tree.to_instance()` first, which raises
`ValidationFailedError` if required fields are unset. **This is the
contract** — partial trees can't go through `save_yaml`. For mid-edit
saves, use `save_draft_yaml(tree, path)` which skips validation and
emits whatever `to_python()` returns.

This bites people writing renderer code who expect `save_yaml` to
always work. The TUI's Ctrl+S handler uses `notify("Save failed: …")`
to surface the validation error to the user.

## Conventions

### Python style

- **Python 3.11+**, Pydantic v2.7+
- `from __future__ import annotations` at the top of every module —
  required for the codebase's TYPE_CHECKING patterns
- Type annotations everywhere (this is `Typing :: Typed`)
- ruff rules: `["E", "F", "I", "B", "UP", "PT", "RUF", "TC", "SIM"]`,
  line length 100
- `tests/*` has the `D` rule disabled (no docstring requirement on tests)
- pyright in basic mode; production code stays clean. The Textual
  renderer is excluded via `[tool.pyright] exclude` because Textual's
  typing surface is noisy

### TYPE_CHECKING discipline

Anything used only as an annotation goes under `if TYPE_CHECKING:`.
Anything used at runtime (registry resolution, isinstance checks,
exception classes) stays at module top.

**Exception**: FastAPI route handlers' `Request` parameter must be
imported at runtime — FastAPI resolves the annotation at runtime to
detect Starlette types. Mark with `# noqa: TC002` if ruff flags it.

### `field_default` helper

All builders pull defaults via `pydantic_studio.types.utils.field_default(field_info)`
which normalizes `PydanticUndefined → None`. Don't roll the
`field_info.get_default(call_default_factory=True)` + sentinel-check
inline — that pattern was extracted to `utils.py` in Phase 4
housekeeping.

### Inline imports

Late imports are used liberally inside method bodies to:
- Break circular dependencies (renderer → tree, tree → builder)
- Keep optional deps (e.g., `email_validator`) opt-in
- Dispatch on node-kind to a specific concrete editor

This is intentional. Don't hoist these to module top to "clean up" —
ruff knows the rule and won't complain.

### Naming

- Modules: lowercase, snake_case (`yaml.py`, `routes.py`)
- Classes: PascalCase (`StringNode`, `StudioApp`)
- Functions/methods: snake_case (`build_form_tree`, `set_value`)
- Constants: UPPER_SNAKE (`DRAFT_FILENAME`)
- Private helpers: leading underscore (`_build_commented_map`,
  `_resolve_node`)
- Module trailing underscore reserved for stdlib collisions
  (`io/json_.py` because `io.json` would collide if anyone ever did
  `from pydantic_studio.io import json`)

## Test patterns

- **`uv run pytest -q`** runs the default suite (1234 tests currently).
  This intentionally skips `tests/e2e/` and disables the pytest-playwright
  plugin because plugin registration interferes with Textual
  `App.run_test()` under `asyncio_mode="auto"`.
- **Browser e2e** runs explicitly:
  `uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra"`.
  Install Chromium first with `uv run playwright install chromium` on a
  developer machine, or `uv run playwright install --with-deps chromium`
  in Linux CI.
- **CI split**: `.github/workflows/ci.yml` runs the default test suite
  on Python 3.11, 3.12, 3.13, and 3.14. The browser, frontend bundle,
  wheel/sdist, `twine check`, and wheel and sdist install smoke gates run
  once on Python 3.13 after the matrix passes. Every CI job passes the
  intended version to `uv sync --python` and asserts `sys.version_info`
  before running tests.
- **TUI tests**: use `App.run_test()` which returns a `Pilot` async
  context. Always `await pilot.pause()` before DOM queries — `on_mount`
  pushes the `EditorScreen` asynchronously, and the screen isn't active
  until the event loop yields once. Use **`app.screen.query_one(...)`**
  not `app.query_one(...)` — the latter searches the base screen.
- **Web API tests**: use `fastapi.testclient.TestClient` for the JSON
  `/api/*` routes and Playwright for the bundled SPA. The React SPA's
  canonical path is JSON over `/api/tree`, `/api/mutations`,
  `/api/submit`, `/api/cancel`, and `/api/heartbeat`; legacy form-post
  routes and HTMX/Jinja assets are intentionally absent.
- **TDD discipline**: write the failing test first, run it, see the
  failure, write the minimal code, see it pass, commit. Phase
  implementations earned strong test coverage by following this every
  task.
- **Round-trip tests**: every new I/O writer needs a `save → reload →
  assert state == previous state` test. Phase 4's enum-bearing
  schema is a useful golden case.

## Common gotchas

### Textual 8.x specifics

- `App.tree` is a built-in read-only property (renders the DOM). We
  override it on `StudioApp` with a writable property — see
  `renderers/textual_/app.py`. If you need the DOM-debug tree, use
  `super().tree` or rename our attribute.
- `Select.NULL` is the no-selection sentinel in **textual 8.x** (a
  `NoSelection` instance). In **textual ≤7.x** the same sentinel was
  named `Select.BLANK` and `NULL` did not exist. In textual 8.x
  `Select.BLANK` still exists but is `False` (inherited from `Widget`,
  unrelated to selection state) — do **not** use it as a sentinel.
  Both `widgets/scalars.py` and `widgets/containers.py` define a
  module-level `_SELECT_BLANK` shim (`getattr(Select, "NULL", None)`,
  falling back to `Select.BLANK` if the attribute is absent) that
  picks the right value across versions; use it instead of
  `Select.NULL` directly (issue #4 regressed when an implementer
  "fixed" the plan's `BLANK` → `NULL` against 8.x without noticing
  7.x users would crash).
- `BINDINGS: ClassVar[list[BindingType]] = [...]` — the `ClassVar`
  annotation satisfies ruff's `RUF012` rule.
- `await self.recompose()` is the idiomatic way to re-render a widget
  after state changes. Manual `remove_children + compose + mount` will
  hit `DuplicateIds` errors because `remove_children` returns an
  awaitable.
- `App.action_quit` is a priority binding at the App level. To route
  Ctrl+C through a Screen, override `App.action_quit` to delegate to
  `self.screen.action_quit()`.

### Pydantic v2 specifics

- `model_dump(mode="python")` leaves Enum/Decimal/UUID/datetime as
  Python instances. ruamel.yaml can't serialize Python-only types.
  **Use `mode="json"`** when feeding output to a YAML/TOML writer.
  The PreviewPane and `save_yaml` both do this.
- `EmailStr` is a plain class in Pydantic v2 (not `Annotated[str, ...]`),
  so detection looks at `type_.__name__ == "EmailStr"` directly without
  `strip_annotated`.
- `re.compile(pattern).flags` includes `re.UNICODE` (32) by default on
  Python 3 — strip it before storing on `PatternNode.flags` so user
  comparisons against `re.IGNORECASE` work.

### File-format quirks

- ruamel.yaml stores per-key comments on `cm.ca.items[key]` (a list of
  CommentToken) and document-level comments on `cm.ca.comment`. The
  `_copy_comment_if_present` helper covers both.
- tomlkit needs `comment()` calls **before** `add(key, value)` — order
  matters because the comment attaches to the next-added key.
- bytes in JSON go through Pydantic's base64 encoder by default, but in
  YAML with a `bytes | None` field type, Pydantic emits UTF-8 strings.
  `BytesNode` works around this with a hex-encoded
  `field_serializer` + `model_validator(mode="before")` pair.

## Workflow conventions

### Git

- **Commit and merge only.** **Never push** to origin without explicit
  user confirmation. This is a standing instruction across every phase.
- One feature branch per plan: `feature/phase-N-<topic>`.
- `--no-ff` merge to master with a descriptive merge commit.
- Tag the feature tip before merging: `vX.Y.Z-phase-N`.
- Major releases also get a plain version tag (`v0.1.0`).

### Plan-driven development

- Each phase starts with a plan document at
  `docs/superpowers/plans/YYYY-MM-DD-pydantic-studio-phase-N-*.md`.
- Plans use the `superpowers:writing-plans` skill. They list every task
  with TDD steps inline (write failing test → run → implement → run →
  commit).
- Execute via the `superpowers:subagent-driven-development` skill: one
  fresh subagent per task, with two-stage review (spec compliance +
  code quality) for substantive tasks.
- After each phase, the Final Reviewer flags housekeeping items for the
  next phase's first task. This bundling pattern keeps tech debt from
  accumulating.

### Skills used

- `superpowers:writing-plans` — drafts the implementation plan
- `superpowers:subagent-driven-development` — executes per-task
- `superpowers:executing-plans` — alternative inline execution
- `superpowers:test-driven-development` — every task uses TDD
- `superpowers:requesting-code-review` — review subagent template

### Model selection

The user prefers **Opus 4.7** for all subagent dispatches in this
project (overrides the Subagent-Driven skill's default
"least-powerful-model" guidance). Pass `model: "opus"` to the Agent
tool when dispatching implementer or reviewer subagents. The skill's
quality benefits (catching framework quirks, multi-file integration
issues) compound with the higher-capability model.

## Where to look for things

| If you need… | Look at |
|---|---|
| Spec / requirements | `docs/superpowers/specs/2026-05-05-pydantic-studio-design.md` |
| Phase decisions | `docs/superpowers/plans/2026-05-06-pydantic-studio-phase-N-*.md` |
| Architecture overview | `docs/site/architecture.md` |
| User-facing tutorial | `docs/site/tutorial.md` |
| API reference | `docs/site/api.md` (mkdocstrings auto-render) |
| CLI reference | `docs/site/cli.md` |
| FormTree mutations | `src/pydantic_studio/tree/nodes.py` (search for `def set_value`) |
| Type registry | `src/pydantic_studio/tree/builder.py` |
| YAML round-trip | `src/pydantic_studio/io/yaml.py` |
| TUI widget dispatch | `src/pydantic_studio/renderers/textual_/widgets/field_list.py` |
| Web JSON API | `src/pydantic_studio/renderers/html/routes.py` and `serialize.py` |
| Web SPA source | `frontend/src/` |
| Committed Web bundle | `src/pydantic_studio/renderers/html/static/dist/` |

## Deferred items

These are still deliberate non-goals unless the user asks for them:

- Markdown rendering of `Field(description=...)` in the UIs
- Light-theme toggle / custom `theme.css` for Textual
- mkdocs publishing to GitHub Pages
- Demo gif/screencast
- Status-bar widget for inline error display in TUI
- LLM-assisted defaults (`fill_with_llm`)
- Multi-profile management (dev/staging/prod overlays)

## Common debugging starting points

| Symptom | First check |
|---|---|
| YAML representer error on save | `model_dump(mode=...)` should be `"json"` |
| Pilot DOM query returns None | `await pilot.pause()`, then use `app.screen.query_one` |
| Widget id collision | Check `_sanitize_id(path)` for pre-escaped underscores |
| Web field does not update | Check `/api/mutations`, `mutation_result`, and Query cache |
| save_yaml raises ValidationFailedError | Unset required fields need `save_draft_yaml` |
| pyright reports many renderer errors | Check `[tool.pyright] exclude` is intact |
| Test asserting `node.value` is None | Default-seeding was removed; seed with `tree.set_value` |

## Final note

Read the relevant phase plan before making big changes. Each plan
documents the *why* of design decisions made at that phase, which is
often more useful than the resulting code. The plans were written to
the standard "engineer with zero codebase context" — they explain
everything.
