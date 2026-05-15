# TUI redesign — Claude Code `/config` aesthetic

| Field | Value |
|---|---|
| Status | Draft, awaiting user review |
| Successor to | `src/pydantic_studio/renderers/textual_/` (Phase 5 sidebar + editor-pane split) |
| Driver | Current TUI is functional but visually plain (Textual defaults, IDE-style two-pane). User wants the polish + focus of Claude Code's `/config` settings dialog: centered modal, vertical list, in-place editing, drill-down for nested, warm minimal palette. |
| Working dir at design time | `D:\Projects\Work\pydantic-studio\` |

---

## 1. Goal

Replace the TUI's sidebar + editor-pane layout with a single centered modal that
navigates fields like Claude Code's `/config` dialog. Drill-down for nested
containers (Group / Sequence / Mapping / Union variants), in-place value editing
for leaves, footer hint bar with context-sensitive keybinds, warm muted palette
with a single accent color.

The web (SPA) and CLI renderers are unaffected. Only the Textual renderer at
`src/pydantic_studio/renderers/textual_/` changes.

---

## 2. Motivation

Today's TUI is technically correct but feels dated:

1. **Visually plain** — Textual default theme, heavy borders, default accent. No
   shared identity with Claude Code (the reference) or the shadcn SPA (sibling
   surface).
2. **Cognitively wide** — sidebar lists every group, editor pane shows the
   current group's fields, plus inline labels and error static-text widgets. The
   eye has to scan a lot to find anything.
3. **No keybind discoverability** — the user has to know `Ctrl+S` saves and the
   sequence Add button is `+ Add` somewhere; nothing tells them.
4. **No focus locus** — every editor row looks the same; there's no
   "you-are-here" marker.

The `/config` aesthetic solves all four: one panel, one focused row, one accent,
keybind hints always visible. It also matches the rest of the project's recent
direction (shadcn polish on the SPA, lucide-equivalent simplicity).

---

## 3. Design principles

1. **One panel at a time.** Drill into nested containers; don't show them
   alongside their parent. Breadcrumb in the title bar tracks the path.
2. **One row focused.** A single highlighted row at all times. All keys act on
   that row (Enter edits / drills, Space toggles, Tab cycles, D deletes,
   R renames).
3. **Inline editing where possible.** Don't pop a modal-over-modal for a string
   edit. Press Enter → the value cell becomes an input. Enter commits, Esc
   cancels. Errors appear as a red helper line under the row.
4. **Server is authoritative.** Mutations route through the existing
   `FormTree.set_value` / `add_item` / `select_variant` etc. — the validate-first
   contract is preserved. The TUI never has its own canonical state.
5. **Keybinds are visible.** Footer always shows the relevant keys for the
   current mode (idle / editing / drilled-in-sequence / etc.).
6. **Single accent color.** Everything else is shades of gray. The accent
   marks the focused row + primary actions. No rainbow palette.

---

## 4. Architecture

### 4.1 Region layout

```
┌─ AppSettings ──────────────────────────────────────┐    ← title bar (breadcrumb)
│                                                     │
│  ▸ name              · · · · ·  my-service          │    ← field list
│    workers           · · · · ·  4                    │       (scrollable)
│    debug             · · · · ·  [ off ]              │
│    database          · · · · ·  (group)         >    │
│                                                     │
├─────────────────────────────────────────────────────┤
│ ↑↓ navigate · Enter edit · Tab cycle · Esc back     │    ← footer hint bar
│ Ctrl+S save · Ctrl+Q quit                            │       (2 lines)
└─────────────────────────────────────────────────────┘
```

Modal centered in the terminal at 80 cols × `min(28, term_h - 4)` rows. If the
terminal is narrower than 80 cols, fall back to `term_w - 4`. The body region
scrolls vertically if the field list exceeds the available height.

### 4.2 Screen stack model

Each "level" of the schema (root group, drilled-into group, sequence items
panel, mapping entries panel, errors panel) is its own Textual `Screen`. Pushing
a screen drills in; popping returns. Textual already supports this natively via
`app.push_screen` / `app.pop_screen` — no custom navigation stack to maintain.

The breadcrumb in the title bar derives from the stack depth:

- Root: `┌─ AppSettings ─...─┐`
- 1 deep: `┌─ AppSettings › database ─...─┐`
- 2 deep: `┌─ AppSettings › database › auth ─...─┐`
- Truncated at 3+ deep: `┌─ AppSettings › … › auth ─...─┐` (middle ellipsis).

### 4.3 Module shape

```
src/pydantic_studio/renderers/textual_/
├── app.py                                 # StudioApp (shell; unchanged surface)
├── screens.py                             # ConfigScreen, ContainerScreen, ErrorsScreen
├── widgets/
│   ├── field_list.py                      # FieldListView (vertical row stack)
│   ├── field_row.py                       # FieldRow (focused/idle, dispatches to cells)
│   ├── breadcrumb.py                      # title bar with truncating path
│   ├── footer_hints.py                    # 2-line keybind hint bar
│   └── cells/                             # NEW per-kind value cell widgets
│       ├── text_cell.py                   # str/int/float/decimal/date/.../path
│       ├── bool_cell.py                   # [ off ] / [ on  ]
│       ├── choice_cell.py                 # ‹ value › or drill-down chooser
│       ├── container_cell.py              # (group) | N items | N entries | [variant]
│       └── secret_cell.py                 # ********** (with reveal toggle)
├── theme.tcss                             # NEW custom palette + row chrome
└── (DEPRECATED, kept for one phase)
    ├── widgets/scalars.py                 # legacy TextInputEditor, BoolEditor, ChoiceEditor
    └── widgets/containers.py              # legacy SequenceEditor, MappingEditor, UnionEditor
```

Once the new screens cover every interaction the legacy widgets supported and
all `tests/unit/test_textual_*.py` are rewritten against the new widgets, the
deprecated files are deleted as part of M6 (Cutover).

---

## 5. Component design

### 5.1 `ConfigScreen(group_node: GroupNode, breadcrumb: list[str])`

Wraps a `GroupNode`. Composes:

- `Breadcrumb(parts=breadcrumb)` at the top
- `FieldListView(group_node)` in the middle (scrollable)
- `FooterHints(mode="idle")` at the bottom

Key bindings (priority order):

| Key | Action |
|---|---|
| `up` / `down` | move row focus |
| `enter` | edit current row (delegates to focused cell) |
| `tab` / `right` | cycle value if cell supports it (bool, choice) |
| `shift+tab` / `left` | cycle backwards |
| `escape` | pop screen (no-op at root → quit prompt) |
| `ctrl+s` | save (validate → save_yaml → app.exit) |
| `ctrl+q` | cancel (set app.cancelled, app.exit) |

### 5.2 `FieldRow(node: AnyNode, path: str, focused: bool)`

One row in the field list. Composes:

- left chrome: focus marker `▸ ` or `  `
- label (left-justified, fixed width 22 cols)
- dotted leader filling the gap
- value cell (right-justified, variable width)
- drillable marker `>` on the far right for Group/Sequence/Mapping/Union

Dispatches to one of these cells based on `node.kind`:

| kind(s) | cell |
|---|---|
| string, int, float, decimal, datetime, date, time, timedelta, ip_address, ip_network, url, email, path, uuid, pattern, bytes | `TextCell` |
| bool | `BoolCell` |
| enum, literal | `ChoiceCell` |
| secret | `SecretCell` |
| group, sequence, mapping, union | `ContainerCell` |
| any | `TextCell` with JSON-string mode |

### 5.3 Per-kind cell behavior

#### `TextCell`
- **Idle**: renders the current value as text (`str(node.value)` with hex
  fallback for bytes, ISO for date/datetime/time, str for Decimal/UUID/IP).
- **Editing** (after Enter): replaces text with a Textual `Input` widget,
  cursor inside, current value pre-filled. **Enter** parses via the existing
  `_parse_for_kind(kind, raw)` helper from `widgets/scalars.py`, then routes
  to `FormTree.set_value(path, parsed)`. On parse or validate failure: red
  helper line `[!] {message}` below the row, value reverts. **Esc** exits
  edit mode without mutation.

#### `BoolCell`
- Renders `[ off ]` / `[ on  ]` (5-char chips, matched widths so the row
  doesn't jitter on toggle). Chosen over `[ ]`/`[x]` because the on/off text
  is unambiguous to non-developers and matches the existing SPA's
  `Switch`-style bool surface.
- **Space** or **Enter** flips the value via `set_value`. No "edit mode" —
  toggle is immediate.

#### `ChoiceCell`
- Renders `‹ {value} ›` for ≤7 choices. Threshold chosen because cycling
  through 8+ options with Tab gets tedious (worst case: 4 presses to reach
  the target) and the longest value's width plus chevrons might exceed the
  value column. ChooserScreen scales better past that.
- **Tab** / **right** / **left** cycle through the choices in place via
  `set_value`.
- **Enter** with >7 choices pushes a `ChooserScreen` listing all options;
  Enter on a row picks it and pops back.

#### `SecretCell`
- Renders `**********` (always — never reveal in the read view).
- **Enter** opens inline `Input` with `password=True`; same commit flow as
  TextCell.

#### `ContainerCell`
- Renders the appropriate summary:
  - Group: `(group)`
  - Sequence: `N items` (or `empty` if 0)
  - Mapping: `N entries` (or `empty`)
  - Union: `[{variant_short_name}]` (or `<unselected>` if none)
- Right-side marker: `>`.
- **Enter** pushes the appropriate sub-screen (see §5.4–5.6).
- **Tab** on Union cycles the variant in place via `select_variant`.

### 5.4 Sequence drill-down: `SequenceScreen(node: SequenceNode, path)`

Same chrome as ConfigScreen. Body is the sequence's items as rows, each
labelled `[i]` instead of the field name. Final row is `+ Add {type}` ghost
row (different style — italic, no marker).

Key bindings (in addition to ConfigScreen's):

| Key | Action |
|---|---|
| `enter` on `+ Add` | call `FormTree.add_item(path, default)` then auto-focus the new row |
| `d` | call `FormTree.remove_item(path, focused_index)` |
| `enter` on item | edit if leaf; drill if container item |

### 5.5 Mapping drill-down: `MappingScreen(node: MappingNode, path)`

Rows are `{key} → {value-summary}`. Final row is `+ Add entry`.

Key bindings:

| Key | Action |
|---|---|
| `enter` on `+ Add` | call `FormTree.add_entry(path, "", default_value)`; immediately drop into rename-key mode |
| `enter` on entry | edit value cell (leaf or drill) |
| `r` | rename key via `FormTree.rename_key(path, idx, new_key)` |
| `d` | remove via `FormTree.remove_entry(path, idx)` |

### 5.6 Union variant selection

Union doesn't get its own screen — it's a single row with `ContainerCell`. The
Tab/cycle behavior switches the variant (calling
`FormTree.select_variant(path, variant_index)`), and Enter drills into the
selected variant's GroupNode (treated exactly like a Group drill).

### 5.7 Errors screen: `ErrorsScreen(errors: list[ValidationError])`

Triggered when Ctrl+S validation fails. Shows one row per error:

```
[!] name              pattern violation: ^[a-z][a-z0-9-]*$
[!] database.port     must be ≥ 1 and ≤ 65535
[!] tags[1]           value is required
```

**Enter** on an error pops back through the screen stack to the offending
row (best-effort: walks the path, drills to the deepest reachable
ancestor, focuses the leaf if visible). **Esc** pops back to the screen
that triggered Save.

---

## 6. Theme (`theme.tcss`)

Custom Textual CSS defining the palette. Keep it terminal-respecting (i.e.
use Textual's variable system, not hard-coded hex, so dark/light themes
both look intentional).

```css
$surface: #0f0f10;
$surface-lighten-1: #1a1a1c;
$text: #e8e6e3;
$text-muted: #6e6e6e;
$accent: #d18b40;
$error: #cc6666;

Screen {
  background: $surface;
  color: $text;
}

FieldRow {
  height: 1;
  padding: 0 1;
}

FieldRow.-focused {
  background: $surface-lighten-1;
  color: $text;
}

FieldRow.-focused > .focus-marker {
  color: $accent;
}

FieldRow > .label {
  width: 22;
  color: $text;
}

FieldRow > .leader {
  color: $text-muted;
}

FieldRow > .value {
  color: $text;
}

FieldRow > .drill-marker {
  color: $text-muted;
  width: 3;
  align: right top;
}

FieldRow.-error > .helper {
  color: $error;
}

Breadcrumb {
  height: 1;
  background: $surface;
  color: $text-muted;
}

Breadcrumb > .current {
  color: $accent;
}

FooterHints {
  height: 2;
  background: $surface;
  color: $text-muted;
}

FooterHints > .key {
  color: $accent;
}
```

Light-theme override is a Phase 6 nice-to-have already on the deferred list.

---

## 7. Interactions in detail

### 7.1 Editing a string field

```
1. User focuses `name` row (▸ marker on left, accent bg).
2. Footer reads: ↑↓ navigate · Enter edit · Tab cycle · Esc back
3. User presses Enter.
4. Value cell ("my-service" text) replaced with Input widget,
   pre-filled "my-service", cursor at end. Footer updates to:
   Type to edit · Enter commit · Esc cancel
5a. User types and presses Enter → _parse_for_kind("string", raw)
    → FormTree.set_value("name", parsed) → success: cell returns
    to text view showing new value. Footer reverts.
5b. User presses Esc → cell returns to text view, no mutation.
5c. User types invalid value, presses Enter → set_value fails →
    red helper line "[!] {error}" appears below the row, value
    cell reverts to last committed value. Stay in edit mode? No —
    exit edit mode so error helper persists until user re-enters
    edit or moves to another row.
```

### 7.2 Toggling a bool

```
1. User focuses `debug` row.
2. Presses Space (or Enter).
3. FormTree.set_value("debug", not_current) → row re-renders
   with new [ on  ] / [ off ] state. No edit mode, no Input widget.
```

### 7.3 Cycling a small-choice field

```
1. User focuses `level` row (3 choices: debug/info/warn).
2. Cell renders `‹ info ›`. Footer adds: Tab cycle.
3. User presses Tab → set_value to next choice → re-render `‹ warn ›`.
   Wraps at end.
4. Shift+Tab cycles backwards.
```

### 7.4 Drilling into a group

```
1. User focuses `database` row. Cell renders `(group)  >`.
2. Footer adds: Enter drill in
3. User presses Enter → app.push_screen(ConfigScreen(database_node, [...path])).
4. New screen mounts. Breadcrumb shows `AppSettings › database`.
5. User edits fields, eventually presses Esc.
6. Screen pops. Back at the AppSettings panel. Focus restored to `database` row.
```

### 7.5 Adding to a sequence

```
1. User focuses `tags` row, presses Enter → SequenceScreen pushed.
2. Sequence is empty. Body shows only the ghost row "+ Add str".
3. Focus is on the + Add row. User presses Enter.
4. FormTree.add_item("tags", "") → screen re-renders with one item
   row "[0]  ''" + the + Add row. Focus moves to the new item.
5. User presses Enter on item → edit mode → types "alpha" → Enter
   commits. Item row now reads "[0]  alpha".
6. User presses D → item removed.
```

### 7.6 Save flow

```
1. User presses Ctrl+S anywhere.
2. App calls tree.to_instance(). On success:
    a. If app.save_path set: save_yaml(tree, save_path). On YAML
       failure (rare — usually permission), show error toast (Textual notify).
    b. app.submitted = True
    c. app.exit() → terminal returns to user with stdout "saved to <path>"
       (existing run_app behavior preserved).
3. On to_instance failure (validation):
    a. Build list of (path, message) tuples from the ValidationError.
    b. app.push_screen(ErrorsScreen(errors))
    c. User reviews. Esc returns to the editing screen.
```

### 7.7 Cancel flow

```
1. User presses Ctrl+Q (or Esc at root level).
2. app.cancelled = True
3. app.exit() → stdout "cancelled"
```

---

## 8. Data flow

Unchanged from today. The TUI mutates the FormTree via the existing methods;
the FormTree is the single source of truth. The validate-first contract
ensures invalid mutations don't pollute state.

What changes:

- Per-cell mutations now happen at the cell level (the `Cell.commit(value)`
  helper). Previously each scalar widget rolled its own commit logic.
- Re-render after mutation is now `field_row.refresh()` (Textual) rather than
  the editor's `recompose`, since the row's structure stays stable (only the
  value cell changes).

---

## 9. Error handling

### 9.1 Validation errors during edit

A failed `set_value` returns `ValidationResult(ok=False, errors=[...])`. The
cell catches this, sets `field_row.error = errors[0]`, and the row's CSS class
toggles to `-error`. A helper line below the value row renders
`[!] {message}`. The helper line is part of `FieldRow`'s composition; it's
hidden when `error is None` and shown when set. Moving focus to another row
does NOT clear the error — the row stays in error state until the user
re-enters edit mode on it (consistent with how the SPA Phase 6 plan handles
inline errors).

### 9.2 Validation errors at save

Aggregated via `tree.to_instance()` which raises `ValidationError` (or
`ValidationFailedError` from leaf nodes). The error list is built into the
`ErrorsScreen` (§5.7).

### 9.3 Operational errors

YAML write failure, draft restore failure, etc. → Textual `notify(message,
severity="error")` toast. These don't gate the editor.

---

## 10. Testing strategy

### 10.1 Unit tests (Pilot-driven)

For each new widget:

- `TextCell`: enter edit → type → commit; enter edit → type → Esc cancel;
  enter edit → invalid → error helper appears; per-kind parse coverage (one
  test per node kind that maps to TextCell).
- `BoolCell`: Space toggles; round-trips through set_value.
- `ChoiceCell` (small): Tab cycles forward; Shift+Tab cycles backward; wraps.
- `ChoiceCell` (large): Enter pushes ChooserScreen.
- `SecretCell`: shown as `**********`; edit mode uses Input with password=True.
- `ContainerCell`: renders correct summary per kind; Enter pushes correct
  screen type.
- `FieldRow`: focus marker visibility; error helper visibility; drill marker
  presence.
- `FieldListView`: up/down navigation; scroll when row count exceeds
  viewport; restores focus index on re-mount.
- `Breadcrumb`: truncation at 3+ levels.
- `FooterHints`: mode-dependent contents.

For each new screen:

- `ConfigScreen`: composes with field list of correct length; bindings fire;
  Esc pops at non-root, prompts at root.
- `SequenceScreen`: Add row visible; add → new item appears; D removes.
- `MappingScreen`: Add → rename mode; R renames; D removes.
- `ErrorsScreen`: lists errors; Enter on error pops back to offending field
  (best-effort).

Target: ≥90% coverage on the new widgets/cells/ + screens module. The
deprecated `widgets/scalars.py` and `widgets/containers.py` keep their
existing tests until they're deleted in the housekeeping pass.

### 10.2 Integration (end-to-end Pilot)

One full-flow Pilot test per major interaction:

- Load → focus name → edit → save → assert YAML output
- Load → drill into nested group → edit child → save → assert nested YAML
- Load → drill into sequence → add item → edit → remove → save
- Load → drill into mapping → add entry → rename → save
- Load → switch union variant → drill into variant → edit → save
- Load → enter invalid value → save → assert ErrorsScreen → Esc → fix → save

### 10.3 Performance budgets

- Initial mount for a 30-field schema: < 100 ms (Textual is fast; we just need
  to not regress)
- Re-render after a mutation: < 30 ms
- Memory: no leak across drill / pop cycles (verified by snapshot count
  inspection)

### 10.4 Visual regression

Out of scope. Textual doesn't have a clean snapshot story; manual screenshots
of the four mockup states (top level, editing, drilled-group, drilled-sequence,
errors) in the spec serve as the reference.

---

## 11. Migration plan

The redesign is large enough to ship as its own initiative. Suggested
break-up into 6 milestones (the writing-plans skill turns these into concrete
tasks). Milestone numbering is local to this redesign and intentionally
distinct from the project's "Phase 6 polish" slot (SPA validation surface,
theme toggle, etc.) so the two streams don't collide:

1. **M1 — Chrome:** theme.tcss, Breadcrumb, FooterHints, FieldRow shell
   (no cells yet). Smoke test that ConfigScreen mounts with a hard-coded
   mock list.
2. **M2 — Leaf cells:** TextCell, BoolCell, ChoiceCell, SecretCell. Wire
   ConfigScreen to dispatch via FieldRow. All leaf kinds editable.
3. **M3 — Container cells + Group drill:** ContainerCell rendering;
   ConfigScreen.push for Group; breadcrumb depth.
4. **M4 — Sequence/Mapping screens:** SequenceScreen, MappingScreen;
   add/remove/rename.
5. **M5 — Union + ErrorsScreen:** variant cycling in place + drill-down;
   ErrorsScreen on Ctrl+S validation failure.
6. **M6 — Cutover:** swap `EditorScreen` → new `ConfigScreen` in
   `StudioApp`; delete `widgets/scalars.py` + `widgets/containers.py`;
   update or delete old `test_textual_widgets.py` tests.

Each milestone ships independently with its own tests; the old TUI keeps
working as the default until M6 flips the switch. M1–M5 land behind a
feature flag (env var `PYDANTIC_STUDIO_TUI_V2=1` or similar) so they can
be exercised in isolation without forcing a half-built UI on every user.

---

## 12. Open questions (defer to plan or first PR)

1. **Confirmation on D (delete) in sequence/mapping.** Cheap to add (`D`
   shows `delete? [y/n]` footer prompt); cheap to omit. Recommend omit for
   v1, add if user feedback suggests accidents.
2. **Read-only fields.** No node currently has a read-only flag, but adding
   one for computed fields (e.g., `created_at: datetime`) would be a small
   extension. Out of scope for this redesign.
3. **Mouse support.** Textual supports click handlers. Enabling Click on row
   = focus is ~3 lines. Enabling drag-to-reorder in sequences is much more
   work. Recommend click-to-focus only; reorder via keybind only.
4. **Cell width when value is very long.** Today a long string would
   overflow the right edge. Options: truncate with ellipsis + show full value
   when editing; soft-wrap; horizontal scroll. Recommend truncate; full value
   visible in edit mode.

---

## 13. Out of scope (deliberately deferred)

These are post-M6 candidates, listed so the redesign doesn't grow:

- Light/dark theme toggle (today: dark only; light when terminal background
  is light is acceptable for v1)
- Sidebar search/filter (Sequence/Mapping with >50 entries — punt to drill-
  down navigation; revisit if users hit pain)
- Undo/redo UI (the snapshot ring exists; surface in a future polish pass)
- Constraint badges in the value cell (`int · ≥1 · ≤64` — partially covered
  by the helper line on error; full badge surface is post-v1)
- Mouse drag reordering in sequences
- Visual regression snapshot testing (manual review for v1)
