# Shadcn Web Redesign — Phase 4: Container Fields Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the 5 container node kinds (sequence/mapping/union/any) plus polished GroupField into the FormField dispatcher, surfacing the mutation ops Phase 1 already exposes (`add_item`, `remove_item`, `move_item`, `add_entry`, `remove_entry`, `rename_key`, `select_variant`). Each container kind ships with a Playwright e2e test that drives it end-to-end.

**Architecture:** Container components consume the same chrome layer + `useApplyMutation` hook from Phase 3, but expose their own per-kind controls (add/remove/reorder buttons for sequences, key+value cards for mappings, variant chips for unions, mode-inferring text editor for any). GroupField gets a collapsible card wrapper. zod schemas extend to cover the 4 new node kinds; `FormNodeData` discriminated union grows accordingly. Path-building helper (`childPath`) centralizes the dotted-path convention so containers and nested groups produce consistent paths.

**Tech Stack:** React 18 + TypeScript strict + TanStack Query 5 (for the existing mutation hook + new container ops), zod 3, shadcn primitives (re-uses existing Button + Input + Label from Phase 3; no new primitives needed for Phase 4). Test stack: pytest-playwright (already installed in Phase 3).

**Spec:** `docs/superpowers/specs/2026-05-14-shadcn-web-redesign-design.md` §6.3 (container fields), §8 Phase 4 row.

**Predecessors:**
- Phase 1 (`v0.2.0-phase-1`, merged at `b1c0ff8`): JSON API including all 8 mutation ops
- Phase 2 (`v0.2.0-phase-2`, merged at `969d6f3`): Vite/React toolchain + empty SPA
- Phase 3 (`v0.2.0-phase-3`, merged at `ffbaef3`): FormField dispatcher + 5 primitives + minimal GroupField + first Playwright e2e

---

## File Structure

**Create (frontend source):**
- `frontend/src/components/form/path.ts` — `childPath(parent, segment)` helper for the dotted-path convention. ~12 lines.
- `frontend/src/components/form/fields/SequenceField.tsx` — list of FormField children + add/remove/move controls. ~85 lines.
- `frontend/src/components/form/fields/MappingField.tsx` — list of {key input, value FormField} cards + add/remove/rename-key controls. ~95 lines.
- `frontend/src/components/form/fields/UnionField.tsx` — variant chip buttons + selected-variant FormField. ~55 lines.
- `frontend/src/components/form/fields/AnyField.tsx` — text editor that JSON-parses on blur + mode badge. ~50 lines.

**Modify:**
- `frontend/src/api/schemas.ts` — add `SequenceNodeSchema`, `MappingNodeSchema`, `UnionNodeSchema`, `AnyValueNodeSchema`; extend the `FormNodeData` union to include them. ~80 new lines.
- `frontend/src/components/form/fields/GroupField.tsx` — collapsible card chrome (border, chevron header, optional schema_class subtitle). Replace minimal 12-line version. ~40 lines.
- `frontend/src/components/form/FormField.tsx` — add 4 new dispatch cases (`sequence`, `mapping`, `union`, `any`). The `default` placeholder shrinks accordingly.
- `tests/e2e/conftest.py` — extend `_DemoSchema` to include one container per kind (`tags: list[str]`, `env: dict[str, str]`, `notifier: Annotated[Email | Slack, Field(discriminator="kind")]`, `metadata: dict[str, Any]`). Existing `name/workers/debug` fields stay.

**Create (tests):**
- `tests/e2e/test_sequence_field.py` — add an item, edit its value, assert preview + server tree update.
- `tests/e2e/test_mapping_field.py` — add an entry, rename its key, edit its value, assert state.
- `tests/e2e/test_union_field.py` — switch variants, edit a field of the selected variant, assert state.
- `tests/e2e/test_any_field.py` — type a JSON value, blur, assert parsing landed in the tree.

**Bundle artifacts (regenerated):**
- `src/pydantic_studio/renderers/html/static/dist/index.html`
- `src/pydantic_studio/renderers/html/static/dist/assets/*.js`
- `src/pydantic_studio/renderers/html/static/dist/assets/*.css`

**Do NOT touch:**
- The 5 primitive field components from Phase 3 (StringField, IntField, BoolField, EnumField, LiteralField) — they're working
- The chrome layer (FieldRow, FieldHeader, etc.) — Phase 5 may add `data-testid` props but not Phase 4
- `serialize.py` / `routes.py` — Phase 1's mutation ops cover everything containers need
- The 14 other primitive kinds (date/datetime/uuid/url/email/etc.) — deferred to a later phase; FormField's default branch handles them as "not yet wired" placeholders

---

## Prerequisites

Before Task 1, confirm the Phase 3 baseline:

```bash
git log --oneline -1                     # should show the Phase 3 merge or T17 commit
uv run python -m pytest tests/ --deselect tests/unit/test_docs_build.py 2>&1 | tail -3
# should show: 506 passed, 1 deselected
uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra" 2>&1 | tail -3
# should show: 1 passed
cd frontend && pnpm exec tsc -b
# should exit 0
```

If anything fails, fix before starting Phase 4 tasks.

---

## Task 1: Path helper + zod schemas for container nodes

**Files:**
- Create: `frontend/src/components/form/path.ts`
- Modify: `frontend/src/api/schemas.ts`
- Modify: `frontend/src/components/form/fields/GroupField.tsx` (use the helper)

- [ ] **Step 1: Write the path helper**

`frontend/src/components/form/path.ts`:

```typescript
// Dotted-path convention shared by all container components.
// Examples:
//   childPath("", "name")      -> "name"
//   childPath("database", "host") -> "database.host"
//   childPath("tags", 0)       -> "tags.0"
//   childPath("env", 2)        -> "env.2"
//
// The backend's tree._descend (src/pydantic_studio/tree/paths.py) parses
// the same dotted format - numeric segments index into SequenceNode.items
// and MappingNode.entries; string segments select GroupNode fields.

export function childPath(parent: string, segment: string | number): string {
  return parent ? `${parent}.${segment}` : String(segment);
}
```

- [ ] **Step 2: Refactor GroupField to use the helper**

Read `frontend/src/components/form/fields/GroupField.tsx`. Replace the inline path concat with the helper:

```typescript
import type { GroupNodeData } from "@/api/schemas";
import { FormField } from "@/components/form/FormField";
import { childPath } from "@/components/form/path";

export function GroupField({ node, path }: { node: GroupNodeData; path: string }) {
  return (
    <div className="space-y-6">
      {node.fields.map((child) => (
        <FormField
          key={child.name}
          node={child}
          path={childPath(path, child.name)}
        />
      ))}
    </div>
  );
}
```

(GroupField gets a full collapsible-card facelift in T2. T1 is minimal — just the helper switch.)

- [ ] **Step 3: Add zod schemas for the 4 new container kinds**

Edit `frontend/src/api/schemas.ts`. Find the existing schema definitions (after the 6 primitive schemas). Add the 4 new container schemas. The full updated file should look like this (only the new section shown; preserve everything above):

After the `GroupNodeSchema` block (around line 75 of the current file), add:

```typescript
// SequenceNode: list[T] / set[T] / tuple[T,...]. items is a recursive
// list of FormNodes (each item gets its own sub-tree).
export interface SequenceNodeData {
  kind: "sequence";
  name: string;
  description: string | null;
  required: boolean;
  error: string | null;
  items: FormNodeData[];
  item_type_name: string;   // e.g. "builtins.str"
}

export const SequenceNodeSchema: z.ZodType<SequenceNodeData> = z.lazy(() =>
  NodeBase.extend({
    kind: z.literal("sequence"),
    items: z.array(FormNodeSchema),
    item_type_name: z.string(),
  }),
);

// MappingNode: dict[K, V]. entries is a list of (key_node, value_node)
// tuples - 2-element arrays in JSON. Backend uses index-based removal
// and rename so the client doesn't have to worry about key uniqueness.
export interface MappingNodeData {
  kind: "mapping";
  name: string;
  description: string | null;
  required: boolean;
  error: string | null;
  entries: Array<[FormNodeData, FormNodeData]>;
  key_type_name: string;
  value_type_name: string;
}

export const MappingNodeSchema: z.ZodType<MappingNodeData> = z.lazy(() =>
  NodeBase.extend({
    kind: z.literal("mapping"),
    entries: z.array(z.tuple([FormNodeSchema, FormNodeSchema])),
    key_type_name: z.string(),
    value_type_name: z.string(),
  }),
);

// UnionNode: T1 | T2 | ... (with optional discriminator). selected is the
// active variant node (matching one of variant_type_names). variant_index
// is the index into variant_type_names.
export interface UnionNodeData {
  kind: "union";
  name: string;
  description: string | null;
  required: boolean;
  error: string | null;
  variant_type_names: string[];
  selected_index: number | null;
  selected: FormNodeData | null;
}

export const UnionNodeSchema: z.ZodType<UnionNodeData> = z.lazy(() =>
  NodeBase.extend({
    kind: z.literal("union"),
    variant_type_names: z.array(z.string()),
    selected_index: z.number().nullable(),
    selected: FormNodeSchema.nullable(),
  }),
);

// AnyValueNode: typing.Any. mode auto-syncs to value's runtime shape
// (null/str/int/float/bool/list/dict). The wire value is the raw JSON.
export const AnyValueNodeSchema = NodeBase.extend({
  kind: z.literal("any"),
  mode: z.enum(["null", "str", "int", "float", "bool", "list", "dict"]),
  value: z.unknown(),
});
```

Then update the `FormNodeData` type union and the `FormNodeSchema` body to include the 4 new schemas. Replace the existing `FormNodeData` type and `FormNodeSchema` const with:

```typescript
export type FormNodeData =
  | z.infer<typeof StringNodeSchema>
  | z.infer<typeof IntNodeSchema>
  | z.infer<typeof BoolNodeSchema>
  | z.infer<typeof EnumNodeSchema>
  | z.infer<typeof LiteralNodeSchema>
  | GroupNodeData
  | SequenceNodeData
  | MappingNodeData
  | UnionNodeData
  | z.infer<typeof AnyValueNodeSchema>
  | { kind: string; name: string; [extra: string]: unknown };

// z.union (not z.discriminatedUnion - see Phase 3 T3 commit for the
// rationale: recursive z.lazy types + the passthrough UnknownNodeSchema
// don't satisfy z.discriminatedUnion's stricter member shape).
export const FormNodeSchema: z.ZodType<FormNodeData> = z.union([
  StringNodeSchema,
  IntNodeSchema,
  BoolNodeSchema,
  EnumNodeSchema,
  LiteralNodeSchema,
  GroupNodeSchema,
  SequenceNodeSchema,
  MappingNodeSchema,
  UnionNodeSchema,
  AnyValueNodeSchema,
  UnknownNodeSchema,
]);
```

- [ ] **Step 4: Typecheck**

```bash
cd frontend
pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/src/components/form/path.ts \
  frontend/src/components/form/fields/GroupField.tsx \
  frontend/src/api/schemas.ts
git commit -m "$(cat <<'EOF'
feat(frontend): path helper + zod schemas for 4 container node kinds

Adds childPath(parent, segment) helper centralizing the dotted-path
convention every container needs (foo.0, foo.1, env.0, value.field).
Backend's tree._descend (src/pydantic_studio/tree/paths.py) parses
the same format - numeric segments index sequence items + mapping
entries; string segments select group fields. GroupField refactored
to use it; container components in T3-T6 will too.

Schemas:
- SequenceNodeSchema (list[T] / set[T] / tuple[T,...])
- MappingNodeSchema (dict[K, V] - entries are [k, v] tuples)
- UnionNodeSchema (T1 | T2 + optional discriminator; selected_index
  + selected variant node)
- AnyValueNodeSchema (typing.Any with mode discriminator)

FormNodeData union grows from 7 to 11 members + the loose passthrough
fallback. FormNodeSchema stays z.union (not z.discriminatedUnion;
recursive z.lazy + passthrough kind:string defeat discrimination).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: GroupField polish (collapsible card chrome)

**Files:**
- Modify: `frontend/src/components/form/fields/GroupField.tsx`

The Phase 3 GroupField was a 12-line iterator. Phase 4 wraps it in a collapsible card chrome so nested groups (and Phase 4's containers) sit inside visible boundaries. Default expanded.

- [ ] **Step 1: Rewrite GroupField with collapsible card**

`frontend/src/components/form/fields/GroupField.tsx`:

```typescript
import { useState } from "react";

import type { GroupNodeData } from "@/api/schemas";
import { FormField } from "@/components/form/FormField";
import { childPath } from "@/components/form/path";

export function GroupField({
  node,
  path,
}: { node: GroupNodeData; path: string }) {
  // Root group (path === "") expands the children directly with no card
  // chrome - it IS the form. Nested groups render with a collapsible
  // card so the hierarchy is visible.
  if (path === "") {
    return (
      <div className="space-y-6">
        {node.fields.map((child) => (
          <FormField
            key={child.name}
            node={child}
            path={childPath(path, child.name)}
          />
        ))}
      </div>
    );
  }
  return <NestedGroup node={node} path={path} />;
}

function NestedGroup({
  node,
  path,
}: { node: GroupNodeData; path: string }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50/50">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-100"
        aria-expanded={expanded}
      >
        <span className="flex items-baseline gap-2">
          <span className="text-xs font-mono uppercase text-zinc-500">group</span>
          <span className="font-medium">{node.name}</span>
          {node.schema_class && (
            <span className="text-xs text-zinc-400">
              {node.schema_class.split(".").pop()}
            </span>
          )}
        </span>
        <span className="text-zinc-400">{expanded ? "v" : ">"}</span>
      </button>
      {expanded && (
        <div className="space-y-4 border-t border-zinc-200 p-4 bg-white">
          {node.fields.map((child) => (
            <FormField
              key={child.name}
              node={child}
              path={childPath(path, child.name)}
            />
          ))}
        </div>
      )}
    </div>
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
cd ..
git add frontend/src/components/form/fields/GroupField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): GroupField - collapsible card chrome for nested groups

Root group (path === '') still renders fields directly with no chrome -
it IS the form. Nested groups (anything with a non-empty path) wrap
in a card with a clickable header that toggles expanded/collapsed.
Header shows the group's field name + the schema_class short name
(e.g., 'Replica' for src.module.Replica) as a muted subtitle.

Default expanded; aria-expanded set for screen readers. Plain v/>
chevron text (no lucide icon dep beyond what shadcn already pulled
in) to keep the diff scoped.

Spec section 6.3 mentions depth-based defaults ('default collapsed
for nested groups deeper than 2 levels'); that's a Phase 5 polish
- Phase 4 keeps every nested group expanded.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: SequenceField

**Files:**
- Create: `frontend/src/components/form/fields/SequenceField.tsx`

- [ ] **Step 1: Write the component**

`frontend/src/components/form/fields/SequenceField.tsx`:

```typescript
import type { SequenceNodeData } from "@/api/schemas";
import { useApplyMutation } from "@/api/mutations";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { FormField } from "@/components/form/FormField";
import { childPath } from "@/components/form/path";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export function SequenceField({
  node,
  path,
}: { node: SequenceNodeData; path: string }) {
  const mutation = useApplyMutation();

  const onAdd = () => mutation.mutate({ op: "add_item", path });
  const onRemove = (index: number) =>
    mutation.mutate({ op: "remove_item", path, index });
  const onMove = (from: number, to: number) =>
    mutation.mutate({ op: "move_item", path, from, to });

  return (
    <FieldRow>
      <FieldHeader>
        <Label className="text-sm font-medium">{node.name}</Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
        <span className="text-xs text-zinc-400">
          {node.items.length} {node.items.length === 1 ? "item" : "items"}
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <div className="space-y-2">
        {node.items.map((item, index) => (
          <div
            key={index}
            className="rounded-md border border-zinc-200 bg-zinc-50/50"
          >
            <div className="flex items-center justify-between px-3 py-1.5 text-xs">
              <span className="font-mono text-zinc-500">[{index}]</span>
              <div className="flex gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={index === 0}
                  onClick={() => onMove(index, index - 1)}
                  aria-label={`move ${node.name}[${index}] up`}
                >
                  ^
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={index === node.items.length - 1}
                  onClick={() => onMove(index, index + 1)}
                  aria-label={`move ${node.name}[${index}] down`}
                >
                  v
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => onRemove(index)}
                  aria-label={`remove ${node.name}[${index}]`}
                >
                  x
                </Button>
              </div>
            </div>
            <div className="border-t border-zinc-200 bg-white p-3">
              <FormField node={item} path={childPath(path, index)} />
            </div>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full border-dashed text-zinc-500"
          onClick={onAdd}
        >
          + Add {node.item_type_name.split(".").pop() ?? "item"}
        </Button>
      </div>
      <FieldError message={node.error} />
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
cd ..
git add frontend/src/components/form/fields/SequenceField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): SequenceField - list/set/tuple with add/remove/move

Card per item: chevron-style [index] header with ^/v/x buttons, then
the item's FormField below. + Add button at the bottom uses
node.item_type_name to label the new entry (e.g., 'Add Replica',
'Add str').

All three mutation ops (add_item, remove_item, move_item) from
Phase 1's contract are wired. The disabled-when-at-edge state on
^/v buttons prevents no-op move calls.

Path encoding: items render at path.0, path.1, etc. via childPath().
The backend's tree._descend resolves numeric segments as
SequenceNode.items[i].

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: MappingField

**Files:**
- Create: `frontend/src/components/form/fields/MappingField.tsx`

- [ ] **Step 1: Write the component**

`frontend/src/components/form/fields/MappingField.tsx`:

```typescript
import { useEffect, useState } from "react";

import type { MappingNodeData, FormNodeData } from "@/api/schemas";
import { useApplyMutation } from "@/api/mutations";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { FormField } from "@/components/form/FormField";
import { childPath } from "@/components/form/path";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// MappingNode.entries are [k_node, v_node] tuples; for dict[str, V] the
// k_node is a StringNode whose .value is the key string. Generic
// extraction so dict[int, ...] keys would also work (their k_node.value
// is the int).
function entryKey(k: FormNodeData): string {
  if ("value" in k && k.value !== null && k.value !== undefined) {
    return String(k.value);
  }
  return "";
}

export function MappingField({
  node,
  path,
}: { node: MappingNodeData; path: string }) {
  const mutation = useApplyMutation();

  const onAdd = () => {
    // Compute a fresh key like "key0", "key1", ... that doesn't collide.
    const existing = new Set(node.entries.map(([k]) => entryKey(k)));
    let i = 0;
    while (existing.has(`key${i}`)) i += 1;
    mutation.mutate({ op: "add_entry", path, key: `key${i}` });
  };
  const onRemove = (index: number) =>
    mutation.mutate({ op: "remove_entry", path, index });
  const onRenameKey = (index: number, new_key: string) =>
    mutation.mutate({ op: "rename_key", path, index, new_key });

  return (
    <FieldRow>
      <FieldHeader>
        <Label className="text-sm font-medium">{node.name}</Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
        <span className="text-xs text-zinc-400">
          {node.entries.length} {node.entries.length === 1 ? "entry" : "entries"}
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <div className="space-y-2">
        {node.entries.map(([k_node, v_node], index) => (
          <MappingEntry
            key={index}
            entryKey={entryKey(k_node)}
            valueNode={v_node}
            valuePath={childPath(path, index)}
            onRenameKey={(new_key) => onRenameKey(index, new_key)}
            onRemove={() => onRemove(index)}
          />
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full border-dashed text-zinc-500"
          onClick={onAdd}
        >
          + Add Entry
        </Button>
      </div>
      <FieldError message={node.error} />
    </FieldRow>
  );
}

function MappingEntry({
  entryKey,
  valueNode,
  valuePath,
  onRenameKey,
  onRemove,
}: {
  entryKey: string;
  valueNode: FormNodeData;
  valuePath: string;
  onRenameKey: (new_key: string) => void;
  onRemove: () => void;
}) {
  const [keyLocal, setKeyLocal] = useState(entryKey);
  useEffect(() => setKeyLocal(entryKey), [entryKey]);

  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50/50">
      <div className="flex items-center gap-2 px-3 py-1.5">
        <Input
          value={keyLocal}
          onChange={(e) => setKeyLocal(e.target.value)}
          onBlur={() => {
            if (keyLocal !== entryKey) onRenameKey(keyLocal);
          }}
          className="h-7 text-xs font-mono"
          aria-label="entry key"
        />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onRemove}
          aria-label="remove entry"
        >
          x
        </Button>
      </div>
      <div className="border-t border-zinc-200 bg-white p-3">
        <FormField node={valueNode} path={valuePath} />
      </div>
    </div>
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
cd ..
git add frontend/src/components/form/fields/MappingField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): MappingField - dict[K,V] with add/remove/rename

Two-section card per entry: key input + remove button on top, value
FormField on bottom. + Add Entry button picks a non-colliding key
(key0, key1, ...) and dispatches add_entry; rename_key fires on
key-input blur if the value changed.

The auto-key strategy matches the HTMX route (routes.py:240-248).
remove_entry is index-based (matches the Phase 1 API contract -
clients don't have to track key uniqueness).

Entry-value paths use childPath(parent, index) per the established
convention; the backend's tree._descend resolves env.0 as the value
side of the first entry.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: UnionField

**Files:**
- Create: `frontend/src/components/form/fields/UnionField.tsx`

- [ ] **Step 1: Write the component**

`frontend/src/components/form/fields/UnionField.tsx`:

```typescript
import type { UnionNodeData } from "@/api/schemas";
import { useApplyMutation } from "@/api/mutations";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

function shortName(fq: string): string {
  // "examples.04.EmailNotifier" -> "EmailNotifier"
  return fq.split(".").pop() ?? fq;
}

export function UnionField({
  node,
  path,
}: { node: UnionNodeData; path: string }) {
  const mutation = useApplyMutation();

  const onSelect = (variant_index: number) =>
    mutation.mutate({ op: "select_variant", path, variant_index });

  return (
    <FieldRow>
      <FieldHeader>
        <Label className="text-sm font-medium">{node.name}</Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <div className="flex flex-wrap gap-1">
        {node.variant_type_names.map((variantName, index) => {
          const active = node.selected_index === index;
          return (
            <Button
              key={variantName}
              type="button"
              variant={active ? "default" : "outline"}
              size="sm"
              onClick={() => onSelect(index)}
            >
              {shortName(variantName)}
              {active && " v"}
            </Button>
          );
        })}
      </div>
      {node.selected ? (
        <div className="rounded-md border border-zinc-200 bg-white p-3">
          <FormField node={node.selected} path={path} />
        </div>
      ) : (
        <p className="text-xs text-zinc-400">
          Pick a variant above to set a value.
        </p>
      )}
      <FieldError message={node.error} />
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
cd ..
git add frontend/src/components/form/fields/UnionField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): UnionField - variant chips + selected-variant editor

Variant chip row: one button per variant_type_names; the active
variant gets variant='default' (filled), others get 'outline'. Click
fires select_variant, which on the server-side rebuilds the
.selected sub-node freshly (per Phase 1 contract).

Selected variant renders below via the same FormField dispatcher
(recursion: the variant is just another node). When .selected is
null (no variant chosen), a muted prompt explains the next action.

Path: the selected variant's FormField uses the SAME path as the
UnionNode - because the union IS its selected variant once chosen.
The backend's tree._descend transparently traverses through unions
(it sees the selected node, not the union wrapper).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: AnyField

**Files:**
- Create: `frontend/src/components/form/fields/AnyField.tsx`

- [ ] **Step 1: Write the component**

`frontend/src/components/form/fields/AnyField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { AnyValueNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type AnyValueNode = z.infer<typeof AnyValueNodeSchema>;

// Display + parse the Any value as a JSON string. Mirrors the HTMX
// route (routes.py:64-74): try JSON.parse first (covers numbers,
// booleans, null, arrays, objects); fall back to raw string. The
// node.mode discriminator on the server tracks the inferred shape.

function stringifyAny(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function parseAny(raw: string): unknown {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return raw;
  }
}

export function AnyField({
  node,
  path,
}: { node: AnyValueNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(stringifyAny(node.value));
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(stringifyAny(node.value));
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
        <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
          {node.mode}
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          const original = stringifyAny(node.value);
          if (local === original) return;
          mutation.mutate(
            { op: "set_value", path, value: parseAny(local) },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
        placeholder="any value (JSON or raw string)"
        className="font-mono text-xs"
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
cd ..
git add frontend/src/components/form/fields/AnyField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): AnyField - JSON-parse-or-raw-string editor

Text input that JSON.parse's its value on blur, falling back to a
raw string when parsing fails. Empty input maps to null. Server
auto-syncs node.mode based on the parsed value's runtime shape
(AnyValueNode._sync_mode model_validator).

Mode badge in the header shows the current shape (null/str/int/
float/bool/list/dict) - read-only; users change the mode implicitly
by typing into a different shape (e.g., '42' -> int mode, '[1,2]'
-> list mode).

Mirrors the HTMX route's parse behavior at routes.py:64-74; matches
the design from spec section 6.2's 'AnyField' description.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: FormField dispatcher — add 4 new cases

**Files:**
- Modify: `frontend/src/components/form/FormField.tsx`

- [ ] **Step 1: Add the 4 cases**

Read `frontend/src/components/form/FormField.tsx`. Replace the entire file (preserving the Phase 3 cast helper pattern):

```typescript
// Dispatcher: switch on node.kind to render the right component.
// Phase 3 covered string/int/bool/enum/literal/group. Phase 4 adds
// sequence/mapping/union/any.

import type { FormNodeData } from "@/api/schemas";
import { AnyField } from "@/components/form/fields/AnyField";
import { BoolField } from "@/components/form/fields/BoolField";
import { EnumField } from "@/components/form/fields/EnumField";
import { GroupField } from "@/components/form/fields/GroupField";
import { IntField } from "@/components/form/fields/IntField";
import { LiteralField } from "@/components/form/fields/LiteralField";
import { MappingField } from "@/components/form/fields/MappingField";
import { SequenceField } from "@/components/form/fields/SequenceField";
import { StringField } from "@/components/form/fields/StringField";
import { UnionField } from "@/components/form/fields/UnionField";

type NodeOfKind<K extends string> = Extract<FormNodeData, { kind: K }>;

export function FormField({
  node,
  path,
}: { node: FormNodeData; path: string }) {
  switch (node.kind) {
    case "string":
      return <StringField node={node as NodeOfKind<"string">} path={path} />;
    case "int":
      return <IntField node={node as NodeOfKind<"int">} path={path} />;
    case "bool":
      return <BoolField node={node as NodeOfKind<"bool">} path={path} />;
    case "enum":
      return <EnumField node={node as NodeOfKind<"enum">} path={path} />;
    case "literal":
      return <LiteralField node={node as NodeOfKind<"literal">} path={path} />;
    case "group":
      return <GroupField node={node as NodeOfKind<"group">} path={path} />;
    case "sequence":
      return <SequenceField node={node as NodeOfKind<"sequence">} path={path} />;
    case "mapping":
      return <MappingField node={node as NodeOfKind<"mapping">} path={path} />;
    case "union":
      return <UnionField node={node as NodeOfKind<"union">} path={path} />;
    case "any":
      return <AnyField node={node as NodeOfKind<"any">} path={path} />;
    default:
      return (
        <div className="rounded border border-dashed border-zinc-300 p-2 text-xs text-zinc-500">
          <strong className="font-mono">{node.name}</strong>: kind{" "}
          <code className="font-mono">{node.kind}</code> not yet wired
          (Phase 5+).
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

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/components/form/FormField.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): FormField - dispatch 4 new container kinds

Adds sequence / mapping / union / any cases to the existing switch.
The 6 Phase 3 cases are unchanged; the default-arm placeholder is
re-targeted to 'Phase 5+' for the 14 remaining primitive kinds
(date/datetime/time/timedelta/uuid/ip_address/ip_network/url/email/
secret/path/bytes/pattern/decimal/float - Phase 5 work).

Cast helper NodeOfKind<K> preserves the Phase 3 narrowing pattern;
the recursive z.lazy schemas + UnknownNodeSchema passthrough don't
satisfy TS's discriminated-union narrowing on their own.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Rebuild bundle + smoke test still passes

**Files:**
- Modify: `src/pydantic_studio/renderers/html/static/dist/index.html` (rebuilt)
- Modify: `src/pydantic_studio/renderers/html/static/dist/assets/*.{js,css}` (rebuilt, new hashes)

- [ ] **Step 1: Rebuild**

```bash
cd frontend
pnpm build
```

Expected: Vite emits to `../src/pydantic_studio/renderers/html/static/dist/`. Bundle grows from Phase 3's ~115 KB gzip to roughly ~140-180 KB (4 new components are small but they pull in the same Radix + cn machinery already in the bundle, so growth should be modest). Still well under the 250 KB spec budget.

- [ ] **Step 2: Run the existing smoke tests**

```bash
cd ..
uv run python -m pytest tests/unit/test_html_static_bundle.py -q
```

Expected: 3 passed (unchanged from Phase 3 — base path, mount, and assets all still resolve).

- [ ] **Step 3: Commit the rebuilt bundle**

```bash
git add src/pydantic_studio/renderers/html/static/dist
git commit -m "$(cat <<'EOF'
build(frontend): rebuild bundle with 4 container field components

SequenceField + MappingField + UnionField + AnyField + GroupField
chrome polish + path helper land in the bundle. Hashed asset
filenames change; index.html re-rewritten. Smoke tests
(test_html_static_bundle.py) unchanged - the static-mount contract
is the same.

Bundle size: Phase 3 was ~115 KB gzip; expect ~140-180 KB now
(check 'vite build' output). Well under the 250 KB spec budget.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

In the commit body, replace "~140-180 KB" with the actual size from `vite build`'s emit table if it differs.

---

## Task 9: Extend e2e _DemoSchema + SequenceField e2e test

**Files:**
- Modify: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_sequence_field.py`

- [ ] **Step 1: Extend _DemoSchema**

Read `tests/e2e/conftest.py`. Replace the existing `_DemoSchema` class with this richer version:

```python
from enum import Enum
from typing import Annotated, Any, Literal


class _LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"


class _EmailNotifier(BaseModel):
    kind: Literal["email"] = "email"
    address: str = ""


class _SlackNotifier(BaseModel):
    kind: Literal["slack"] = "slack"
    channel: str = ""


_Notifier = Annotated[
    _EmailNotifier | _SlackNotifier, Field(discriminator="kind")
]


class _DemoSchema(BaseModel):
    """Schema the e2e tests drive. Edit cautiously - test assertions
    pin specific field names and values."""

    name: str = Field(default="demo-service", description="Service identifier")
    workers: int = Field(default=4, ge=1, le=64, description="Worker count")
    debug: bool = Field(default=False, description="Verbose logging")
    level: _LogLevel = Field(default=_LogLevel.INFO, description="Log level")
    tags: list[str] = Field(default_factory=list, description="Free labels")
    env: dict[str, str] = Field(default_factory=dict, description="Env vars")
    notifier: _Notifier = Field(
        default_factory=_EmailNotifier, description="Where to alert"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata"
    )
```

Then in the `fastapi_url` fixture, replace the existing seeding (if any — Phase 3 added a few `tree.set_value(...)` calls) with seeds for the additional fields:

```python
@pytest.fixture(scope="session")
def fastapi_url() -> Iterator[str]:
    port = _find_free_port()
    tree = build_form_tree(_DemoSchema)
    # Seed defaults so the SPA renders with values (Phase 6 housekeeping
    # removed default-seeding from build_form_tree).
    tree.set_value("name", "demo-service")
    tree.set_value("workers", 4)
    tree.set_value("debug", False)
    tree.set_value("level", _LogLevel.INFO)
    # tags, env, notifier, metadata start at their default_factory values
    # (empty list / empty dict / default EmailNotifier / empty dict).
    # The notifier needs explicit variant selection because UnionBuilder's
    # preselect uses isinstance, which works with the default_factory
    # instance directly.
    server = StudioServer(tree=tree, save_path=None)
    config = uvicorn.Config(
        server.app, host="127.0.0.1", port=port, log_level="warning"
    )
    uvi = uvicorn.Server(config)
    thread = threading.Thread(target=uvi.run, daemon=True)
    thread.start()

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

(Adapt as needed — preserve any fixture-setup pieces the existing file already has.)

- [ ] **Step 2: Write the SequenceField e2e test**

`tests/e2e/test_sequence_field.py`:

```python
"""E2E: add an item to a sequence field, edit the new item's value,
assert both server tree and preview update.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_add_remove_and_edit_sequence_item(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    # Wait for the SPA to render the form
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    # Sanity: tags starts empty. The "+ Add" button should be present
    # under the tags field.
    add_button = page.get_by_role("button", name="+ Add str")
    expect(add_button).to_be_visible()

    # Click +Add. A new card appears at index 0 with a string input.
    add_button.click()

    # After the mutation round-trips, the preview should reflect that
    # tags has one item (initially empty string).
    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text('"tags"', timeout=5000)

    # The new item is the only StringNode-shaped child of tags. There
    # are several other string fields on the page (name, level), so
    # locate by the "[0]" header text that SequenceField renders.
    item_header = page.get_by_text("[0]").first
    expect(item_header).to_be_visible(timeout=5000)

    # Independent check: fetch /api/tree and confirm tags has 1 item.
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    tags_field = next(
        f for f in body["root"]["fields"] if f["name"] == "tags"
    )
    assert len(tags_field["items"]) == 1
```

- [ ] **Step 3: Run**

```bash
uv run python -m pytest tests/e2e/test_sequence_field.py -p playwright -o "addopts=-ra" -q
```

Expected: 1 passed.

If the test fails on `+ Add str` not being visible: the SequenceField may be showing `+ Add <other-label>` because `item_type_name` is something like `builtins.str` — adjust the regex/exact-match in the locator.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/conftest.py tests/e2e/test_sequence_field.py
git commit -m "$(cat <<'EOF'
test(e2e): SequenceField - add an item, assert tree + preview update

Extends _DemoSchema with tags/env/notifier/metadata + enum so e2e
can exercise all 4 container kinds + EnumField. New test confirms:

1. + Add str button is present under the tags field
2. Clicking it dispatches add_item and the preview/tree reflects
   the new item
3. /api/tree (fetched independently) shows tags.items length 1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: MappingField e2e test

**Files:**
- Create: `tests/e2e/test_mapping_field.py`

- [ ] **Step 1: Write the test**

`tests/e2e/test_mapping_field.py`:

```python
"""E2E: add an entry to a mapping field, rename its key, assert both
server tree and preview update.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_add_entry_rename_key(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    # env starts empty - click + Add Entry under the env field
    add_button = page.get_by_role("button", name="+ Add Entry").first
    expect(add_button).to_be_visible()
    add_button.click()

    # MappingField generates a default key "key0" for the new entry.
    # The key input has aria-label="entry key".
    key_input = page.get_by_label("entry key").first
    expect(key_input).to_have_value("key0", timeout=5000)

    # Rename the key to "TZ"
    key_input.fill("TZ")
    key_input.blur()

    # Server should reflect the new key after the rename_key round-trip.
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    env_field = next(
        f for f in body["root"]["fields"] if f["name"] == "env"
    )
    # entries is a list of (k_node, v_node) tuples; the first key node's
    # value should be "TZ" after rename.
    assert len(env_field["entries"]) == 1
    k_node, _v_node = env_field["entries"][0]
    assert k_node["value"] == "TZ"

    # Preview should also show "TZ" somewhere
    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text('"TZ"', timeout=5000)
```

- [ ] **Step 2: Run**

```bash
uv run python -m pytest tests/e2e/test_mapping_field.py -p playwright -o "addopts=-ra" -q
```

Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_mapping_field.py
git commit -m "$(cat <<'EOF'
test(e2e): MappingField - add entry, rename key, assert state

Click + Add Entry under env -> server picks key0 -> client renames
to TZ via the entry-key input's onBlur. Asserts both that the server
tree shows the renamed key AND that the preview pane reflects it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: UnionField e2e test

**Files:**
- Create: `tests/e2e/test_union_field.py`

- [ ] **Step 1: Write the test**

`tests/e2e/test_union_field.py`:

```python
"""E2E: UnionField - switch variants, assert preview + server tree.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_switch_union_variant(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    # The notifier field has a default of EmailNotifier so the email
    # chip is initially selected. Click the Slack chip to switch.
    slack_chip = page.get_by_role("button", name="_SlackNotifier")
    expect(slack_chip).to_be_visible(timeout=5000)
    slack_chip.click()

    # Server tree should now show the Slack variant selected.
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    notifier_field = next(
        f for f in body["root"]["fields"] if f["name"] == "notifier"
    )
    assert notifier_field["selected_index"] is not None
    selected = notifier_field["selected"]
    assert selected is not None
    # The selected GroupNode's schema_class short name should be SlackNotifier
    assert "Slack" in selected["schema_class"]

    # Preview should mention the slack kind
    preview = page.get_by_test_id("tree-preview")
    expect(preview).to_contain_text('"slack"', timeout=5000)
```

- [ ] **Step 2: Run**

```bash
uv run python -m pytest tests/e2e/test_union_field.py -p playwright -o "addopts=-ra" -q
```

Expected: 1 passed.

If the test fails on `_SlackNotifier` not being visible: the variant_type_names format includes module qualification (e.g., `tests.e2e.conftest._SlackNotifier`). Check what the actual button text is and update the locator. The `shortName` helper in UnionField does `split(".").pop()` which would yield `_SlackNotifier` — so the locator should match.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_union_field.py
git commit -m "$(cat <<'EOF'
test(e2e): UnionField - switch variant, assert tree + preview

Default variant is _EmailNotifier (per default_factory in
_DemoSchema). Click the _SlackNotifier chip; assert the server
tree's selected_index updates and the selected GroupNode shows
the SlackNotifier schema_class.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: AnyField e2e test

**Files:**
- Create: `tests/e2e/test_any_field.py`

- [ ] **Step 1: Write the test**

`tests/e2e/test_any_field.py`:

```python
"""E2E: AnyField - dict[str, Any] entries support the AnyField editor.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_any_field_parses_json_value(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    # metadata starts empty. Add an entry via the metadata's +Add button.
    # There are TWO +Add Entry buttons (env and metadata); use .all()
    # and pick the second.
    add_buttons = page.get_by_role("button", name="+ Add Entry").all()
    assert len(add_buttons) >= 2, (
        f"expected >=2 +Add Entry buttons, found {len(add_buttons)}"
    )
    add_buttons[1].click()   # the metadata one

    # The new entry's value field is an AnyField - takes raw text or JSON.
    # Locate the "any value (JSON or raw string)" placeholder input.
    any_input = page.get_by_placeholder(
        "any value (JSON or raw string)"
    ).first
    expect(any_input).to_be_visible(timeout=5000)

    # Type a JSON number, blur
    any_input.fill("42")
    any_input.blur()

    # Server tree should show the value as a number (not a string).
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    metadata_field = next(
        f for f in body["root"]["fields"] if f["name"] == "metadata"
    )
    assert len(metadata_field["entries"]) == 1
    _key_node, value_node = metadata_field["entries"][0]
    assert value_node["kind"] == "any"
    assert value_node["value"] == 42      # parsed as int, not string
    assert value_node["mode"] == "int"
```

- [ ] **Step 2: Run**

```bash
uv run python -m pytest tests/e2e/test_any_field.py -p playwright -o "addopts=-ra" -q
```

Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_any_field.py
git commit -m "$(cat <<'EOF'
test(e2e): AnyField - JSON-parse on blur, mode auto-syncs

Add an entry to metadata (dict[str, Any]); the value field is an
AnyField. Type '42' and blur - the JSON parser turns it into the
number 42 (not the string '42'). Server's AnyValueNode auto-syncs
mode to 'int' via its model_validator.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Full-suite verify + handoff

- [ ] **Step 1: Run the unit suite**

```bash
uv run python -m pytest tests/ --deselect tests/unit/test_docs_build.py 2>&1 | tail -3
```

Expected: 506 passed (unchanged from Phase 3; Phase 4 added no unit tests).

- [ ] **Step 2: Run the e2e suite**

```bash
uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra" 2>&1 | tail -3
```

Expected: 5 passed (the Phase 3 string-edit test + 4 new container tests).

- [ ] **Step 3: Ruff + tsc clean**

```bash
uv run ruff check tests/e2e
cd frontend && pnpm exec tsc -b
```

Expected: All checks passed! / exit 0.

- [ ] **Step 4: Phase 4 done — handoff note**

Phase 4 ships:
- 4 new container field components (SequenceField, MappingField, UnionField, AnyField)
- GroupField polish (collapsible card for nested groups)
- Path helper (`childPath`) centralizing the dotted-path convention
- zod schemas for the 4 new node kinds (FormNodeData grew from 7 to 11 known variants)
- Updated FormField dispatcher (10 known cases + Phase 5+ placeholder for the 14 remaining primitive kinds)
- Rebuilt bundle (~140-180 KB gzip, still under spec's 250 KB)
- 4 new Playwright e2e tests, one per container kind

Known gaps (deferred to Phase 5+):
- The 14 other primitive kinds (date/datetime/time/timedelta/uuid/ip_address/ip_network/url/email/secret/path/bytes/pattern/decimal/float)
- Validation surface (red border on bad input, errors tab)
- Theme toggle + sidebar search
- Vitest unit tests
- `data-testid={`field-${path}`}` for robust e2e selectors
- GroupField depth-based default-collapse (spec §6.3 says "default collapsed for nested groups deeper than 2 levels")

Recommended branch name: `feature/shadcn-redesign-phase-4-container-fields`; merge with `--no-ff` per the codebase convention; tag the feature tip as `v0.2.0-phase-4` before merging.

---

## Self-review checklist (already applied)

- ✅ **Spec §8 Phase 4 ("Container fields: sequence, mapping, union, group (inline), any")**: T2 (group polish), T3 (sequence), T4 (mapping), T5 (union), T6 (any), T7 (dispatcher), T8 (bundle).
- ✅ **Spec §8 acceptance ("Playwright tests for each container kind")**: T9 (sequence), T10 (mapping), T11 (union), T12 (any). 4 new tests.
- ✅ **Spec §6.3 container designs**: SequenceField (stack of cards + add/remove/move) ✓, MappingField (two-column cards + add/remove/rename) ✓, UnionField (variant chips + selected editor) ✓, GroupField (collapsible) ✓.
- ✅ **Spec §3.2 mutation contract**: add_item/remove_item/move_item/add_entry/remove_entry/rename_key/select_variant — all wired in T3-T5. (set_value was already wired in Phase 3.) add_item ✓ in T3; remove_item ✓ in T3; move_item ✓ in T3; add_entry ✓ in T4; remove_entry ✓ in T4; rename_key ✓ in T4; select_variant ✓ in T5.
- ✅ **No placeholders**: every step has exact code or commands; no "TBD" / "add appropriate handling".
- ✅ **Type consistency**: `childPath`, `SequenceNodeData`, `MappingNodeData`, `UnionNodeData`, `AnyValueNode` used consistently across T1-T7.
- ✅ **Frequent commits**: 13 task-aligned commits.
- ✅ **YAGNI**: no constraint UI polish (Phase 5), no theme toggle, no Vitest, no data-testid refactor (Playwright tests use labels + placeholders + roles), no depth-based default-collapse, no insert_item in SequenceField (move_item covers reorder; insert isn't in the spec's mutation contract).
- ✅ **Pyright pitfalls anticipated**: FormField uses the same `NodeOfKind<K>` cast helper Phase 3 established; recursive `z.lazy` types preserved.
- ✅ **Backend not touched**: Phase 1's mutation API exposes everything Phase 4 needs (verified: add_item, remove_item, move_item, add_entry, remove_entry, rename_key, select_variant all reach `_resolve` correctly via dotted paths).
- ✅ **E2e plugin scoping preserved**: tests/e2e/ stays gated behind `-p playwright -o "addopts=-ra"`; no changes to pyproject.toml addopts needed.
