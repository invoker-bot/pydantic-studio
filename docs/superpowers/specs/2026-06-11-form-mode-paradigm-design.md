# Form-mode paradigm — aligning both frontends with human operating habits

Date: 2026-06-11 (v2, follows the task-oriented editing spec of the same date)
Status: approved for implementation

## The complaint, restated

The 0.2.0 overhaul fixed *correctness* (submit/cancel, parse-on-load,
crashes) and added *guidance* (HelpBar, `n`, `/`). The downstream
verdict: still not enough — the **interaction paradigm itself** fights
human habits. Verified by driving both frontends against real
downstream schemas (`OKXExchangeConfig`, 23 fields; `AppConfig`, 30+
fields with 7-plugin mapping + optional nested models):

### TUI paradigm violations

- **T1 Modal cell editing.** Focus ≠ editable. The user must press
  Enter to *enter* an edit mode, Enter again to commit, Esc to leave.
  Every editor humans use daily (web forms, spreadsheets, IDE settings)
  works the other way: *the focused field is the editable field* —
  you type, you Tab to the next one.
- **T3 No mouse.** `mouse=False` everywhere (chosen for native
  copy-paste). Clicking a row, toggling a switch, pressing a visible
  button, wheel-scrolling — all dead.
- **T4 No visible actions.** Save/Cancel exist only as key chords
  described in footer prose. Humans look for buttons.
- **T5 Letter-key actions collide with typing.** `a` add, `d` delete,
  `r` rename, `n` next-required, `/` filter — all unreachable the
  moment focus-is-editable arrives, and all non-discoverable anyway.
- **T2 Nesting swaps the whole screen.** Drilling into
  `white_deposit_addresses[0]` replaces the entire view; parent
  context survives only as a breadcrumb. Humans expect in-place
  expansion (tree/accordion).

### Web paradigm violations

(The React SPA is the canonical web UI; the legacy Jinja/HTMX templates
are dead code. The SPA already does much right: real widgets, top
action bar, descriptions, required badges, live YAML preview.)

- **W1 Errors are a detached banner.** Submit failures render a red
  list at the top; offending fields get no highlight, no
  click-to-jump, no auto-scroll. On a 23-field page the user plays
  find-the-field.
- **W2 Deep nesting renders fully expanded.** `AppConfig` becomes a
  wall: 7 plugin cards × (enabled + params × entries), and the
  *optional* `database` model spreads all its fields as if they were
  required. Humans expect collapsed-by-default sections with
  summaries.
- **W4 Required fields exist but aren't guided.** Badges yes; count /
  jump / anchor navigation no.
- **W5 Unreachable from the CLI.** `hft config gen/edit` can only
  launch the TUI; the frontend closest to human habits has no
  entry point.

## Design

### A. TUI form mode (replaces the modal-cell model)

1. **Focus = edit.** Text-backed leaf cells (string, numbers, temporal,
   network, path, uuid, pattern, bytes, secret) host a *persistent*
   Input widget. Moving the cursor onto the row focuses the Input;
   typing edits immediately. No enter-edit/exit-edit lifecycle.
2. **Form navigation keys.**
   - Tab / Shift+Tab: commit the current value, move to next/previous
     row (same keys across all cell kinds).
   - Up / Down: commit, then move.
   - Enter: commit, then advance to the next row (spreadsheet habit).
     On containers: open (drill — or expand once T2 lands).
   - Esc: revert the focused field to its value-on-focus; thereafter
     the layered Esc (filter → child screen → session) applies.
   - Bool: Space/Enter toggles. Choice: Left/Right cycles, Enter opens
     the chooser for large sets.
3. **Humane action keys** (letter keys freed for typing):
   - `Ctrl+F` filter (was `/`), `Ctrl+N` jump-to-next-required (was
     `n`), `F2` rename mapping key (was `r`), `Delete`/`Backspace`*
     remove item on container screens (was `d`), move stays
     `Ctrl+Up/Down`. (*only where the row is not text-editable.)
   - Adding items: an **[+ add item] AddRow** at the end of
     sequence/mapping screens — Enter or click. (Replaces invisible
     `a`.)
4. **ActionBar.** A persistent bottom bar with real `[ Save ]`
   `[ Cancel ]` buttons (mouse-clickable, Tab-reachable), doubling the
   Ctrl+S / Ctrl+C chords. Sits under the HelpBar.
5. **Mouse on by default.** Click row → focus it. Click toggle/choice →
   change it. Wheel scrolls. `run_app(..., mouse=False)` remains an
   opt-out for copy-heavy workflows (most terminals bypass via
   Shift+drag anyway).

### B. Web fixes

1. **W1 Anchored errors.** Submit failure: banner stays as the summary,
   each entry becomes a link that scrolls to + flashes the field; the
   field row shows a red border + inline message; auto-scroll to the
   first offender on failure.
2. **W2 Collapsible nesting.** Group/sequence/mapping cards collapse to
   a one-line summary (`name · N fields/items`) with chevron toggle.
   Default: root-level scalars stay flat; nested containers start
   collapsed. An *optional* model that is still untouched shows
   `not set — click to configure` instead of a full field spread.
3. **W4 Required guidance.** Sticky header shows `N required missing`;
   clicking it jumps to the next missing-required field (cycling).
4. Rebuild `static/dist` via pnpm; bundle stays committed.

### C. HFT wiring

`hft config gen/edit --web` launches `run_html_app` (same
submit/cancel + readonly_paths contract — the server side gets
readonly support to match). Default remains the TUI.

## Out of scope (deferred, recorded)

- T2 full in-place tree expansion in the TUI (structural rewrite of
  FieldListView's row model; the breadcrumb + form-mode changes reduce
  the pain meanwhile).
- Console renderer form-mode parity.
- Web sections/anchor sidebar beyond the required-jump (W3) — revisit
  once collapsing lands, which removes most of the wall.

## Testing

TUI: pilot-driven — typing without Enter mutates the tree after
Tab/arrow commit; Esc reverts; AddRow adds; Delete removes; clicks
focus/toggle; ActionBar buttons submit/cancel; key remaps pinned.
Web: vitest component tests where present + a Playwright smoke against
the rebuilt bundle (errors anchor + collapse behavior), plus the
existing FastAPI TestClient API suites.
HFT: contract test asserting `--web` invokes `run_html_app` with
readonly_paths and obeys the outcome protocol.
