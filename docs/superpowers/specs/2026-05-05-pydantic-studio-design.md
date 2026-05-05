# pydantic-studio — Design Document

| Field | Value |
|---|---|
| Date | 2026-05-05 |
| Status | Draft, awaiting user review |
| Predecessor | [promptantic](https://github.com/phil65/promptantic) (CLI-only, prompt-toolkit-based) |
| License | MIT |
| Working dir at design time | `D:\Projects\Work\pydantic-config\` (rename to `pydantic-studio` deferred — see O-2) |

---

## 1. Overview

`pydantic-studio` is an **interactive editor for Pydantic models**, built to generate **config files** (YAML / TOML / JSON) for software developers. It offers three first-class frontends — a modern terminal UI (Textual), an ephemeral local web app (HTMX + Tailwind), and a CLI shorthand — all driven by a single shared form-state model.

It is the spiritual successor to `promptantic`, fixing two structural limitations:

1. CLI-only — no web mode
2. Type handlers tightly coupled to `prompt_toolkit`, blocking multi-frontend reuse

### 1.1 Primary use case

A developer is preparing `config.yaml` for an application whose schema is defined as a Pydantic model. They run:

```bash
$ pydantic-studio edit config.yaml --schema myapp.config:Settings
```

A Textual TUI opens (or `--frontend web` opens a browser tab) showing the existing config on the left, a live YAML preview on the right, and a tree of nested sections in the sidebar. They edit, hit "Save", and `config.yaml` is rewritten with field-description comments preserved and updated.

### 1.2 Differentiation from existing packages

| Package | Niche | Overlap |
|---|---|---|
| promptantic | Terminal-only, line-by-line | We replace + extend (modern TUI + web) |
| pydantic-forms | FastAPI router + React, multi-user prod | We are dev-tool-shaped, ephemeral, no auth |
| fh-pydantic-form | FastHTML SSR forms, multi-user | Same as above |
| pydantic-settings | Loads config from files (no UI) | Complementary — we generate, they consume |
| pydantic-config (existing pkg) | Yaml/toml/json file loading | Different problem; coincidental name conflict drove our rename |

---

## 2. Goals & non-goals

### 2.1 v0.1 goals (locked features)

| # | Feature | Rationale |
|---|---|---|
| 1 | Load existing `config.yaml/json/toml` and edit interactively | Most common workflow — config files iterate, rarely written from blank |
| 2 | Real-time dual-panel preview: form on left, rendered config text on right | Bridges "form thinking" and "yaml thinking" — promptantic users have no view of the output |
| 3 | Sidebar tree-nav for nested models / lists / dicts | promptantic forces strict linear order; we let users jump |
| 5 | Undo/redo (Ctrl+Z) + auto-saved draft for crash recovery | Editing a 50-field config is high-stakes; one slip shouldn't lose work |
| 7 | Field descriptions render as **markdown**; constraints (`gt`, `regex`, etc.) shown as icons/badges | Beauty + clarity — schema authors put effort into descriptions |
| 8 | YAML output preserves user comments on edit; new files auto-generate description comments | Round-trip integrity is the whole point of a config tool |

### 2.2 v0.1 non-goals (deferred to v0.2+)

- Multi-profile management (dev/staging/prod overlays)
- LLM-assisted defaults / autofill
- `.env` file format
- Multi-user web service / authentication
- Hosted cloud editor
- Pydantic v1 support
- VS Code / JetBrains plugin

---

## 3. High-level architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Public API   ps.fill()  ps.edit()  ps.run()  ps.write()         │
│  CLI entry    pydantic-studio fill | edit | run | check          │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
   ┌──────────────────┐                   ┌──────────────────────────┐
   │ I/O Layer        │                   │ Form Tree (core)         │
   │ • yaml load      │ ── existing ───▶  │ • FormTree (BaseModel)   │
   │ • toml load      │      dict         │ • Nodes: Group / Field / │
   │ • json load      │                   │   Sequence / Mapping /   │
   │                  │                   │   Union                  │
   │ • yaml writer    │ ◀── instance ───  │ • Snapshots / Undo       │
   │ • toml writer    │                   │ • Validation cache       │
   │ • json writer    │                   │ • Draft auto-save        │
   └──────────────────┘                   └──────────────┬───────────┘
                                                         │
                                       ┌─────────────────┴─────────────────┐
                                       ▼                                   ▼
                            ┌──────────────────────┐           ┌──────────────────────┐
                            │ Textual Renderer     │           │ HTML Renderer        │
                            │ • App + Screens      │           │ • FastAPI server     │
                            │ • per-Node widgets   │           │ • Jinja2 templates   │
                            │ • theme.css          │           │ • HTMX partials      │
                            │                      │           │ • Tailwind styles    │
                            │ Renders + binds      │           │ Renders + binds      │
                            └──────────┬───────────┘           └──────────┬───────────┘
                                       │                                  │
                                       └────── two-way binding ───────────┘
                                              (via path-addressed mutations)
```

**Architectural commitment**: the Form Tree is the **single source of truth**. Renderers translate user intent into tree mutations and translate tree state into pixels — they own no canonical state. Adding a 4th frontend = implementing one new Renderer; the tree code does not change.

---

## 4. Module layout

```
src/pydantic_studio/
├── __init__.py              # Public API: fill, edit, run, write, Studio
├── cli.py                   # `pydantic-studio` (typer-based)
├── exceptions.py            # PydanticStudioError + subclasses
├── tree/
│   ├── nodes.py             # FormTree + Node hierarchy (all pydantic models)
│   ├── builder.py           # build_form_tree(schema, existing) → FormTree
│   ├── validation.py        # node-level + cross-field validation
│   ├── snapshots.py         # Snapshot, UndoStack, Draft (auto-save)
│   └── paths.py             # JSONPath-style addressing into a tree
├── types/
│   ├── registry.py          # NodeBuilder registry; pluggable for custom types
│   ├── primitives.py        # Str/Int/Float/Bool/Decimal builders
│   ├── datetime.py          # Date/Time/Datetime/Timedelta/Timezone
│   ├── network.py           # IPv4/IPv6/Network/URL/DSN/Email
│   ├── special.py           # Path, UUID, SecretStr, Pattern
│   ├── constrained.py       # constr/conint detection (borrowed from promptantic)
│   └── annotated.py         # Annotated[...] traversal
├── io/
│   ├── loaders.py           # load_yaml / load_toml / load_json
│   └── writers.py           # write_yaml / write_toml / write_json (smart)
└── renderers/
    ├── base.py              # Renderer Protocol; auto-detect logic
    ├── textual_/
    │   ├── app.py
    │   ├── screens.py
    │   ├── widgets/         # one widget per node type
    │   └── theme.css        # Textual CSS
    └── html/
        ├── renderer.py      # HtmlRenderer entry
        ├── server.py        # FastAPI app
        ├── routes.py        # /, /preview, /partials/<path>, /submit, /cancel
        ├── templates/
        │   ├── base.jinja
        │   ├── form.jinja
        │   ├── preview.jinja
        │   └── partials/    # one partial per node type
        └── static/
            ├── studio.css   # compiled Tailwind, vendored at build
            ├── htmx.min.js  # vendored (~14 KB)
            ├── alpine.min.js  # vendored (~16 KB)
            └── studio.js    # ~50 lines of bespoke sprinkles

tests/
├── unit/
│   ├── test_builder.py
│   ├── test_snapshots.py
│   ├── test_io_yaml.py      # golden-file tests
│   └── test_writers_smart.py
├── integration/
│   └── test_full_cycle.py   # mock renderer, mutation script → instance
├── e2e/
│   ├── test_textual.py      # uses App.run_test() Pilot framework
│   └── test_html.py         # Playwright Chromium
└── fixtures/                # sample schemas, golden config files

docs/
├── index.md
├── tutorial.md
├── api.md
├── architecture.md
└── superpowers/specs/...    # this design doc lives here
```

---

## 5. Form Tree — the core abstraction

The Form Tree is itself a hierarchy of Pydantic models. **This is the central design bet**: by making the editor's runtime state itself a Pydantic model, we get **validation, deep copy, JSON serialization, and round-trip** for free, with zero hand-rolled state machinery.

### 5.1 Node hierarchy

```python
class FormTree(BaseModel):
    """Root. Holds metadata + the root node + history."""
    schema_class: type[BaseModel]
    schema_name: str                  # e.g. 'myapp.config:Settings'
    root: GroupNode
    created_at: datetime
    snapshots: list[bytes] = []       # serialized prior states (LRU-capped)
    cursor: int = 0                   # position in snapshots (for undo/redo)
    draft_path: Path | None = None

class FormNode(BaseModel):            # abstract base
    name: str
    description: str | None = None    # markdown
    required: bool = True
    error: str | None = None          # last validation message

class FieldNode(FormNode):            # leaf
    value: Any
    default: Any
    # Subclasses (one per pydantic type family):
    # StringNode(min_length, max_length, regex, secret, multiline)
    # IntNode(ge, le, gt, lt, multiple_of)
    # FloatNode / DecimalNode
    # BoolNode
    # EnumNode(choices) / LiteralNode(choices)
    # DateNode / TimeNode / DateTimeNode / TimedeltaNode / TimezoneNode
    # PathNode(must_exist, kind)
    # UUIDNode / IPv4Node / IPv6Node / NetworkNode
    # URLNode / DSNNode / EmailNode / PatternNode
    # SecretStrNode (display masked)

class GroupNode(FormNode):            # represents a nested BaseModel
    fields: list[FormNode]
    schema_class: type[BaseModel]

class SequenceNode(FormNode):         # list/set/tuple
    item_factory: NodeFactory         # builds a fresh child node on add
    items: list[FormNode]
    min_length: int | None
    max_length: int | None
    homogeneous: bool                 # tuple[int, str] → False; list[int] → True

class MappingNode(FormNode):          # dict
    key_factory: NodeFactory
    value_factory: NodeFactory
    entries: list[tuple[FormNode, FormNode]]

class UnionNode(FormNode):            # Union / Optional / discriminated unions
    variants: list[NodeFactory]
    selected_index: int | None
    selected_node: FormNode | None
    discriminator: str | None
```

### 5.2 Builder

```python
def build_form_tree(
    schema: type[BaseModel],
    existing: dict[str, Any] | None = None,
) -> FormTree:
    """Build an empty (or pre-populated) form tree from a Pydantic model."""
```

The builder dispatches by type via the **Type Registry**:

```python
class NodeBuilder(Protocol):
    def matches(self, type_: type) -> bool: ...
    def build(
        self,
        type_: type,
        field_info: FieldInfo,
        existing: Any,
    ) -> FormNode: ...

# Default registration order matters — first match wins
DEFAULT_BUILDERS: list[NodeBuilder] = [
    StringBuilder, IntBuilder, FloatBuilder, BoolBuilder, DecimalBuilder,
    EnumBuilder, LiteralBuilder,
    DateBuilder, TimeBuilder, DateTimeBuilder, TimedeltaBuilder, TimezoneBuilder,
    PathBuilder, UUIDBuilder, IPv4Builder, IPv6Builder, NetworkBuilder,
    URLBuilder, DSNBuilder, EmailBuilder, SecretStrBuilder, PatternBuilder,
    SequenceBuilder, MappingBuilder, UnionBuilder, GroupBuilder,
    AnyFallbackBuilder,  # safety net — renders as JSON textarea
]

# Custom registration for end users
ps.register_builder(MyTypeBuilder())
```

Type detection (Annotated unwrapping, Union detection, Literal/Constrained probing) **is vendored from promptantic's `type_utils.py`** — promptantic is MIT and battle-tested for this exact dispatch problem. Concrete plan: copy the relevant predicate functions (`is_constrained_str`, `is_constrained_int`, `is_literal_type`, `is_union_type`, `is_tuple_type`, `is_enum_type`, `is_model_type`, `is_skip_prompt`, `strip_annotated`) into our `types/annotated.py` and `types/constrained.py`, prepend an attribution comment naming `phil65/promptantic` and the SHA we copied from. Adapt as needed; do not link or vendor the full library.

### 5.3 Mutations

```python
class FormTree:
    def set_value(self, path: str, value: Any) -> ValidationResult:
        """Set value at JSONPath; pushes snapshot; runs node-local validation."""

    def add_item(self, path: str, value: Any = MISSING) -> ValidationResult:
        """Append to a SequenceNode at path."""

    def remove_item(self, path: str, index: int) -> ValidationResult:
        """Remove from a SequenceNode."""

    def select_variant(self, path: str, variant_idx: int) -> ValidationResult:
        """Switch UnionNode variant; old subtree is discarded (snapshot kept)."""

    def undo(self) -> bool: ...
    def redo(self) -> bool: ...

    def to_instance(self) -> BaseModel:
        """Materialize into the user's schema_class. Re-validates fully via TypeAdapter.
        Raises ValidationError if invalid (caller should refuse to exit submit)."""
```

All mutations push a snapshot **before** applying — undo is total and cheap.

### 5.4 Snapshots

A snapshot is `tree.model_dump_json(...).encode()` — pydantic gives us this for free. We keep a bounded ring buffer (default 50) plus the most recent snapshot mirrored to `draft_path` for crash recovery.

---

## 6. Renderer protocol

```python
class Renderer(Protocol):
    name: ClassVar[str]               # 'textual', 'html'

    async def run(self, tree: FormTree) -> FormTree:
        """Render the tree, let the user interact, return the mutated tree.

        Raises:
            CancelledByUser: if the user cancels.
        """

def auto_detect_renderer(prefer: str = "auto") -> Renderer:
    """If 'auto': use Textual when stdout.isatty(), else HTML.
       Honors $PYDANTIC_STUDIO_FRONTEND env var."""
```

### 6.1 Textual renderer

- Single screen, three regions:
  - **Sidebar** (left): tree nav. Textual's `Tree` widget showing GroupNode hierarchy. Click → focus a section.
  - **Main** (center): scrollable form for the focused section. One Textual widget per FieldNode subtype.
  - **Preview** (right): live-rendered YAML/TOML/JSON pane (toggle between formats; defaults to YAML).
- Bottom bar: status (`unsaved changes`, last validation result) and key hints (`^Z`/`^Y` undo/redo, `^S` save, `^Q` quit).
- Theme: dark by default, light variant via `--theme light`. Slate/zinc grays + a single accent color, defined in `theme.css` (Textual CSS).

### 6.2 HTML renderer

- Boots a FastAPI app on `127.0.0.1:<random_free_port>`, opens browser to `http://localhost:<port>/` via `webbrowser.open()`.
- One HTML page; HTMX swaps partials on edit:
  - `<input hx-post="/field/<path>" hx-trigger="change">` → server validates → returns updated YAML preview partial AND any error message.
  - Add/remove items in sequences: `hx-post="/seq/<path>/add"` → returns the new row partial.
- Layout: same three-region (sidebar tree, form, preview) using Tailwind grid. Mobile collapses to tabs (low priority for v0.1).
- Persistence on page refresh: server still has the `FormTree` — page just re-renders.
- **Submit**: posts `/submit` → server calls `tree.to_instance()`, exits the FastAPI loop, returns the instance to the calling Python code; browser shows a "Done — you can close this tab" page.
- **Cancel**: `/cancel` → raises `CancelledByUser` in the calling code.
- **Tab-closed detection**: the page polls `/heartbeat` every 5 seconds via HTMX (`hx-get="/heartbeat" hx-trigger="every 5s"`). If the server sees no heartbeat for **30 seconds** (configurable via `Studio(html_idle_timeout=30)`), it treats the tab as abandoned, saves a draft, and raises `CancelledByUser`. This avoids the "user closed the browser, server hangs forever" failure mode.

`htmx.min.js`, `alpine.min.js`, and the compiled `tailwind.css` are **vendored at build time** — runtime needs no Node, no CDN.

### 6.3 Cross-frontend identity

A **path** identifies any node in the tree (e.g., `root.database.replicas[2].host`). Both renderers send the same path strings; the tree resolves them. A draft saved from web can be resumed in TUI, and vice versa.

---

## 7. Library API

```python
import pydantic_studio as ps

# Convenience (most users)
config = ps.fill(MyConfig)                       # auto-detect frontend
config = ps.edit("config.yaml", MyConfig)        # load + edit
ps.run(MyConfig, source="config.yaml", target="config.yaml")  # full cycle
ps.write("config.yaml", config, schema=MyConfig) # smart write

# Forced frontend
config = ps.fill(MyConfig, frontend="web")       # opens browser
config = ps.fill(MyConfig, frontend="tui")       # Textual

# Async (FastAPI / async-app contexts)
config = await ps.fill_async(MyConfig)

# Advanced — full control
studio = ps.Studio(
    theme="dark",
    frontend="auto",
    autosave_path=".studio.draft.json",
    yaml_indent=2,
    preserve_comments=True,
    secret_handling="env_placeholder",  # 'mask' | 'omit' | 'env_placeholder'
)
config = studio.fill(MyConfig)
```

Public re-exports: `Studio`, `FormTree`, `Renderer`, `NodeBuilder`, `register_builder`, `PydanticStudioError` (and subclasses), `__version__`.

---

## 8. CLI

```
pydantic-studio fill  <schema_ref> [-o <file>] [--frontend tui|web]
pydantic-studio edit  <file>       [--schema <schema_ref>] [--frontend ...]
pydantic-studio run   <schema_ref>   --source <file> --target <file>
pydantic-studio check <file>       [--schema <schema_ref>]
```

`<schema_ref>` syntax: `module.path:ClassName` (matches uvicorn/gunicorn convention).

Exit codes: `0` ok, `1` validation failure, `2` user cancelled, `3` IO error, `4` schema-load error.

CLI built with `typer` (already canonical in the pydantic ecosystem).

---

## 9. Data flow — the load → edit → save cycle

```
ps.run(MyConfig, source='config.yaml', target='config.yaml')
   │
   ▼
io.loaders.load_yaml('config.yaml')
   ─ returns (dict, RuamelDoc)        # comments preserved in RuamelDoc
   │
   ▼
tree = build_form_tree(MyConfig, existing=dict)
   ─ walks fields; dispatches to NodeBuilder
   ─ populates FieldNode.value
   ─ runs initial validation; errors become FieldNode.error (do not raise)
   │
   ▼
renderer = auto_detect_renderer()    # 'textual' or 'html'
   │
   ▼
mutated_tree = await renderer.run(tree)
   ─ subscribes to tree mutations
   ─ on user edit: tree.set_value(path, value); preview re-rendered
   ─ on submit:    validates whole tree; if errors, refuses; else returns
   │
   ▼
instance = mutated_tree.to_instance()  # full validate via TypeAdapter
   │
   ▼
io.writers.write_yaml('config.yaml', instance, schema=MyConfig, original_doc=RuamelDoc)
   ─ smart writer: preserves user comments where keys haven't changed
   ─ new keys: inject schema description as comment above
   ─ field order: follow schema (not user reordering)
   ─ SecretStr → '${ENV_VAR}' placeholder (configurable)
```

---

## 10. Format I/O

| Format | Read library | Write library | Round-trip |
|---|---|---|---|
| YAML  | `ruamel.yaml.YAML(typ='rt')` | `ruamel.yaml.YAML(typ='rt')` | Comments + key order preserved |
| TOML  | `tomllib` (stdlib, parse only) | `tomlkit` | Comments + key order preserved |
| JSON  | stdlib `json` | `pydantic.model_dump_json(indent=2)` | No comments — accepted limitation |

### 10.1 Smart YAML writer rules (v0.1)

1. **Field order** = schema definition order (not user input order, not file's existing order)
2. **Comments above fields** = `Field(description=...)` — markdown stripped to plain text, wrapped at 80 cols
3. **User comments on existing fields** = preserved verbatim if the field still exists
4. **User comments on now-deleted fields** = dropped, with a warning to stderr
5. **SecretStr** → `password: ${MY_PASSWORD}  # set via env var` (configurable via `secret_handling` option)
6. **None** → `field: ~` (yaml standard for null)
7. **Datetime** → ISO 8601 string (`2026-05-05T12:34:56`)
8. **Path** → forward-slash even on Windows for portability

### 10.2 TOML writer rules

Same shape as YAML rules; nested groups become `[section.subsection]` tables.

### 10.3 JSON writer

`model_dump_json(indent=2, by_alias=True)` — no special handling beyond pydantic's own.

---

## 11. Undo/redo + draft persistence

- Every mutation pushes a snapshot (`tree.model_dump_json()`) to a bounded ring buffer (default 50 entries).
- `cursor` points to current; `undo()` decrements and rehydrates; `redo()` increments.
- Branching after undo discards the redo tail (standard editor convention).
- **Draft auto-save**: on every mutation, write `tree.model_dump_json()` to `<cwd>/.pydantic-studio.draft.json` (path overridable via `Studio(autosave_path=...)`). Atomic via temp + rename.
- **Recovery**: on startup, **before launching any renderer**, the entry function (`fill` / `edit` / `run`) checks for a draft. If one exists and is newer than the source file, prints to stderr and prompts on stdin:
  ```
  Found a draft from 12 minutes ago at .pydantic-studio.draft.json. Resume? [Y/n]
  ```
  This is a plain terminal prompt — it runs before Textual takes over the screen and before the browser opens, so it works in both frontends. Non-interactive callers (no TTY) skip the prompt and ignore the draft (with a warning). A `--resume` / `--no-resume` CLI flag overrides the prompt.
- Draft is deleted on successful submit.
- **Schema-class compatibility**: a draft records `schema_name`. If on resume the schema cannot be re-imported or has a structurally incompatible change, recovery aborts with a clear error and the draft is left intact (user decides to keep or delete).

---

## 12. Error handling

| Failure | Where | Behavior |
|---|---|---|
| Field validation error | live, on mutation | Render inline, allow further edits, block submit |
| Cross-field error (e.g., model_validator) | on submit | Banner + focus first failing field |
| YAML parse error (load) | startup | Friendly message + line/col, exit 3 |
| Schema import failure | startup | Stack with hint about `module:Class` syntax, exit 4 |
| `KeyboardInterrupt` (TUI Ctrl+C) | renderer | Save draft, exit 2 |
| Browser tab closed (HTML) | renderer | After 30s grace without re-poll, save draft, exit 2 |
| Disk full on write | writer | Print error, leave original file untouched (write-temp-then-rename) |
| Network types' DNS lookup (e.g., URL validation) | live | Validate format only, do not hit network — keep editor offline-capable |

All exceptions surface as subclasses of `PydanticStudioError` for programmatic handling.

---

## 13. Testing strategy

### 13.1 Unit (fast, no I/O)
- `tree/builder.py`: every builder, including degenerate cases (empty model, recursive model, `Any` type, generic types).
- `tree/snapshots.py`: undo/redo correctness, ring-buffer eviction, draft round-trip.
- `io/writers.py`: golden-file tests `(schema, instance) → expected_yaml_text`, fixtures under `tests/fixtures/golden/`.

### 13.2 Integration (mock renderers)
- `MockRenderer` records mutations the test harness pushes; verifies `to_instance()` round-trip.
- Both `TextualRenderer` and `HtmlRenderer` test seams must produce identical instances given identical mutation scripts.

### 13.3 E2E
- **Textual**: `App.run_test()` + `Pilot` snapshot framework. No TTY required.
- **HTML**: Playwright (Chromium). Boots `HtmlRenderer`, fills fields, clicks Submit, asserts the captured Python instance equals the expected.

### 13.4 CI matrix
- Unit + integration on Linux/macOS/Windows × Python 3.11/3.12/3.13/3.14.
- E2E on Linux only (Playwright cost).
- Type checking: `pyright` in basic mode; tests excluded from strict.

---

## 14. Implementation order (writing-plans seed)

| Phase | Scope | Effort |
|---|---|---|
| 1 | Form Tree skeleton (Group + primitive Field nodes) + builder + snapshots + `to_instance` round-trip | 2-3 days |
| 2 | Type coverage: port promptantic's type detection; cover Sequence/Mapping/Union/Enum/Literal/Constrained | 2-3 days |
| 3 | YAML I/O (load + smart write with comments) | 1-2 days |
| 4 | Textual renderer: split layout + primitive widgets + preview pane + undo/redo/save | 4-5 days |
| 5 | HTML renderer: FastAPI scaffold + HTMX form + Tailwind compile pipeline + matching widget set | 5-6 days |
| 6 | TOML + JSON I/O | 1 day |
| 7 | Polish: markdown descriptions, constraint badges, draft recovery prompt, theming | 2-3 days |
| 8 | Documentation (mkdocs-material), README, example schemas, demo gif/screencast | 2 days |
| **Total v0.1** | | **~3-4 weeks of focused work** |

---

## 15. Open questions / risks

| # | Question | Resolution proposal |
|---|---|---|
| O-1 | How to handle config-file fields not present in the schema? | Default: drop with stderr warning; `--strict` causes an error. Document the behavior. |
| O-2 | Project directory rename `pydantic-config` → `pydantic-studio`? | Defer until after design approved. Mid-session rename risks breaking the working directory pointer. Do at the end of Phase 1 in a clean checkpoint. |
| O-3 | Tailwind build pipeline in dev deps, or commit compiled CSS? | Commit compiled CSS to repo; provide `scripts/build_css.sh` (uses `npx tailwindcss`) for contributors who change styles. Runtime never touches Node. |
| O-4 | How to embed Textual `App.test()` in CI without a TTY? | Use Textual's headless mode via `App.run_test()` returning a `Pilot`. No TTY required. |
| O-5 | Types we cannot render (`Callable`, custom Protocols, types with no `__init__`)? | Render as a "frozen" pre-set field with a notice; user cannot edit but value is preserved on round-trip. |
| O-6 | Is `tomlkit` round-trip robust for nested arrays of tables? | Spike test in Phase 6. Fallback: JSON-flavoured TOML output without comments preserved. |
| O-7 | Should the Web renderer support multiple concurrent browser tabs of the same session? | v0.1: no — first tab wins; second tab gets "session in another tab" page. v0.2 candidate. |
| O-8 | Recursive Pydantic models — how deep do we render eagerly? | Lazy-render: GroupNode for a recursive type starts collapsed; user expands to materialize. Prevents infinite trees. |

---

## 16. Future (post-v0.1) directions

- **v0.2 candidates** in priority order:
  1. Multi-profile management (dev/staging/prod overlay editor)
  2. LLM-assisted defaults (`fill_with_llm("a sensible dev config")`)
  3. Schema hints via `json_schema_extra` (`{"widget": "slider", "step": 0.1}`)
- Optional remote-hosted mode (auth-gated FastAPI) for team config workflows
- VS Code / JetBrains plugin: open Studio in an editor pane via webview
- Native integration with `pydantic-settings` so it can consume Studio output directly

---

## 17. Out-of-spec dependencies (commit list)

For unambiguous handoff to writing-plans:

**Runtime**:
- `pydantic >= 2.7`
- `ruamel.yaml >= 0.18`
- `tomlkit >= 0.13`
- `textual >= 0.85`
- `fastapi >= 0.115`
- `uvicorn[standard] >= 0.32`
- `jinja2 >= 3.1`
- `typer >= 0.13`

**Build-time only** (does not ship to runtime):
- `tailwindcss` CLI (`npx tailwindcss`) — invoked by `scripts/build_css.sh`

**Dev**:
- `pytest >= 8`, `pytest-asyncio`, `pytest-cov`
- `playwright >= 1.50`
- `ruff`, `pyright`
- `mkdocs-material`, `mkdocs-mknodes`

**Vendored static assets** (in `src/pydantic_studio/renderers/html/static/`):
- `htmx.min.js` (v2.x, ~14 KB)
- `alpine.min.js` (v3.x, ~16 KB)
- `studio.css` (compiled Tailwind, expected ~30 KB minified)

---

*End of design document. Awaiting user review before transition to `writing-plans` skill.*
