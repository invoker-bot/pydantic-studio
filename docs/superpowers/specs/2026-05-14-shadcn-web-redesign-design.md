# Web renderer redesign — shadcn-ui + Tailwind + React

| Field | Value |
|---|---|
| Date | 2026-05-14 |
| Status | Draft, awaiting user review |
| Successor to | `src/pydantic_studio/renderers/html/` (FastAPI + Jinja + HTMX) |
| Driver | The current HTMX renderer is visually plain, ships several rendering gaps (no inline list/map item editors, no inner editor for selected union variant, nested groups invisible inside the form pane), and surfaces neither validation feedback nor constraint hints. |
| Working dir at design time | `D:\Projects\Work\pydantic-studio\` |

---

## 1. Overview

Replace the FastAPI + Jinja + HTMX web renderer with a React 18 SPA built using shadcn/ui components and Tailwind CSS, served by the existing FastAPI process. The FormTree on the server stays authoritative; HTML routes are rewritten as a JSON API that the SPA consumes.

The redesign is end-to-end: visuals, missing inline editors, validation surface, constraint hints, light/dark theme, schema search, and a per-field type/description affordance. The Textual TUI and CLI are unaffected.

### 1.1 Why now

The current renderer is the weakest of the three frontends. Specifically:

1. **Visual** — system-ui defaults, 12 lines of CSS, raw `<button>` and `<input>` controls.
2. **Functional** — `list` items render as `[i] kind` text with no per-item editor; `dict` entries show `key → value` text only; `union` shows a variant dropdown but no editor for the selected variant; nested groups vanish from the form pane (sidebar-only navigation).
3. **Diagnostic** — `Field(ge=…, description=…)` exists in the FormTree but is never surfaced. Validation errors only show after `Save`.

These compound: the form looks unfinished AND is unfinished.

### 1.2 Non-replacements

- **FormTree, mutation API, registry, builders** — unchanged. The redesign is a renderer swap.
- **Textual TUI, CLI** — unchanged.
- **YAML/TOML/JSON I/O** — unchanged.
- **`StudioServer` class** — kept; only its routes are rewritten.

---

## 2. Goals & non-goals

### 2.1 In scope (v0.2)

| # | Feature | Rationale |
|---|---|---|
| 1 | shadcn/ui + Tailwind CSS design system | Visual consistency, accessible primitives, well-documented patterns |
| 2 | Inline editors for `list` items, `dict` entries, and the selected `union` variant | Fills today's rendering gaps |
| 3 | Nested `BaseModel` groups rendered inline (collapsible card) | Sidebar nav becomes optional, not gating |
| 4 | Field-level validation feedback (red border + helper text, on blur and on submit) | Mirrors shadcn-form's affordance |
| 5 | Type badges & constraint hints (`int · ≥1 · ≤64`, `str · 3..32`, `required`) | Schema authorial intent is visible to the user |
| 6 | Live YAML preview as a tab alongside Form / Errors | Same affordance as today, organized into tabs |
| 7 | Light / dark theme toggle with OS-default detection | Standard dev-tool expectation |
| 8 | Search/filter input on big sidebars (>30 fields) | Lookups remain fast when schemas grow |
| 9 | Undo / redo wired to the existing snapshot ring (UI buttons + Cmd/Ctrl-Z, Cmd/Ctrl-Shift-Z) | Existing capability gets a surface |
| 10 | Pre-built `static/dist/` bundle committed; `pip install` requires no Node | Distribution parity with v0.1 |

### 2.2 Out of scope (deferred)

- Drag-to-reorder for list items (numeric `↑/↓` buttons only)
- Real-time multi-user collaboration
- Custom theme builder beyond light/dark presets
- Keyboard-shortcut overlay / help modal
- Schema diff view between saved drafts
- Server-Sent Events for push updates (heartbeat poll stays simple)
- i18n (English only)

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Browser (one tab)                                           │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  React 18 SPA                                           │ │
│  │  - TanStack Query cache (key: ["tree"])                 │ │
│  │  - shadcn/ui primitives                                 │ │
│  │  - Tailwind CSS v4                                      │ │
│  │  - YAML preview computed client-side from tree JSON     │ │
│  └─────────────────────────────────────────────────────────┘ │
│                ▲ JSON                                        │
│                ▼                                             │
└────────────────┼─────────────────────────────────────────────┘
                 │  (fetch, no websockets)
┌────────────────┼─────────────────────────────────────────────┐
│  FastAPI process (uvicorn, ephemeral)                        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  StudioServer (unchanged)                               │ │
│  │  ├── GET   /                  → index.html              │ │
│  │  ├── GET   /static/dist/*     → bundled JS/CSS/font     │ │
│  │  ├── GET   /api/tree          → FormTree as JSON        │ │
│  │  ├── POST  /api/mutations     → apply mutation, return  │ │
│  │  │                              updated FormTree        │ │
│  │  ├── POST  /api/submit        → save + flag submitted   │ │
│  │  ├── POST  /api/cancel        → flag cancelled          │ │
│  │  └── GET   /api/heartbeat     → mark alive              │ │
│  └─────────────────────────────────────────────────────────┘ │
│                 │                                            │
│                 ▼                                            │
│  FormTree (the single source of truth — unchanged)           │
└──────────────────────────────────────────────────────────────┘
```

### 3.1 State management

- **Server-authoritative**. The FormTree on the server is the truth. Every mutation is a `POST /api/mutations` with `{op, path, payload}`; response is the full updated tree JSON.
- **Client-side cache**. TanStack Query stores the tree under `["tree"]`. On mutation success, `setQueryData(["tree"], response)` updates the cache and triggers re-render. No optimistic updates in v1 — the round-trip is on localhost (sub-ms), so the latency win isn't worth the consistency complexity.
- **Derived state**. YAML preview is computed client-side from the cached tree (no extra route). Errors tab reads the same source.

### 3.2 Mutation contract

```ts
type Mutation =
  | { op: "set_value";    path: string; value: JsonValue }
  | { op: "add_item";     path: string; }
  | { op: "remove_item";  path: string; index: number }
  | { op: "move_item";    path: string; from: number; to: number }
  | { op: "add_entry";    path: string; key: string }
  | { op: "remove_entry"; path: string; index: number }
  | { op: "rename_key";   path: string; index: number; new_key: string }
  | { op: "select_variant"; path: string; variant_index: number };
```

Each maps 1:1 to an existing FormTree mutator. Server applies, then returns `{tree: <full json>, validation: {ok: bool, errors: [...]}}`.

### 3.3 Why no WebSocket / SSE

- Local dev tool, single user, single tab. No push needed.
- Heartbeat poll (existing) handles tab-close detection.
- One fewer dependency, one fewer failure mode.

---

## 4. Repo layout

```
frontend/                                # NEW — TypeScript source, tracked in git
  package.json
  pnpm-lock.yaml                         # pinned, committed
  vite.config.ts
  tailwind.config.ts                     # Tailwind v4 — minimal config
  tsconfig.json
  index.html                             # Vite entry point
  src/
    main.tsx                             # ReactDOM.createRoot
    App.tsx                              # layout shell
    api/
      client.ts                          # fetch wrapper, base URL, error handling
      tree.ts                            # GET /api/tree + zod parser
      mutations.ts                       # POST /api/mutations + typed mutation builder
      submit.ts                          # POST /api/submit, /api/cancel
    components/
      ui/                                # shadcn/ui primitives (copied source)
        button.tsx
        input.tsx
        select.tsx
        tabs.tsx
        ...
      form/
        FormField.tsx                    # dispatcher by node.kind
        fields/
          StringField.tsx
          IntField.tsx
          BoolField.tsx
          EnumField.tsx
          LiteralField.tsx
          GroupField.tsx                 # nested, collapsible
          SequenceField.tsx              # list of any item kind
          MappingField.tsx               # dict of any value kind
          UnionField.tsx                 # variant chips + inner editor
          AnyField.tsx                   # mode picker + value editor
          SecretField.tsx                # password + show toggle
          DatetimeField.tsx              # date+time pickers
          ...                            # one per node kind, ~20 components
        TypeBadge.tsx                    # "int · ≥1 · ≤64"
        Description.tsx                  # muted description text
        FieldError.tsx                   # red helper text
      layout/
        AppShell.tsx                     # header + sidebar + main grid
        Sidebar.tsx                      # group tree + search
        Header.tsx                       # title + unsaved counter + save/cancel
        Tabs.tsx                         # Form / YAML / Errors
      preview/
        YamlPreview.tsx                  # syntax-highlighted YAML
        ErrorsPanel.tsx                  # validation issues with click-to-jump
    hooks/
      useTree.ts                         # wraps useQuery(["tree"])
      useMutation.ts                     # wraps useMutation w/ optimistic invalidation
      useUnsavedCount.ts                 # derived from tree.snapshots
      useTheme.ts                        # light/dark toggle + localStorage
    types/
      tree.ts                            # FormTree TS types (mirrors Python nodes)
      mutations.ts                       # Mutation discriminated union
    styles/
      globals.css                        # @import "tailwindcss"; theme vars
  scripts/
    build.sh                             # `pnpm install && pnpm build`

src/pydantic_studio/renderers/html/      # MUTATED
  __init__.py                            # unchanged exports
  server.py                              # serves index.html; routes registered for JSON API
  routes.py                              # REWRITTEN — JSON only
  serialize.py                           # NEW — FormTree → JSON, Mutation → tree mutator
  static/
    dist/                                # NEW — committed Vite output
      index.html
      assets/
        index-<hash>.js
        index-<hash>.css
    htmx.min.js                          # DELETED
    studio.css                           # DELETED
  templates/                             # DELETED entire directory
```

The `frontend/` directory lives at the repo root (not under `src/`) because:
- It is not a Python package — it's a Vite project with its own `package.json` and toolchain.
- Pyright / ruff won't touch it (no Python).
- Its build output, not its source, gets shipped in the wheel.

### 4.1 Wheel packaging

`pyproject.toml` already uses `uv_build`. Add an explicit data file include for the dist directory:

```toml
[tool.uv.build]
include = [
  "src/pydantic_studio/renderers/html/static/dist/**",
]
```

`frontend/` itself does NOT ship in the wheel. Only the bundled output does.

### 4.2 CI / contributor experience

- **End user**: `pip install pydantic-studio`. No change. Bundle is already in the wheel.
- **Python-only contributor**: `uv sync && uv run pytest`. No Node touched.
- **Frontend contributor**: `cd frontend && pnpm install && pnpm dev` opens Vite dev server with HMR; backend can be run separately and CORS-allowed. `pnpm build` updates `static/dist/`. Commit both source and bundle.
- **CI**: a single workflow runs Python tests; a second job runs `pnpm install && pnpm build && git diff --exit-code static/dist/` so a PR that changes frontend source without rebuilding fails fast.

---

## 5. JSON API contract

### 5.1 `GET /api/tree`

Returns the full FormTree as JSON. The shape mirrors the existing Pydantic models in `pydantic_studio.tree.nodes`, with `kind` discriminating each node:

```json
{
  "schema_name": "examples.server_config:ServerConfig",
  "root": {
    "kind": "group",
    "name": "<root>",
    "fields": [
      { "kind": "string", "name": "name", "value": "billing-api",
        "required": true, "description": "...",
        "min_length": 3, "max_length": 32, "pattern": "..." },
      { "kind": "group", "name": "database", "fields": [...] },
      ...
    ]
  },
  "validation": { "ok": true, "errors": [] }
}
```

Implementation: `FormTree.model_dump(mode="json", exclude={"schema_class"})`. The `schema_class` (a Python class object) is non-serialisable; the client doesn't need it.

### 5.2 `POST /api/mutations`

Request:
```json
{ "op": "set_value", "path": "database.primary.host", "value": "db-x.internal" }
```

Response:
```json
{
  "tree": { ... full updated tree ... },
  "validation": { "ok": false, "errors": [
    { "path": "database.primary.port", "message": "Field required" }
  ]}
}
```

The server's existing validate-first contract is preserved — mutations that fail validation return the un-mutated tree with the failure in `validation.errors`. Because v1 uses no optimistic updates, the client simply renders whatever the server sends back; a rejected mutation shows up as "the field's value didn't change" plus an entry in `validation.errors`.

### 5.3 `POST /api/submit` / `POST /api/cancel` / `GET /api/heartbeat`

Same semantics as today's HTML routes — set `submitted` / `cancelled` flags on `StudioServer`, return `{ok: true}` JSON. The auto-exit watchdog in `run_html_app` is unchanged.

---

## 6. Frontend component design

### 6.1 Field dispatcher

```ts
// FormField.tsx
export function FormField({ node, path }: { node: TreeNode; path: string }) {
  switch (node.kind) {
    case "string":    return <StringField  node={node} path={path} />;
    case "int":       return <IntField     node={node} path={path} />;
    case "bool":      return <BoolField    node={node} path={path} />;
    case "group":     return <GroupField   node={node} path={path} />;
    case "sequence":  return <SequenceField node={node} path={path} />;
    case "mapping":   return <MappingField node={node} path={path} />;
    case "union":     return <UnionField   node={node} path={path} />;
    ...
  }
}
```

One component per node kind. Mirrors the Python registry's structure 1:1.

### 6.2 Shared field chrome

Every field gets the same outer shell:

```tsx
<FieldRow>
  <FieldHeader>
    <Label>{node.name}</Label>
    <TypeBadge node={node} />               // "int · ≥1 · ≤64"
    {node.required && <RequiredBadge />}
  </FieldHeader>
  {node.description && <Description>{node.description}</Description>}
  <InputArea>
    {/* the kind-specific input */}
  </InputArea>
  <FieldError path={path} />               // pulled from validation cache
</FieldRow>
```

`FieldRow`, `FieldHeader`, `Label`, `TypeBadge`, `Description`, `InputArea`, `FieldError` are reusable shadcn-style primitives in `components/form/`.

### 6.3 Container fields

- **SequenceField**: stack of cards, each card is a `FormField` for the item's kind. `[↑] [↓] [✕]` controls per item, `+ Add` dashed-border button below.
- **MappingField**: stack of two-column cards (key input + value `FormField`). `+ Add Entry` button. Keys are validated for uniqueness on blur.
- **UnionField**: row of variant chips (shadcn `ToggleGroup`), then a `FormField` for the selected variant inline below.
- **GroupField**: collapsible card with chevron. Default expanded for the root; default collapsed for nested groups deeper than 2 levels.

### 6.4 Validation surface

- Field-level: red border + small helper text under the input. Triggered on blur, persists until the field changes.
- Aggregate: `Errors` tab lists every validation error with `path` + `message`. Clicking jumps to the field (sets focus + scrolls into view).
- Header: an unsaved-changes counter pulled from `tree.snapshots.length`.

### 6.5 Tabs

`shadcn-ui` tabs primitive. Three tabs:

- **Form** — the editor. Default.
- **YAML** — read-only syntax-highlighted view. Live; updates on every mutation. Highlighter library chosen during phase 5 (see O-4).
- **Errors** — only the validation issues (empty state when none).

### 6.6 Sidebar

- Group tree, flattened to first two levels by default.
- Search input filters by field-name substring; matching path is bolded.
- Active group is highlighted; click scrolls the form pane to that group.
- Sub-items (list indices, dict keys) appear under their group with grey index/key text.

### 6.7 Theme

- `localStorage["theme"]` of `"light" | "dark" | "system"`.
- shadcn ships both palettes via CSS variables. Toggle button in header.
- Default: `system`.

---

## 7. Build pipeline

### 7.1 Tools

- **pnpm** for installs (lockfile committed). Faster, disk-friendlier than npm; widely used in shadcn docs.
- **Vite** for dev + bundle. React + TS template.
- **Tailwind CSS v4** (`@tailwindcss/vite` plugin) for utilities.
- **TypeScript strict mode**.

### 7.2 Dev loop

```bash
cd frontend
pnpm install                 # one-time
pnpm dev                     # opens http://localhost:5173 with HMR
# in another terminal:
cd .. && uv run python -c "from pydantic_studio import run_html_app, build_form_tree; ..."
```

Vite's `server.proxy` forwards `/api/*` and `/static/*` to the FastAPI process. Both processes hot-reload independently.

### 7.3 Production build

```bash
cd frontend
pnpm build
# emits ../src/pydantic_studio/renderers/html/static/dist/
git add ../src/pydantic_studio/renderers/html/static/dist
git commit -m "build: refresh frontend bundle"
```

A `frontend/scripts/build.sh` wraps this so contributors don't need to remember the flags.

### 7.4 CI guard

`.github/workflows/ci.yml` adds a job:

```yaml
frontend-bundle-fresh:
  - run: cd frontend && pnpm install --frozen-lockfile && pnpm build
  - run: git diff --exit-code src/pydantic_studio/renderers/html/static/dist
```

A PR that touches `frontend/src/**` but forgets `pnpm build` fails this check.

---

## 8. Migration plan (phased)

| Phase | Scope | Tests pass after |
|---|---|---|
| 1 | Add JSON routes (`/api/tree`, `/api/mutations`, etc.) **alongside** today's HTML routes. Add `serialize.py`. New tests for JSON contract. | All existing + new JSON contract tests. |
| 2 | Scaffold `frontend/`: Vite + React + Tailwind + shadcn primitives. Empty page that fetches `/api/tree` and dumps it. | Existing tests + a smoke test that `static/dist/index.html` loads under TestClient. |
| 3 | Build `FormField` dispatcher + primitive field renderers (string/int/bool/enum/literal). Wire mutations. | Existing + Playwright test: load schema, edit one field, see preview update. |
| 4 | Container fields: sequence, mapping, union, group (inline), any. | Add Playwright tests for each container kind. |
| 5 | Polish: validation surface, type badges, constraint hints, theme toggle, sidebar search. | Visual regression snapshots via Playwright. |
| 6 | Delete `templates/`, `htmx.min.js`, `studio.css`. Remove HTML routes (now redundant). Update `routes.py` to JSON-only. | Existing test suite migrated; deleted-template tests removed. |
| 7 | Documentation: update `docs/site/architecture.md`, add `docs/site/web-frontend.md`, refresh screenshots. | `mkdocs build --strict` green. |

Each phase ships behind the existing branch / `--no-ff` merge convention. Phase 1 doesn't break anything; phase 6 is the breaking switch.

---

## 9. Testing strategy

### 9.1 Python side

- **Unit**: `serialize.py` round-trip — FormTree → JSON → expected shape; Mutation JSON → tree mutator dispatch.
- **Integration**: TestClient (existing pattern) for every API endpoint; validation-failure path; heartbeat behaviour preserved.

### 9.2 Frontend

- **Unit (Vitest)**: each field component renders correctly for representative nodes; type badges format `int · ≥1 · ≤64` correctly; YAML derivation matches Python's output for fixture schemas.
- **End-to-end (Playwright)**: spin up `run_html_app(tree)` in a fixture, drive the browser through edit/save/cancel flows. Capture screenshots for visual regression on the four example schemas.

### 9.3 Performance budgets

- Initial bundle ≤ 250 KB gzip (React + shadcn primitives + Tailwind utilities used).
- `GET /api/tree` for a 100-field schema returns in < 50 ms.
- A mutation round-trip in < 30 ms on localhost.

---

## 10. Open questions

- **O-1 (resolved)**: bundle distribution — commit prebuilt artifact.
- **O-2 (resolved)**: layout direction — two pane (sidebar + main) with Form/YAML/Errors tabs.
- **O-3 (resolved)**: state management — server-authoritative, no optimistic updates in v1.
- **O-4**: YAML highlighting library. `shiki` is full-featured but pulls grammars. `prismjs` is smaller but uglier. Decide during phase 5; either works.
- **O-5**: do we ship a "settings" route for theme/density preferences, or stay in `localStorage` only? Lean `localStorage` only — the editor is ephemeral.

---

## 11. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Bundle size creeps past 250 KB | medium | shadcn is copy-paste (no unused exports); Tailwind v4 has built-in dead-code elimination; Vite's bundle analyzer in CI |
| Contributor accidentally commits frontend source change without rebuilt bundle | medium | CI guard in §7.4 |
| FormTree JSON shape drifts from Python types | medium | zod schemas in `frontend/src/api/tree.ts` mirror Pydantic types; round-trip tests; types regenerated automatically in CI is overkill — manual sync is fine for ~20 node kinds |
| Playwright tests flaky in CI | medium | use `@playwright/test`'s built-in retries; pin browser version |
| shadcn's React 19 / 18 churn | low | pin to React 18 LTS; revisit in v0.3 |

---

## 12. Success criteria

The redesign is done when:

1. All four example schemas (`examples/01..04`) load and edit correctly in the new UI.
2. Every rendering-gap noted in §1.1 is closed (inline list/map/union editors, nested groups, validation feedback, type badges, constraint hints).
3. `pip install pydantic-studio` (from PyPI sdist OR wheel) opens the new UI with no Node required.
4. `uv run pytest` is green; the Python test count grows (new JSON contract tests, new Playwright e2e); no test is silently deleted.
5. Bundle is ≤ 250 KB gzip.
6. Documentation reflects the new architecture and screenshots match what users see.
