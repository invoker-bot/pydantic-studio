# Shadcn Web Redesign — Phase 3: Primitive Field Renderers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace App.tsx's JSON dump with real form components for the 5 primitive Pydantic types (str/int/bool/enum/literal), wire `useMutation` against Phase 1's `/api/mutations` endpoint, and prove the loop works via a Playwright e2e test that edits a field and asserts the server-side tree updates.

**Architecture:** A `FormField` dispatcher switches on `node.kind` to render one of 5 primitive components (StringField, IntField, BoolField, EnumField, LiteralField) plus a minimal GroupField that iterates child fields. Each primitive component owns local input state, calls `useApplyMutation` on blur, and re-syncs from `node.value` after the server returns the updated tree (server-authoritative pattern). All components share a chrome layer (FieldRow + FieldHeader + Label + TypeBadge + Description + FieldError) and consume shadcn primitives (Button, Input, Label, Select, Switch). zod schemas in `api/schemas.ts` parse the JSON tree into a typed discriminated union, replacing Phase 2's `Promise<unknown>` seam.

**Tech Stack:** React 18 + TypeScript strict, TanStack Query 5 (useMutation), zod 3, shadcn/ui primitives (installed via `pnpm dlx shadcn@latest add`), Tailwind v4. Test stack adds pytest-playwright + Chromium for e2e.

**Spec:** `docs/superpowers/specs/2026-05-14-shadcn-web-redesign-design.md` §6 (component design), §8 Phase 3 row. This plan implements only Phase 3 of that spec.

**Predecessors:**
- Phase 1 (`v0.2.0-phase-1`, merged at `b1c0ff8`): JSON API at `/api/tree`, `/api/mutations`, `/api/submit`, `/api/cancel`, `/api/heartbeat`
- Phase 2 (`v0.2.0-phase-2`, merged at `969d6f3`): Vite/React/Tailwind toolchain, empty SPA that dumps `/api/tree` JSON, committed `static/dist/` bundle

---

## File Structure

**Create (frontend source):**
- `frontend/src/api/schemas.ts` — zod schemas + inferred TS types for FormTree, GroupNode, and the 5 primitive node kinds. ~80 lines.
- `frontend/src/api/mutations.ts` — `applyMutation()` POST helper + `useApplyMutation()` TanStack Query hook. ~50 lines.
- `frontend/src/components/form/FormField.tsx` — dispatcher switching on `node.kind`. ~40 lines.
- `frontend/src/components/form/chrome/FieldRow.tsx` — wrapper card per field. ~12 lines.
- `frontend/src/components/form/chrome/FieldHeader.tsx` — label + type badge + required badge row. ~20 lines.
- `frontend/src/components/form/chrome/TypeBadge.tsx` — `int · ≥1 · ≤64` style pill. ~30 lines.
- `frontend/src/components/form/chrome/RequiredBadge.tsx` — amber "required" pill. ~6 lines.
- `frontend/src/components/form/chrome/Description.tsx` — muted description text. ~6 lines.
- `frontend/src/components/form/chrome/FieldError.tsx` — red helper text under the input. ~10 lines.
- `frontend/src/components/form/fields/StringField.tsx` — Input + local state + mutation-on-blur. ~30 lines.
- `frontend/src/components/form/fields/IntField.tsx` — same pattern, parseInt on blur. ~35 lines.
- `frontend/src/components/form/fields/BoolField.tsx` — Switch + immediate mutation. ~25 lines.
- `frontend/src/components/form/fields/EnumField.tsx` — Select over `node.choices`. ~35 lines.
- `frontend/src/components/form/fields/LiteralField.tsx` — Select over `node.choices` (similar). ~30 lines.
- `frontend/src/components/form/fields/GroupField.tsx` — minimal: maps `node.fields` to `<FormField>`. ~12 lines.
- `frontend/src/components/ui/button.tsx` — shadcn Button primitive (CLI-generated)
- `frontend/src/components/ui/input.tsx` — shadcn Input primitive
- `frontend/src/components/ui/label.tsx` — shadcn Label primitive
- `frontend/src/components/ui/select.tsx` — shadcn Select primitive (Radix-based)
- `frontend/src/components/ui/switch.tsx` — shadcn Switch primitive (Radix-based)

**Modify:**
- `frontend/vite.config.ts` — set `base: command === "build" ? "/static/dist/" : "/"` so the built `index.html`'s `<script src="/static/dist/assets/...">` resolves under FastAPI's existing static mount. Dev mode stays at `/`.
- `frontend/src/api/tree.ts` — change `fetchTree()` return type from `Promise<unknown>` to `Promise<FormTree>`; call `FormTreeSchema.parse(...)` before returning.
- `frontend/src/App.tsx` — replace JSON-dump body with a 2-column layout: left = `<FormField node={tree.root} path="">`, right = `<pre>{JSON.stringify(tree, null, 2)}</pre>` (kept as "Live preview" until Phase 5's YAML tab replaces it).
- `frontend/package.json` — adds shadcn deps via the CLI: `@radix-ui/react-label`, `@radix-ui/react-select`, `@radix-ui/react-switch`, `lucide-react`, `class-variance-authority`. Plus zod.
- `frontend/src/styles/globals.css` — shadcn CLI may append CSS variable block for theme colors. Acceptable.
- `pyproject.toml` — add `pytest-playwright` to the `dev` group.
- `tests/unit/test_html_static_bundle.py` — update the diagnostic message in `test_static_dist_assets_are_served` now that the base-path fix lets the root-relative `/assets/...` path also work (or split into two tests: one for the mounted path, one for the root-relative path).

**Create (tests):**
- `tests/e2e/__init__.py` — empty.
- `tests/e2e/conftest.py` — pytest fixture spinning up uvicorn on a fixed port with a known schema; teardown stops it.
- `tests/e2e/test_spa_edit_flow.py` — first Playwright e2e test: load page, edit a string field, blur, fetch `/api/tree`, assert the new value appears in the tree AND in the preview `<pre>` text.

**Bundle artifacts (regenerated):**
- `src/pydantic_studio/renderers/html/static/dist/index.html` — rebuilt with new asset base path
- `src/pydantic_studio/renderers/html/static/dist/assets/*.js` — bundled React + components
- `src/pydantic_studio/renderers/html/static/dist/assets/*.css` — bundled Tailwind + shadcn theme

**Do NOT touch:**
- `src/pydantic_studio/tree/` — Phase 1 / pre-Phase territory
- `src/pydantic_studio/renderers/html/{routes.py,server.py,serialize.py}` — Phase 1 territory
- `src/pydantic_studio/renderers/html/templates/` — Phase 6 deletes
- The existing HTMX-driven tests (`tests/unit/test_html_server.py`, `test_html_api_routes.py`, `test_html_serialize.py`) — Phase 1/2 owns them

---

## Prerequisites

Before Task 1, confirm Node + pnpm are still working (Phase 2 already verified):

```bash
node --version    # v20+ (v24.15.0 on host)
pnpm --version    # 9.x (via corepack)
cd frontend && pnpm install --frozen-lockfile && cd ..   # should be a no-op
```

If anything is broken, fix before starting.

---

## Task 1: Vite base-path fix + smoke-test diagnostic update

**Files:**
- Modify: `frontend/vite.config.ts`
- Modify: `tests/unit/test_html_static_bundle.py` (update diagnostic message text)

The Phase 2 final review flagged that the built `index.html` references `/assets/<hash>.js` root-relative, which 404s under FastAPI's `/static/dist/index.html` mount. Setting `base: "/static/dist/"` rewrites the built HTML to `<script src="/static/dist/assets/<hash>.js">` which DOES resolve via the static mount. Use a conditional so `pnpm dev` (Vite's dev server) keeps serving at `/`.

- [ ] **Step 1: Update vite.config.ts**

Replace the existing `defineConfig({ ... })` call with a function form so we can switch on the command:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Vite builds output INTO the Python package's static/ tree so the
// existing StudioServer._mount_static at "/static" serves it without
// any new route. Setting base="/static/dist/" on production builds
// (only) makes the built index.html reference assets at
// /static/dist/assets/<hash>.js so they resolve via the same mount.
// Dev mode keeps base="/" so `pnpm dev` and its proxy work normally.
const PYTHON_DIST = path.resolve(
  __dirname,
  "../src/pydantic_studio/renderers/html/static/dist",
);

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/dist/" : "/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: PYTHON_DIST,
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
}));
```

- [ ] **Step 2: Confirm tsc still passes**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0. The function-form `defineConfig` is fully typed.

- [ ] **Step 3: Update the diagnostic in test_html_static_bundle.py**

Read `tests/unit/test_html_static_bundle.py`. In `test_static_dist_assets_are_served`, the assertion's diagnostic message currently says "Phase 5/6 fixes this". After the base fix lands and the bundle is rebuilt (T14), the assets test STILL passes (the mounted-path assertion is the same). But the diagnostic text is now stale — the fix is landing in Phase 3, not deferred.

Find the assertion that contains "Phase 5/6 fixes this" (likely around line 56). Update the diagnostic message to:

```python
    assert response.status_code == 200, (
        f"GET {mounted_path} returned {response.status_code}; "
        f"the static mount under /static/dist/ should serve every "
        f"file under src/pydantic_studio/renderers/html/static/dist/. "
        f"Re-run `pnpm build` from frontend/ to refresh the bundle."
    )
```

(The post-build verification that the root-relative `/assets/...` ALSO works will be added as a new test in T14, after the rebuilt bundle is committed.)

- [ ] **Step 4: Run the smoke test (still 2 passing)**

```bash
uv run python -m pytest tests/unit/test_html_static_bundle.py -q
```

Expected: 2 passed. The base fix only affects FUTURE builds; the currently-committed bundle still has root-relative paths, but the test asserts the mounted path which is independent of base.

- [ ] **Step 5: Commit**

```bash
git add frontend/vite.config.ts tests/unit/test_html_static_bundle.py
git commit -m "$(cat <<'EOF'
feat(frontend): set Vite base for production builds + refresh smoke diagnostic

Sets vite.config.ts base="/static/dist/" on production builds so the
built index.html's asset references (/static/dist/assets/<hash>.js)
resolve via FastAPI's existing /static mount. Dev mode (`pnpm dev`)
keeps base="/" so HMR and the /api proxy work unchanged.

This addresses the known limitation flagged in Phase 2 (and locked
into Phase 2 commit d169475's body) ahead of schedule: Phase 3's
Playwright e2e test needs the SPA to actually execute in-browser
when served by FastAPI, which requires resolvable asset paths.

The bundle itself isn't rebuilt in this commit - T14 rebuilds and
recommits the dist tree. test_html_static_bundle.py's stale "Phase
5/6 fixes this" diagnostic is refreshed accordingly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Install shadcn primitives + zod

**Files:**
- Modify: `frontend/package.json` (deps added by shadcn CLI + manual `pnpm add zod`)
- Modify: `frontend/pnpm-lock.yaml` (auto-updated)
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/components/ui/label.tsx`
- Create: `frontend/src/components/ui/select.tsx`
- Create: `frontend/src/components/ui/switch.tsx`
- Possibly Modify: `frontend/src/styles/globals.css` (shadcn CLI may append CSS variable block)

- [ ] **Step 1: Install zod (used by api/schemas.ts in T3)**

```bash
cd frontend
pnpm add zod
```

Expected: zod added to `dependencies`. Version ~3.23 or later.

- [ ] **Step 2: Install the 5 shadcn primitives we need**

```bash
pnpm dlx shadcn@latest add button input label select switch
```

For each primitive, the CLI will:
- Add Radix UI deps to `package.json` (e.g., `@radix-ui/react-label`, `@radix-ui/react-select`, `@radix-ui/react-switch`)
- Add `lucide-react` (icon library used by Select's chevron, etc.)
- Add `class-variance-authority` if not present (Button uses cva for variants)
- Write source files to `frontend/src/components/ui/<name>.tsx`
- On first invocation, append a CSS variable block to `frontend/src/styles/globals.css` for shadcn's theme colors

If the CLI prompts "components.json found, use existing configuration? (Y/n)", answer Y.

If the CLI prompts about TypeScript / Tailwind config — answer with defaults (already configured in Phase 2).

- [ ] **Step 3: Verify all 5 files exist**

```bash
ls src/components/ui/
```

Expected: `button.tsx input.tsx label.tsx select.tsx switch.tsx`.

- [ ] **Step 4: Typecheck**

```bash
pnpm exec tsc -b
```

Expected: exit 0. shadcn primitives are well-typed against the `cn`, Radix, and React 18 patterns.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml \
  frontend/src/components/ui frontend/src/styles/globals.css
git commit -m "$(cat <<'EOF'
feat(frontend): install shadcn primitives (button input label select switch) + zod

5 primitives installed via `pnpm dlx shadcn@latest add`, generated
into src/components/ui/. Adds Radix UI deps, lucide-react,
class-variance-authority as runtime deps (per shadcn convention).
globals.css gains shadcn's CSS variable block for the zinc theme.

zod added separately (used by api/schemas.ts in T3 to parse the JSON
tree into a typed discriminated union).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: zod schemas + typed fetchTree

**Files:**
- Create: `frontend/src/api/schemas.ts`
- Modify: `frontend/src/api/tree.ts`

- [ ] **Step 1: Write the zod schemas**

`frontend/src/api/schemas.ts`:

```typescript
// zod schemas mirroring the Phase 1 JSON API contract (see spec §5.1).
// Each schema corresponds to one FormNode subclass in
// src/pydantic_studio/tree/nodes.py. Phase 3 covers the 5 primitive
// kinds the dispatcher handles (string/int/bool/enum/literal) plus
// group (the root + nested groups). Phase 4 adds the dynamic kinds
// (sequence/mapping/union/any).

import { z } from "zod";

// Common base fields on every FormNode.
const NodeBase = z.object({
  name: z.string(),
  description: z.string().nullable(),
  required: z.boolean(),
  error: z.string().nullable(),
});

export const StringNodeSchema = NodeBase.extend({
  kind: z.literal("string"),
  value: z.string().nullable(),
  default: z.string().nullable(),
  min_length: z.number().nullable(),
  max_length: z.number().nullable(),
  pattern: z.string().nullable(),
  multiline: z.boolean(),
  secret: z.boolean(),
});

export const IntNodeSchema = NodeBase.extend({
  kind: z.literal("int"),
  value: z.number().nullable(),
  default: z.number().nullable(),
  ge: z.number().nullable(),
  le: z.number().nullable(),
  gt: z.number().nullable(),
  lt: z.number().nullable(),
  multiple_of: z.number().nullable(),
});

export const BoolNodeSchema = NodeBase.extend({
  kind: z.literal("bool"),
  value: z.boolean().nullable(),
  default: z.boolean().nullable(),
});

export const EnumNodeSchema = NodeBase.extend({
  kind: z.literal("enum"),
  value: z.unknown(),       // EnumNode.value is the enum member instance; opaque to client
  default: z.unknown(),
  enum_class_name: z.string(),
  choices: z.array(z.tuple([z.string(), z.unknown()])),  // [(name, member), ...]
});

export const LiteralNodeSchema = NodeBase.extend({
  kind: z.literal("literal"),
  value: z.unknown(),
  default: z.unknown(),
  choices: z.array(z.unknown()),
});

// GroupNode is recursive — define it before adding it to the union.
export interface GroupNodeData {
  kind: "group";
  name: string;
  description: string | null;
  required: boolean;
  error: string | null;
  schema_class: string;
  fields: FormNodeData[];
}

export const GroupNodeSchema: z.ZodType<GroupNodeData> = z.lazy(() =>
  NodeBase.extend({
    kind: z.literal("group"),
    schema_class: z.string(),
    fields: z.array(FormNodeSchema),
  }),
);

// Phase 3 dispatcher covers these 6 kinds. Phase 4 adds sequence,
// mapping, union, any (and the rest of the spec's 20+ node kinds).
// For now, unknown kinds parse loosely as a passthrough so the
// fetch doesn't reject the whole tree on a node Phase 3 doesn't
// understand yet (e.g., a sequence in the test schema).
const KnownNodeSchema = z.discriminatedUnion("kind", [
  StringNodeSchema,
  IntNodeSchema,
  BoolNodeSchema,
  EnumNodeSchema,
  LiteralNodeSchema,
  GroupNodeSchema,
]);

const UnknownNodeSchema = z.object({
  kind: z.string(),
  name: z.string(),
}).passthrough();

export const FormNodeSchema: z.ZodType<FormNodeData> = z.union([
  KnownNodeSchema,
  UnknownNodeSchema,
]);

export type FormNodeData =
  | z.infer<typeof StringNodeSchema>
  | z.infer<typeof IntNodeSchema>
  | z.infer<typeof BoolNodeSchema>
  | z.infer<typeof EnumNodeSchema>
  | z.infer<typeof LiteralNodeSchema>
  | GroupNodeData
  | { kind: string; name: string; [extra: string]: unknown };

export const FormTreeSchema = z.object({
  schema_name: z.string(),
  root: GroupNodeSchema,
  unsaved_count: z.number(),
}).passthrough();   // tolerate extra top-level fields (created_at, cursor, etc.)

export type FormTree = z.infer<typeof FormTreeSchema>;
```

- [ ] **Step 2: Update fetchTree to parse with zod**

Replace `frontend/src/api/tree.ts`:

```typescript
import { FormTreeSchema, type FormTree } from "@/api/schemas";

export async function fetchTree(): Promise<FormTree> {
  const response = await fetch("/api/tree");
  if (!response.ok) {
    throw new Error(`GET /api/tree failed: HTTP ${response.status}`);
  }
  const raw = await response.json();
  return FormTreeSchema.parse(raw);
}
```

The return type is now `FormTree` (the typed shape), not `unknown`. zod throws on schema mismatch — TanStack Query surfaces this as a fetch error, just like an HTTP failure.

- [ ] **Step 3: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0. App.tsx currently does `JSON.stringify(data, null, 2)` against the data from useQuery — `data` is now typed as `FormTree | undefined` but JSON.stringify accepts both. No App.tsx changes yet.

- [ ] **Step 4: Verify zod parses the actual /api/tree response**

```bash
cd ..
uv run python -c "
import json, sys
from pydantic import BaseModel
from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html.serialize import tree_to_json

class M(BaseModel):
    name: str = 'demo'
    workers: int = 4

print(json.dumps(tree_to_json(build_form_tree(M)), indent=2))
" > /tmp/tree-sample.json
```

(On Windows, replace `/tmp/tree-sample.json` with a path that works, e.g., `$env:TEMP\tree-sample.json` in PowerShell or just any temp path. The intent is to capture a real API response.)

Then test the parse:

```bash
cd frontend
pnpm exec tsx -e "import('fs').then(async fs => { const raw = JSON.parse(fs.readFileSync(process.argv[1] || '/tmp/tree-sample.json', 'utf-8')); const {FormTreeSchema} = await import('./src/api/schemas.ts'); console.log(FormTreeSchema.parse(raw).schema_name); })" /tmp/tree-sample.json
```

If `tsx` isn't installed, skip this step — T16's e2e test will exercise the parser end-to-end. The typecheck in Step 3 already verifies the schema compiles correctly.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/schemas.ts frontend/src/api/tree.ts
git commit -m "$(cat <<'EOF'
feat(frontend): typed tree parser via zod + 6 primitive node schemas

api/schemas.ts defines zod schemas mirroring the Phase 1 JSON
contract (spec §5.1): NodeBase fields, then 5 primitive node kinds
(string/int/bool/enum/literal) plus the recursive GroupNode.
Unknown kinds (sequence/mapping/union/any — Phase 4 work) parse via
a permissive passthrough so the fetch doesn't reject the whole tree
on a node Phase 3 doesn't yet understand.

fetchTree() now returns Promise<FormTree> instead of Promise<unknown>;
zod throws on schema mismatch, surfaced as a fetch error by TanStack
Query.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: applyMutation + useApplyMutation hook

**Files:**
- Create: `frontend/src/api/mutations.ts`

- [ ] **Step 1: Write the mutation helper and hook**

`frontend/src/api/mutations.ts`:

```typescript
// Wrapper around POST /api/mutations from Phase 1. Each field
// component calls useApplyMutation() and invokes .mutate(...) with
// a typed Mutation. On success the tree is invalidated and refetched,
// triggering re-render of all subscribed components with the new
// server-side state.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FormTreeSchema, type FormTree } from "@/api/schemas";

// Discriminated union mirroring spec §3.2. Phase 3 wires set_value
// (used by every primitive field). Container ops (add_item, etc.)
// land in Phase 4 when the corresponding components arrive.
export type Mutation =
  | { op: "set_value"; path: string; value: unknown }
  | { op: "add_item"; path: string }
  | { op: "remove_item"; path: string; index: number }
  | { op: "move_item"; path: string; from: number; to: number }
  | { op: "add_entry"; path: string; key: string }
  | { op: "remove_entry"; path: string; index: number }
  | { op: "rename_key"; path: string; index: number; new_key: string }
  | { op: "select_variant"; path: string; variant_index: number };

export interface MutationResponse {
  tree: FormTree;
  validation: { ok: boolean; errors: Array<{ path: string; message: string }> };
  mutation_result: { ok: boolean; errors: readonly string[] };
}

export async function applyMutation(mutation: Mutation): Promise<MutationResponse> {
  const response = await fetch("/api/mutations", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(mutation),
  });
  if (response.status === 400) {
    // Unknown op or malformed request (Phase 1 spec §5.2 contract).
    const body = await response.json();
    throw new Error(`Mutation rejected: ${body.detail ?? "bad request"}`);
  }
  if (!response.ok) {
    throw new Error(`POST /api/mutations failed: HTTP ${response.status}`);
  }
  const raw = await response.json();
  // The tree field always needs zod parsing; the rest is shape-stable
  // enough that we trust it. Future polish could add a full envelope
  // schema if we ever want stronger guarantees.
  return {
    tree: FormTreeSchema.parse(raw.tree),
    validation: raw.validation,
    mutation_result: raw.mutation_result,
  };
}

export function useApplyMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: applyMutation,
    onSuccess: (response) => {
      // Server-authoritative: replace the cached tree with what the
      // server returned. Every component using useQuery(['tree']) will
      // re-render with the new state on the next React tick.
      queryClient.setQueryData(["tree"], response.tree);
    },
  });
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/mutations.ts
git commit -m "$(cat <<'EOF'
feat(frontend): useApplyMutation hook for POST /api/mutations

applyMutation() posts a typed Mutation (the discriminated union from
spec §3.2; Phase 3 uses only set_value, Phase 4 wires the rest) to
Phase 1's /api/mutations endpoint and parses the response envelope
{tree, validation, mutation_result}. The tree is run through zod.

useApplyMutation() wraps it with TanStack Query's useMutation +
setQueryData(['tree'], response.tree) on success — server-
authoritative invalidation: the cached tree gets replaced with what
the server returned, and every component bound to useQuery(['tree'])
re-renders.

400 responses surface as thrown Errors (the spec's promise: unknown
ops + malformed requests yield 400, NOT 200; the route layer in
routes.py:328 already enforces this).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Shared chrome components

**Files:**
- Create: `frontend/src/components/form/chrome/FieldRow.tsx`
- Create: `frontend/src/components/form/chrome/FieldHeader.tsx`
- Create: `frontend/src/components/form/chrome/TypeBadge.tsx`
- Create: `frontend/src/components/form/chrome/RequiredBadge.tsx`
- Create: `frontend/src/components/form/chrome/Description.tsx`
- Create: `frontend/src/components/form/chrome/FieldError.tsx`

All 6 files are tiny. Listing them in one task because they're consumed together by every field component in T6-T11.

- [ ] **Step 1: Write FieldRow.tsx**

`frontend/src/components/form/chrome/FieldRow.tsx`:

```typescript
// Spacing wrapper used by every primitive field component. Provides
// vertical rhythm between fields and a consistent left-padded layout.

import type { ReactNode } from "react";

export function FieldRow({ children }: { children: ReactNode }) {
  return <div className="space-y-1.5">{children}</div>;
}
```

- [ ] **Step 2: Write FieldHeader.tsx**

`frontend/src/components/form/chrome/FieldHeader.tsx`:

```typescript
// Header row above a field's input: label + type badge + required pill.

import type { ReactNode } from "react";

export function FieldHeader({ children }: { children: ReactNode }) {
  return <div className="flex items-baseline gap-2">{children}</div>;
}
```

- [ ] **Step 3: Write TypeBadge.tsx**

`frontend/src/components/form/chrome/TypeBadge.tsx`:

```typescript
// Small monospace pill showing the field's type + constraints.
// Examples:
//   "str · 3..32"
//   "int · ≥1 · ≤64"
//   "HttpUrl"

import type { FormNodeData } from "@/api/schemas";

function formatNumeric(node: FormNodeData): string {
  const parts: string[] = [];
  if ("ge" in node && node.ge !== null) parts.push(`≥${node.ge}`);
  if ("le" in node && node.le !== null) parts.push(`≤${node.le}`);
  if ("gt" in node && node.gt !== null) parts.push(`>${node.gt}`);
  if ("lt" in node && node.lt !== null) parts.push(`<${node.lt}`);
  if ("multiple_of" in node && node.multiple_of !== null) {
    parts.push(`%${node.multiple_of}`);
  }
  return parts.join(" · ");
}

function formatString(node: FormNodeData): string {
  if (!("min_length" in node)) return "";
  const min = node.min_length;
  const max = node.max_length;
  if (min !== null && max !== null) return `${min}..${max}`;
  if (min !== null) return `≥${min}`;
  if (max !== null) return `≤${max}`;
  return "";
}

export function TypeBadge({ node }: { node: FormNodeData }) {
  let summary = node.kind;
  if (node.kind === "int" || node.kind === "float" || node.kind === "decimal") {
    const constraints = formatNumeric(node);
    if (constraints) summary = `${node.kind} · ${constraints}`;
  } else if (node.kind === "string") {
    const constraints = formatString(node);
    if (constraints) summary = `str · ${constraints}`;
    else summary = "str";
  }
  return (
    <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
      {summary}
    </span>
  );
}
```

- [ ] **Step 4: Write RequiredBadge.tsx**

`frontend/src/components/form/chrome/RequiredBadge.tsx`:

```typescript
export function RequiredBadge() {
  return (
    <span className="rounded bg-amber-100 px-1.5 text-[10px] text-amber-900">
      required
    </span>
  );
}
```

- [ ] **Step 5: Write Description.tsx**

`frontend/src/components/form/chrome/Description.tsx`:

```typescript
import type { ReactNode } from "react";

export function Description({ children }: { children: ReactNode }) {
  return <p className="text-xs text-zinc-500">{children}</p>;
}
```

- [ ] **Step 6: Write FieldError.tsx**

`frontend/src/components/form/chrome/FieldError.tsx`:

```typescript
// Red helper text under the input. Renders nothing when message is null.

export function FieldError({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="text-xs text-red-600">{message}</p>;
}
```

- [ ] **Step 7: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/form/chrome
git commit -m "$(cat <<'EOF'
feat(frontend): shared chrome components for form fields

6 small components in components/form/chrome/ that every primitive
field renderer in T6-T11 will consume:

- FieldRow:       vertical-spacing wrapper
- FieldHeader:    label + type badge + required pill row
- TypeBadge:      monospace pill summarising kind + constraints
                  (e.g., "int · ≥1 · ≤64", "str · 3..32", "HttpUrl")
- RequiredBadge:  amber "required" pill for fields without defaults
- Description:    muted helper text from Field(description=...)
- FieldError:     red helper text under the input; null-safe

All Tailwind utility classes; no shadcn primitive imports (those land
in the field components themselves).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: StringField

**Files:**
- Create: `frontend/src/components/form/fields/StringField.tsx`

- [ ] **Step 1: Write the component**

`frontend/src/components/form/fields/StringField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { StringNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type StringNode = z.infer<typeof StringNodeSchema>;

export function StringField({ node, path }: { node: StringNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

  // Re-sync local state when the server pushes a new tree (after a
  // successful mutation OR an external refetch). Without this, edits
  // by other tabs / mutations elsewhere wouldn't surface here.
  useEffect(() => {
    setLocal(node.value ?? "");
    setError(node.error);
  }, [node.value, node.error]);

  return (
    <FieldRow>
      <FieldHeader>
        <Label htmlFor={`field-${path}`} className="text-sm font-medium">
          {node.name}
        </Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        value={local}
        type={node.secret ? "password" : "text"}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;   // no-op
          mutation.mutate(
            { op: "set_value", path, value: local },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/form/fields/StringField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): StringField - text input with on-blur mutation

Renders a shadcn Input wrapped in the chrome layer from T5. Local
state for the input; useEffect re-syncs from node.value when the
server pushes a new tree. On blur, if the value changed, POSTs a
set_value mutation; on error, sets the local error state for the
FieldError pill.

The secret flag toggles type="password" - this is the v0.2 path for
SecretStr fields that pretty-print as ********** in the YAML
preview.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: IntField

**Files:**
- Create: `frontend/src/components/form/fields/IntField.tsx`

- [ ] **Step 1: Write the component**

`frontend/src/components/form/fields/IntField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { IntNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type IntNode = z.infer<typeof IntNodeSchema>;

export function IntField({ node, path }: { node: IntNode; path: string }) {
  const mutation = useApplyMutation();
  const initial = node.value !== null ? String(node.value) : "";
  const [local, setLocal] = useState<string>(initial);
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value !== null ? String(node.value) : "");
    setError(node.error);
  }, [node.value, node.error]);

  return (
    <FieldRow>
      <FieldHeader>
        <Label htmlFor={`field-${path}`} className="text-sm font-medium">
          {node.name}
        </Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="number"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === initial) return;
          // Local parse for the obvious "not a number" case.
          // The server still does authoritative validation
          // (range / multiple_of / etc.) and may reject.
          const parsed = local.trim() === "" ? null : Number(local);
          if (parsed !== null && Number.isNaN(parsed)) {
            setError(`'${local}' is not a number`);
            return;
          }
          mutation.mutate(
            { op: "set_value", path, value: parsed },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/form/fields/IntField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): IntField - number input with parse-then-mutate

Same chrome + local-state pattern as StringField. type="number"
gives the browser a numeric input affordance; client-side parse
catches "not a number" early without a server round-trip. Constraint
violations (ge/le/multiple_of) still get caught by the server's
validate-first contract and surface as a FieldError on the
mutation's onError callback.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: BoolField

**Files:**
- Create: `frontend/src/components/form/fields/BoolField.tsx`

- [ ] **Step 1: Write the component**

`frontend/src/components/form/fields/BoolField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { BoolNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

type BoolNode = z.infer<typeof BoolNodeSchema>;

export function BoolField({ node, path }: { node: BoolNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<boolean>(node.value ?? false);
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value ?? false);
    setError(node.error);
  }, [node.value, node.error]);

  return (
    <FieldRow>
      <FieldHeader>
        <Label htmlFor={`field-${path}`} className="text-sm font-medium">
          {node.name}
        </Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <div className="pt-1">
        <Switch
          id={`field-${path}`}
          name={node.name}
          checked={local}
          onCheckedChange={(checked: boolean) => {
            setLocal(checked);
            // Switches mutate immediately (no blur for a checkbox)
            mutation.mutate(
              { op: "set_value", path, value: checked },
              { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
            );
          }}
        />
      </div>
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/form/fields/BoolField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): BoolField - shadcn Switch with immediate mutation

Unlike StringField / IntField (which wait for blur to commit), a
switch commits the new value the moment the user toggles - there's
no concept of "still typing". Local state updates optimistically; if
the server rejects (rare for a bool), the next refetch (or the
useEffect re-sync) flips it back.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: EnumField

**Files:**
- Create: `frontend/src/components/form/fields/EnumField.tsx`

- [ ] **Step 1: Write the component**

`frontend/src/components/form/fields/EnumField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { EnumNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type EnumNode = z.infer<typeof EnumNodeSchema>;

// EnumNode.value is the enum member instance; the API serializes it
// as either the enum's NAME (e.g., "INFO") or its raw VALUE (e.g.,
// "info" for a string enum). The choices array is
// [(name, member), ...]. We use the NAME as the canonical wire key.

function currentName(node: EnumNode): string {
  // value may be undefined / null / serialized as either name or value
  if (node.value === null || node.value === undefined) return "";
  const valStr = String(node.value);
  // Find the choice whose name OR whose serialized member matches
  for (const [name, member] of node.choices) {
    if (name === valStr) return name;
    if (String(member) === valStr) return name;
  }
  return valStr;   // fallback - displays as-is
}

export function EnumField({ node, path }: { node: EnumNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(currentName(node));
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(currentName(node));
    setError(node.error);
  }, [node.value, node.error, node.choices]);

  return (
    <FieldRow>
      <FieldHeader>
        <Label htmlFor={`field-${path}`} className="text-sm font-medium">
          {node.name}
        </Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Select
        value={local}
        onValueChange={(name) => {
          setLocal(name);
          mutation.mutate(
            { op: "set_value", path, value: name },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      >
        <SelectTrigger id={`field-${path}`} name={node.name}>
          <SelectValue placeholder="Select..." />
        </SelectTrigger>
        <SelectContent>
          {node.choices.map(([name]) => (
            <SelectItem key={name} value={name}>{name}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/form/fields/EnumField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): EnumField - shadcn Select over node.choices

EnumNode.value is the enum member instance, serialized via Pydantic's
mode='python' default into either the member's NAME or its raw value
(depending on whether the enum is a str-enum). The component normalises
by looking up the matching name from the choices array - this keeps
the wire format predictable regardless of which Pydantic serializes.

Selection commits immediately (no blur - the user has already
committed to a choice by clicking).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: LiteralField

**Files:**
- Create: `frontend/src/components/form/fields/LiteralField.tsx`

- [ ] **Step 1: Write the component**

`frontend/src/components/form/fields/LiteralField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { LiteralNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type LiteralNode = z.infer<typeof LiteralNodeSchema>;

export function LiteralField({ node, path }: { node: LiteralNode; path: string }) {
  const mutation = useApplyMutation();
  const currentStr = node.value === null || node.value === undefined ? "" : String(node.value);
  const [local, setLocal] = useState<string>(currentStr);
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value === null || node.value === undefined ? "" : String(node.value));
    setError(node.error);
  }, [node.value, node.error]);

  return (
    <FieldRow>
      <FieldHeader>
        <Label htmlFor={`field-${path}`} className="text-sm font-medium">
          {node.name}
        </Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Select
        value={local}
        onValueChange={(picked) => {
          setLocal(picked);
          // Send the raw choice value; the server matches against the
          // original literal choices via __eq__.
          const matchedChoice = node.choices.find((c) => String(c) === picked);
          const valueToSend = matchedChoice ?? picked;
          mutation.mutate(
            { op: "set_value", path, value: valueToSend },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      >
        <SelectTrigger id={`field-${path}`} name={node.name}>
          <SelectValue placeholder="Select..." />
        </SelectTrigger>
        <SelectContent>
          {node.choices.map((choice) => {
            const str = String(choice);
            return <SelectItem key={str} value={str}>{str}</SelectItem>;
          })}
        </SelectContent>
      </Select>
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/form/fields/LiteralField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): LiteralField - shadcn Select over node.choices

LiteralNode.choices is just a list of raw values (Literal['a', 'b', 'c']
becomes choices=['a','b','c']). Render each as a SelectItem; on
change, find the matching choice (preserves the original type if it
wasn't a string) and send it via set_value.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: GroupField (minimal)

**Files:**
- Create: `frontend/src/components/form/fields/GroupField.tsx`

- [ ] **Step 1: Write the component**

`frontend/src/components/form/fields/GroupField.tsx`:

```typescript
// Minimal GroupField for Phase 3: just iterates child fields. No
// collapsible chrome, no nested-card visual treatment - those land
// in Phase 4 when sequence/mapping/union containers raise the bar
// for what "nested" looks like. The interface (props.node, props.path)
// is the long-term contract.

import type { GroupNodeData } from "@/api/schemas";
import { FormField } from "@/components/form/FormField";

export function GroupField({ node, path }: { node: GroupNodeData; path: string }) {
  return (
    <div className="space-y-6">
      {node.fields.map((child) => (
        <FormField
          key={child.name}
          node={child}
          path={path ? `${path}.${child.name}` : child.name}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: failure — `FormField` is defined in T12. Continue to T12 immediately.

(If you're running tasks strictly TDD-style and need the typecheck to pass at every commit, swap T11 and T12. The plan orders T11 first because GroupField is conceptually simpler.)

- [ ] **Step 3: Commit anyway (T12 will land moments later)**

```bash
git add frontend/src/components/form/fields/GroupField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): GroupField - minimal iterator over child fields

Phase 3 GroupField is a 12-line wrapper that maps each child node
through FormField (the dispatcher, landing in T12). No chrome, no
collapse, no schema_class display - Phase 4 adds those when nested
containers force the visual treatment.

The interface (props.node, props.path) is the long-term contract;
Phase 4 only changes the body.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: FormField dispatcher

**Files:**
- Create: `frontend/src/components/form/FormField.tsx`

- [ ] **Step 1: Write the dispatcher**

`frontend/src/components/form/FormField.tsx`:

```typescript
// Dispatcher: switch on node.kind to render the right component.
// Phase 3 covers 6 kinds (string/int/bool/enum/literal/group);
// Phase 4 adds sequence/mapping/union/any and the remaining 14 kinds
// from src/pydantic_studio/tree/nodes.py.
//
// Unknown kinds (anything not yet wired) render as a small "TODO"
// placeholder so the rest of the form still renders during incremental
// build-out.

import type { FormNodeData } from "@/api/schemas";
import { BoolField } from "@/components/form/fields/BoolField";
import { EnumField } from "@/components/form/fields/EnumField";
import { GroupField } from "@/components/form/fields/GroupField";
import { IntField } from "@/components/form/fields/IntField";
import { LiteralField } from "@/components/form/fields/LiteralField";
import { StringField } from "@/components/form/fields/StringField";

export function FormField({ node, path }: { node: FormNodeData; path: string }) {
  switch (node.kind) {
    case "string":
      return <StringField node={node} path={path} />;
    case "int":
      return <IntField node={node} path={path} />;
    case "bool":
      return <BoolField node={node} path={path} />;
    case "enum":
      return <EnumField node={node} path={path} />;
    case "literal":
      return <LiteralField node={node} path={path} />;
    case "group":
      return <GroupField node={node} path={path} />;
    default:
      return (
        <div className="rounded border border-dashed border-zinc-300 p-2 text-xs text-zinc-500">
          <strong className="font-mono">{node.name}</strong>: kind <code className="font-mono">{node.kind}</code> not yet wired (Phase 4+).
        </div>
      );
  }
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0. Both GroupField (T11) and FormField now resolve their cross-imports.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/form/FormField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): FormField dispatcher - 6 primitive kinds + unknown fallback

Switches on node.kind to render the right component. Phase 3 wires
string / int / bool / enum / literal / group. Unknown kinds (the 14
others from tree/nodes.py - sequence, mapping, union, any, date,
datetime, uuid, ip_address, url, email, secret, path, bytes, pattern,
decimal, float, timedelta, time, ip_network) render as a dashed-border
"not yet wired" placeholder so a real schema with mixed kinds still
mostly displays during incremental build-out.

Phase 4 replaces the fallback branches one-by-one as container
components arrive.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Update App.tsx with form + preview

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Rewrite App.tsx**

Replace `frontend/src/App.tsx`:

```typescript
import { useQuery } from "@tanstack/react-query";

import { fetchTree } from "@/api/tree";
import { FormField } from "@/components/form/FormField";

export default function App() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tree"],
    queryFn: fetchTree,
  });

  if (isLoading) {
    return <div className="p-8 text-zinc-500">Loading tree...</div>;
  }
  if (error || !data) {
    return (
      <div className="p-8 text-red-600">
        Failed to load tree:{" "}
        {error instanceof Error ? error.message : String(error)}
      </div>
    );
  }

  const schemaName = data.schema_name.includes(":")
    ? data.schema_name.split(":")[1]
    : data.schema_name;

  return (
    <div className="grid grid-cols-2 gap-8 p-8 font-sans min-h-screen bg-white">
      <section className="space-y-6">
        <header>
          <h1 className="text-2xl font-semibold">{schemaName}</h1>
          <p className="text-xs text-zinc-500 mt-1">{data.schema_name}</p>
        </header>
        <FormField node={data.root} path="" />
      </section>
      <section className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Live preview
        </h2>
        <pre
          data-testid="tree-preview"
          className="bg-zinc-100 p-4 rounded text-xs overflow-auto max-h-[80vh]"
        >
          {JSON.stringify(data, null, 2)}
        </pre>
      </section>
    </div>
  );
}
```

The `data-testid="tree-preview"` attribute is what the Playwright test in T16 will target to assert the preview updates after a mutation.

- [ ] **Step 2: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): App.tsx - 2-column layout, form on left + live preview on right

Replaces Phase 2's bare JSON dump with the actual form (left
column - delegates to FormField for the root group) alongside a
preview pane (right column - keeps the raw JSON dump as the v0.2
'preview' until Phase 5's YAML tab replaces it). The preview pane
has a data-testid='tree-preview' for Playwright assertions.

Schema name is parsed from 'module:Class' into just the class name
for the heading; the full path stays as a muted subtitle for context.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Rebuild + commit dist/ + add base-path verification test

**Files:**
- Modify: `src/pydantic_studio/renderers/html/static/dist/index.html` (rebuilt)
- Modify: `src/pydantic_studio/renderers/html/static/dist/assets/*.{js,css}` (rebuilt, new hashes)
- Modify: `tests/unit/test_html_static_bundle.py` (add a test that root-relative `/static/dist/assets/...` matches the HTML's references)

- [ ] **Step 1: Rebuild with the new base + new components**

```bash
cd frontend
pnpm build
```

Expected: Vite builds and writes to `../src/pydantic_studio/renderers/html/static/dist/`. The built `index.html` now references `/static/dist/assets/<hash>.js` (instead of `/assets/<hash>.js`) because of T1's base-path fix.

Bundle size will grow from ~60 KB gzip (Phase 2 empty) to roughly 90-130 KB gzip (Phase 3 with shadcn primitives + Radix UI). Should still be well under the 250 KB spec budget.

- [ ] **Step 2: Spot-check the built HTML**

```bash
cd ..
cat src/pydantic_studio/renderers/html/static/dist/index.html
```

Expected: `<script type="module" src="/static/dist/assets/index-<hash>.js">` (note the `/static/dist/` prefix — that's the base fix from T1 working). Without the base fix it'd be `<script src="/assets/...">`.

- [ ] **Step 3: Add the new test asserting both paths resolve**

Append to `tests/unit/test_html_static_bundle.py`:

```python
def test_static_dist_asset_uses_static_prefixed_path() -> None:
    """After Phase 3's base-path fix, the built index.html should
    reference assets with the /static/dist/ prefix - meaning a browser
    loading /static/dist/index.html will fetch /static/dist/assets/<hash>.js
    (which the existing static mount serves), not the previously-stale
    root-relative /assets/<hash>.js.
    """
    tree = build_form_tree(_Demo)
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app)

    html = client.get("/static/dist/index.html").text
    # New requirement: asset URLs include /static/dist/ prefix.
    import re

    js_match = re.search(r'/static/dist/assets/[A-Za-z0-9_-]+\.js', html)
    assert js_match is not None, (
        f"built index.html should reference /static/dist/assets/*.js "
        f"after Phase 3's base-path fix (vite.config.ts base='/static/dist/'); "
        f"current HTML:\n{html}"
    )

    # And that URL is reachable as-is (no path-rewriting needed).
    response = client.get(js_match.group(0))
    assert response.status_code == 200
    assert len(response.content) > 1000
```

- [ ] **Step 4: Run the smoke tests**

```bash
uv run python -m pytest tests/unit/test_html_static_bundle.py -q
```

Expected: 3 passed (the 2 original tests + 1 new one).

The original `test_static_dist_assets_are_served` may now also pass with the root-relative path matching the spec — verify the regex it uses still matches. If it now scrapes `/static/dist/assets/...` correctly (no longer `/assets/...`), the assertion that `/static/dist{js_path}` resolves becomes `/static/dist/static/dist/assets/...` which would 404. If this fails, update the original test to use `js_path` directly (without the `/static/dist` prefix) since the path is now already absolute via the static mount:

```python
    # Old (Phase 2): root-relative path needed /static/dist prefix
    # mounted_path = f"/static/dist{js_path}"
    # New (Phase 3): the path is already mount-rooted
    mounted_path = js_path
    response = client.get(mounted_path)
```

- [ ] **Step 5: Commit (bundle + test updates)**

```bash
git add src/pydantic_studio/renderers/html/static/dist \
  tests/unit/test_html_static_bundle.py
git commit -m "$(cat <<'EOF'
build(frontend): rebuild bundle with base-path fix + form components

Three coupled changes:

(1) Vite bundle rebuilt with the Phase 3 form components (FormField
    dispatcher + 5 primitive renderers + GroupField + chrome). The
    base='/static/dist/' setting (from T1) means the built index.html
    now references /static/dist/assets/<hash>.js (NOT root-relative
    /assets/<hash>.js as in Phase 2), so a browser loading the
    page via FastAPI's static mount can fetch the bundle.

(2) New test test_static_dist_asset_uses_static_prefixed_path asserts
    the rewritten asset path actually appears in the built HTML and
    is reachable as-is.

(3) test_static_dist_assets_are_served updated: the scraped path no
    longer needs the /static/dist prefix tacked on, since the new
    base-path bakes it in already.

Bundle grows from ~60 KB gzip (Phase 2 empty) to ~120 KB (Phase 3
with shadcn primitives + Radix UI); well under the spec's 250 KB
budget.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Install pytest-playwright + Chromium

**Files:**
- Modify: `pyproject.toml` (add pytest-playwright to dev group)
- Modify: `uv.lock` (auto-updated)

- [ ] **Step 1: Add pytest-playwright to the dev group**

Read `pyproject.toml`. Find the `[dependency-groups]` section. Add `pytest-playwright` to the `dev` group:

```toml
[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "pytest-cov",
  "pytest-playwright>=0.5",
  "email-validator>=2",
  "mkdocs-material>=9.5",
  "mkdocstrings[python]>=0.27",
]
```

- [ ] **Step 2: Sync the new dep**

```bash
uv sync
```

Expected: pytest-playwright + playwright deps installed. Lockfile updated.

- [ ] **Step 3: Install Chromium browser binary**

```bash
uv run playwright install chromium
```

Expected: downloads ~150 MB Chromium binary to `~/.cache/ms-playwright/` (cross-platform; Windows uses `%LOCALAPPDATA%\ms-playwright`). Subsequent installs are cached.

If the download fails (network / corporate proxy), STOP and report DONE_WITH_CONCERNS — the e2e test in T16 needs Chromium to run.

- [ ] **Step 4: Confirm pytest discovers the playwright plugin**

```bash
uv run pytest --version
```

Expected: prints pytest version AND lists "plugins:" including `playwright`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "$(cat <<'EOF'
chore(deps): add pytest-playwright for Phase 3 e2e test

Adds pytest-playwright to the dev group so e2e tests can drive a
real Chromium against a real FastAPI process. Browser binaries are
NOT shipped via pip - contributors run 'uv run playwright install
chromium' once locally; CI will need the same step (handled in a
future CI-setup follow-up, per spec §7.4).

Lockfile updated.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: First Playwright e2e test

**Files:**
- Create: `tests/e2e/__init__.py` (empty marker)
- Create: `tests/e2e/conftest.py` (FastAPI fixture)
- Create: `tests/e2e/test_spa_edit_flow.py` (the test)

- [ ] **Step 1: Empty package marker**

`tests/e2e/__init__.py`:

```python
```

(Empty file. Just makes pytest discover the directory.)

- [ ] **Step 2: Write the FastAPI fixture**

`tests/e2e/conftest.py`:

```python
"""Shared fixtures for the Playwright e2e tests: spin up uvicorn on a
fixed port with a known schema so the SPA has something to render +
mutate.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import closing
from typing import Iterator

import pytest
import uvicorn
from pydantic import BaseModel, Field

from pydantic_studio import StudioServer, build_form_tree


class _DemoSchema(BaseModel):
    """Schema the e2e tests drive. Edit cautiously - test assertions
    pin specific field names and values."""

    name: str = Field(default="demo-service", description="Service identifier")
    workers: int = Field(default=4, ge=1, le=64, description="Worker count")
    debug: bool = Field(default=False, description="Verbose logging")


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def fastapi_url() -> Iterator[str]:
    """Spin up uvicorn on a free port in a background thread.

    Each test gets the same server (session-scoped) - tests that mutate
    state are responsible for either resetting it or using values that
    don't collide.
    """
    port = _find_free_port()
    tree = build_form_tree(_DemoSchema)
    server = StudioServer(tree=tree, save_path=None)
    config = uvicorn.Config(
        server.app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    uvi = uvicorn.Server(config)
    thread = threading.Thread(target=uvi.run, daemon=True)
    thread.start()

    # Wait for the server to bind. Cap at ~5s.
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            with closing(socket.create_connection(("127.0.0.1", port), timeout=0.2)):
                break
        except OSError:
            time.sleep(0.05)
    else:
        raise RuntimeError(f"uvicorn never bound to :{port}")

    yield f"http://127.0.0.1:{port}"

    uvi.should_exit = True
    thread.join(timeout=2.0)
```

- [ ] **Step 3: Write the e2e test**

`tests/e2e/test_spa_edit_flow.py`:

```python
"""End-to-end test: load the SPA, edit a string field, assert both
the server-side tree AND the in-page preview update.

Per spec §8 Phase 3 acceptance: 'Playwright test: load schema, edit
one field, see preview update.'
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_edit_string_field_updates_tree_and_preview(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")

    # Wait for React to mount the form. The 'name' input is the first
    # primitive field in _DemoSchema (see conftest.py).
    name_input = page.get_by_label("name", exact=True)
    expect(name_input).to_be_visible(timeout=5000)
    expect(name_input).to_have_value("demo-service")

    # Edit the field. fill() replaces the entire value, blur() commits
    # via the on-blur mutation in StringField.
    name_input.fill("edited-via-playwright")
    name_input.blur()

    # The preview pane should reflect the new value once the mutation
    # round-trips. Wait for it to update.
    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text("edited-via-playwright", timeout=5000)

    # And the server-side tree, fetched directly (bypassing the SPA),
    # should also show the new value.
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    assert response.status == 200
    body = response.json()
    name_field = next(
        f for f in body["root"]["fields"] if f["name"] == "name"
    )
    assert name_field["value"] == "edited-via-playwright"
```

- [ ] **Step 4: Run the e2e test**

```bash
uv run python -m pytest tests/e2e -q
```

Expected: 1 passed. The test:
1. Opens the FastAPI URL in headless Chromium
2. Waits for the React SPA to mount
3. Edits the `name` field
4. Asserts the preview pane text updated
5. Asserts the server's `/api/tree` also reflects the new value

If the test fails:
- `Timeout waiting for input[aria-label="name"]` → the SPA didn't render. Check that the bundle is rebuilt (T14) AND served from `/static/dist/`.
- `expect(preview).to_contain_text` fails → the mutation didn't round-trip. Check the browser console (via Playwright's page.on("console")) for fetch errors.
- `fastapi_url` fixture errors out → the FastAPI process didn't start. Check uvicorn's stderr (currently suppressed via log_level="warning"; for debugging, set log_level="debug").

- [ ] **Step 5: Commit**

```bash
git add tests/e2e
git commit -m "$(cat <<'EOF'
test(e2e): Playwright - edit a string field, assert tree + preview update

First Phase 3 e2e test (per spec §8 acceptance). conftest.py
session-scopes a uvicorn process on a free port serving a known
_DemoSchema. The test:

1. Opens /static/dist/index.html (headless Chromium)
2. Waits for the React SPA to mount the 'name' field
3. fills the field with 'edited-via-playwright' and blurs
4. Asserts the preview <pre> reflects the new value
5. Independently fetches /api/tree and asserts the server tree also
   reflects the value (defence against the SPA showing stale-cache
   data while the server is out of sync)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: Full-suite verify + handoff

**Files:**
- Run-only; no edits unless something breaks.

- [ ] **Step 1: Run the full Python test suite (skip docs trampoline + e2e if Chromium missing)**

```bash
uv run python -m pytest tests/ -q --deselect tests/unit/test_docs_build.py
```

Expected: 502 passed (501 from Phase 2 baseline + 1 from T16) + 1 deselected (test_docs_build). If T14's new test landed, it's 503 passed.

If any HTML server test, JSON API test, or serializer test fails, the new bundle or base-path change may have broken something — investigate before commit.

- [ ] **Step 2: Ruff lint the touched Python files**

```bash
uv run ruff check tests/unit/test_html_static_bundle.py tests/e2e
```

Expected: All checks passed.

- [ ] **Step 3: Confirm the frontend typecheck is clean**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Sanity-check the dev-loop docs**

Re-read README's "Frontend development" section. Confirm that:
- The dev-backend.py command still works (it was added in Phase 2)
- The pnpm dev URL is still :5173
- The "refresh the committed bundle" command is `pnpm build` (or `frontend/scripts/build.sh`)

No README changes needed unless the dev loop materially changed (it didn't — Phase 3 only added components, no toolchain changes).

- [ ] **Step 5: Phase 3 done — handoff note**

Phase 3 ships:
- 6 form components (StringField / IntField / BoolField / EnumField / LiteralField / GroupField-minimal) consuming 5 shadcn primitives + 6 shared chrome components
- `useApplyMutation` hook + zod-typed `fetchTree`
- App.tsx 2-column layout (form + live preview JSON dump)
- Vite base-path fix → SPA actually executes in-browser via FastAPI's static mount
- 1 Playwright e2e test confirming the edit→mutate→re-render loop works
- Rebuilt bundle (~120 KB gzip; well under 250 KB budget)

Known gaps (deferred to later phases per spec):
- Container fields (sequence / mapping / union / any) — Phase 4
- The 14 other primitive kinds (date / datetime / time / timedelta / uuid / ip_address / ip_network / url / email / secret / path / bytes / pattern / decimal / float) — Phase 4
- Validation surface (red border on invalid input, errors tab) — Phase 5
- Type badges showing constraints for non-int/non-str kinds — Phase 5
- Theme toggle, sidebar search — Phase 5
- Vitest unit tests for each component — Phase 5 polish (Playwright + TS strict is enough coverage for Phase 3)
- CI guard for stale bundles — separate follow-up before Phase 3+ source changes routinely outpace bundle commits

Recommended branch name: `feature/shadcn-redesign-phase-3-primitive-renderers`; merge with `--no-ff` per the codebase convention; tag the feature tip as `v0.2.0-phase-3` before merging.

---

## Self-review checklist (already applied)

- ✅ **Spec §8 Phase 3 ("FormField dispatcher + 5 primitive renderers + wire mutations + Playwright")**: Tasks 4 (mutations), 5 (chrome), 6-10 (5 primitives), 11 (group), 12 (dispatcher), 13 (App update), 15-16 (Playwright). All covered.
- ✅ **Spec §6.1 dispatcher signature**: T12's FormField switch matches the spec example. Unknown-kind fallback is an addition (graceful degradation during incremental build-out).
- ✅ **Spec §6.2 shared field chrome**: T5 covers FieldRow / FieldHeader / Label / TypeBadge / Description / FieldError (RequiredBadge added — used by spec §6.2 example).
- ✅ **Spec §3.1 server-authoritative state**: T4's useApplyMutation calls `setQueryData(['tree'], response.tree)` on success — exactly the spec's model. No optimistic updates.
- ✅ **Spec §5.2 envelope shape**: T4's MutationResponse type matches `{tree, validation, mutation_result}`.
- ✅ **Spec §9.2 testing**: Vitest deliberately skipped (TS strict + Playwright covers Phase 3 needs; Vitest is Phase 5 polish per "Frontend tests added incrementally" note in spec §8 phase 5). Playwright matches the §9.2 description ("spin up run_html_app(tree) in a fixture, drive the browser through edit/save/cancel flows").
- ✅ **No placeholders**: every step has exact code or commands. No "TBD", no "add appropriate handling".
- ✅ **Type consistency**: `FormNodeData`, `FormTree`, `Mutation`, `MutationResponse` are used consistently across T3, T4, T6-T12. File paths under `frontend/src/...` are consistent.
- ✅ **Bundle commit ordering**: T14 rebuilds AFTER T1 (base fix) AND T6-T13 (component changes); the Phase 2 ordering bug (T7→T8) is not repeated.
- ✅ **Frontend test runner choice (pytest-playwright)**: aligns with spec §9.2's "spin up run_html_app(tree) in a fixture" phrasing (Python fixture); avoids the JS/Python interop awkwardness of `@playwright/test`.
- ✅ **YAGNI**: no useFieldValue hook (inlined state per component — 4 lines × 5 components beats a 30-line hook); no Vitest; no router; no theme; no full TypeBadge for every kind (only int/str polished for Phase 3 — others render with just kind name).
- ✅ **Frequent commits**: 17 task-aligned commits, each a logical unit. Mirrors Phase 1 / Phase 2 cadence.
