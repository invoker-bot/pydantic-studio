# Task-oriented editing — TUI interaction overhaul (v0.2)

Date: 2026-06-11
Status: approved for implementation (driven by HFT `hft config gen/edit` field reports)

## Problem

The TUI v2 single-panel editor renders form *state* faithfully but does not
serve the user's *task* ("get from intent to a valid saved config with
minimal friction, without losing data"). Field-verified failures, observed
by driving `StudioApp` headlessly against a real downstream schema
(HFT `OKXExchangeConfig`, 23 fields / 3 required):

### P0 — correctness / data loss

1. **Load bypasses field validators → silent data corruption downstream.**
   `load_yaml` / `build_form_tree(existing=...)` copy raw wire values into
   nodes. Any field whose `Annotated` metadata carries a transforming
   validator (`PlainValidator` / `BeforeValidator`) ends up holding the wire
   form while the editor treats it as the runtime form. Verified end-to-end
   with HFT's Fernet-encrypted `SecretStr` fields: one edit cycle
   (`load_yaml` → touch an unrelated field → `to_instance().model_dump()`)
   **double-encrypts every secret** — the saved config then fails exchange
   auth at runtime with no visible cause. The tree honors serializers on
   save (`model_dump`) but skips validators on load; the asymmetry is the
   bug.

2. **Esc on a small-choice field crashes the whole app.**
   `FieldListView.action_activate_focused` falls through to the *base*
   `Cell.enter_edit()` for small `ChoiceCell`s, which have no edit UI: a
   phantom edit mode (footer flips, row visuals don't) where Enter does
   nothing and Esc raises `AttributeError: 'ChoiceCell' object has no
   attribute 'cancel_edit'` — the app dies, all session input is lost.

3. **No submit/cancel distinction.** `run_app()` returns `None`; the only
   way to finish is Ctrl+C ("quit"). Downstream callers must guess intent
   after the fact: HFT's `gen`/`edit` call `tree.to_instance()` after quit,
   so *quit-with-partial-input* silently discards everything ("cancelled")
   while *quit-after-completing* commits — the user has no way to express
   "I'm done, save" vs "forget it", and no unsaved-changes guard exists.
   Meanwhile Ctrl+S (the natural save gesture) is a dead end without
   `save_path` ("No save path configured").

4. **Footer state machine corrupts.** The phantom edit mode from (2) leaves
   the footer stuck on "Enter commit | Esc cancel" after unrelated screens
   (e.g. ErrorsScreen) pop.

### P1 — no task guidance

5. Required fields sit wherever the schema declares them (in HFT's case:
   dead last), marked only by a faint `*`. No "jump to next missing
   required", no count of what's left, and a failed save shows a detached
   error list that the user must memorize — after dismissing it the cursor
   doesn't move to the offending field.
6. `FieldInfo.description` — the single most valuable guidance the schema
   carries, already written by config authors — is never displayed.
7. Labels hard-truncate (`auto_tracking_orders_a…` vs `…_b`
   indistinguishable) with no ellipsis.

### P2 — friction

8. No search/filter; 23+ field forms are arrow-key-only.
9. Container previews are opaque (`2 fields>`, `0 items>`).
10. Downstream needs field-level read-only (HFT force-overrides `path` on
    edit; the TUI happily lets the user edit a value that will be ignored).

## Approaches considered

- **A. Patch the crashes only.** Cheap; leaves the task-model failure (P0.1,
  P0.3, P1) untouched. Rejected — the complaint is the interaction model,
  not just the bugs.
- **B. Task-oriented session on the existing single-panel skeleton**
  (chosen). Keep the field-list UI; make the *session* explicit
  (submit/cancel outcome, dirty guard), make loading symmetric with saving
  (parse on load), and wire guidance (next-required jump, description help
  bar, error-to-field linkage, filter).
- **C. Full two-pane master-detail rewrite with mouse support.** The ideal
  end state, but a rewrite of the widgets layer; too much risk in one step
  and orthogonal to the correctness fixes. Deferred.

## Design (approach B)

### B1. Session outcome protocol

New `pydantic_studio/outcome.py`:

```python
@dataclass(frozen=True)
class EditOutcome:
    status: Literal["submitted", "cancelled"]

    @property
    def submitted(self) -> bool: ...
```

- `StudioApp(tree, save_path=None, readonly_paths=frozenset())`.
- `run_app(...) -> EditOutcome` (was `None`; additive change).
- **Ctrl+S = submit**: validate via `to_instance()`. Valid → write
  `save_path` if configured → exit with `submitted`. Invalid → notify +
  ErrorsScreen; on dismiss the cursor jumps to the first offending
  top-level row and the row shows the error helper.
- **Ctrl+C / Esc at root = cancel**: if the tree is dirty (deep-compare
  `tree.to_python()` against the session-start snapshot), push a
  ConfirmExitScreen — `[S]ave & exit / [D]iscard / [Esc] keep editing`;
  clean trees exit immediately with `cancelled`.
- Quit via ConfirmExit's Save path behaves exactly like Ctrl+S.

Downstream contract (HFT `gen`/`edit`): only `outcome.submitted` saves;
`cancelled` aborts without writing. No more quit-means-commit.

### B2. Parse-on-load (fixes double encryption)

`GroupBuilder` (the one place that holds `FieldInfo` for model fields):
when a field's annotation metadata contains a transforming validator
(`PlainValidator` / `BeforeValidator` / `WrapValidator`) and an existing
raw value is present, run `TypeAdapter(annotation).validate_python(raw)`
and hand the *validated instance* to the child builder.

- `pydantic.ValidationError` → fall back to the raw value (the user is
  repairing a broken file; show it as-is).
- Any other exception (e.g. wrong Fernet password → `InvalidToken`)
  propagates — corrupting silently is worse than failing loudly.
- `SecretBuilder` learns to unwrap `SecretStr`/`SecretBytes` instances for
  `existing` (it already must for instance defaults).
- Save side is already symmetric (`model_dump` applies serializers).
- Validators must be idempotent w.r.t. runtime instances (they already
  receive instances on every TUI-typed value today; this is a de-facto
  requirement, now documented).

### B3. Required-field guidance

- `FormTree.missing_required_paths() -> list[str]` — preorder walk
  collecting required leaves with no value (drilling into groups,
  sequence items, mapping values, selected union variants).
- `FieldListView` binding **`n`** — cyclic jump to the next row whose
  subtree contains a missing-required or errored path.
- Failed save (B1) jumps to the first offending row.
- HelpBar (B4) shows `⚠ N required missing` while any remain.

### B4. HelpBar (description display)

One-line widget between the field list and the footer showing, for the
focused row: `name — description` plus a constraint summary
(`required · int · ge=1 · le=65535`, `read-only` when applicable).
`FieldListView` posts a `CursorMoved` message on mount and cursor moves;
ConfigScreen routes it to the HelpBar. Descriptions come from
`FormNode.description` (already populated from `FieldInfo.description`).

### B5. Phantom-edit fix

- Enter on a small ChoiceCell **cycles** (same as Tab) instead of entering
  the base-class phantom edit mode; large choices keep the chooser screen.
- `Cell.cancel_edit()` gets a safe default implementation (`exit_edit`),
  and `action_cancel_focused` guards with `getattr` — Esc can never crash
  again.
- With phantom edits gone the footer state machine self-heals; a
  regression test pins footer mode after ErrorsScreen dismiss.

### B6. Honest labels

Label column width derives from the longest label in the active container
(clamped to 40% of screen width); anything longer gets a real `…` ellipsis.

### B7. Read-only paths

`StudioApp(readonly_paths={"path"})` → rows render a lock marker, edit
attempts show a "read-only" helper instead of mutating, HelpBar says
`read-only`. Mutation guard lives in `FieldListView` action handlers.

### B8. Filter

`/` opens a one-line filter input (replaces HelpBar slot while active);
typing narrows visible rows by substring match on name; Enter keeps the
filter (Esc clears it); cursor clamps to the filtered list. Filter state
is per-screen and resets on drill-in.

## Testing

TDD per project convention (`App.run_test()` + Pilot for TUI; pure-tree
tests for `missing_required_paths` and parse-on-load). New tests cover:
outcome protocol (submit / cancel / dirty-confirm), Esc-on-choice
regression, footer regression, save-failure cursor jump, `n` jump, HelpBar
content, readonly guard, label ellipsis, filter, GroupBuilder transform
coercion (PlainValidator round-trip), SecretBuilder instance unwrap.

Downstream (HFT) pins the integration contract in its own suite:
`run_app` returns an outcome; gen/edit save only on `submitted`; encrypted
secrets survive a load→save cycle decrypting to the original plaintext;
descriptions and `missing_required_paths` are populated for its schemas;
`edit` passes `readonly_paths={"path"}`.

## Out of scope

Two-pane layout, mouse support, container value previews (P2.9), web/SPA
parity for the new bindings (the HTML renderer keeps its own submit/cancel
semantics, which were already explicit), console renderer changes beyond
compatibility.
