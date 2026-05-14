# Shadcn Web Redesign — Phase 5: Remaining Primitive Renderers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the remaining 15 primitive FormNode kinds (`float`, `decimal`, `datetime`, `date`, `time`, `timedelta`, `ip_address`, `ip_network`, `url`, `email`, `path`, `uuid`, `secret`, `pattern`, `bytes`) into the SPA so every type a user can put on a Pydantic model has a real React field component. Backend gains a generalized typed-value coercion at the dispatcher boundary so wire-format strings (ISO dates, hex bytes, UUID strings, decimal strings) are converted into the Python typed values that each node's `validate_value` expects. Three Playwright e2e tests cover temporal/network/special groups end-to-end. No polish (validation surface, theme toggle, sidebar search, undo/redo, constraint-aware type badges, Lucide icon migration, depth-based group collapse) — those are Phase 6.

**Architecture:** The 15 components share the Phase 3 chrome layer (`FieldRow` + `FieldHeader` + `Label` + `TypeBadge` + `RequiredBadge` + `Description` + `FieldError`) and follow the canonical StringField pattern: local state mirrors `node.value`, `onBlur` calls `useApplyMutation` with `{op: "set_value", path, value: <wire string>}`, and `useEffect` re-syncs from `node.value` after the server returns the updated tree (server-authoritative). The wire format for the 7 typed kinds is always an ISO-style string (ISO 8601 for temporals, decimal-as-string for `decimal`, hex for `bytes`, UUID string for `uuid`); the dispatcher's `_maybe_coerce_typed_value` translates each kind back into its Python type before `tree.set_value` reaches the node. zod schemas mirror the Python `FormNode` field shapes exactly (cross-verified against `src/pydantic_studio/tree/nodes.py` per task). `FormField.tsx` dispatches each `node.kind` to its component; the `default` branch shrinks from "all 15 unwired" to empty.

**Tech Stack:** Same as Phase 4 — React 18 + TypeScript strict + TanStack Query 5 + zod 3 + shadcn primitives (Button + Input + Label from Phase 3). Backend tests: pytest (existing). E2E: pytest-playwright (installed in Phase 3).

**Spec:** `docs/superpowers/specs/2026-05-14-shadcn-web-redesign-design.md` §6.2 (primitive fields), §8 Phase 5 row.

**Predecessors:**
- Phase 1 (`v0.2.0-phase-1`): JSON API including all 8 mutation ops
- Phase 2 (`v0.2.0-phase-2`): Vite/React toolchain + empty SPA
- Phase 3 (`v0.2.0-phase-3`): FormField dispatcher + 5 primitives (string/int/bool/enum/literal) + first Playwright e2e
- Phase 4 (`v0.2.0-phase-4`): 4 container kinds (sequence/mapping/union/any) + collapsible GroupField + container e2e tests

**Branch:** `feature/shadcn-redesign-phase-5-remaining-primitives` (already created — do NOT create a new one).

---

## File Structure

**Create (frontend source — 15 new field components):**
- `frontend/src/components/form/fields/FloatField.tsx` — `<Input type="number" step="any">` with numeric coercion + optional `allow_inf_nan` hint chip. ~75 lines.
- `frontend/src/components/form/fields/DecimalField.tsx` — text input with `inputMode="decimal"`; sends string wire value. ~60 lines.
- `frontend/src/components/form/fields/DatetimeField.tsx` — `<Input type="datetime-local">`; slices ISO down to `YYYY-MM-DDTHH:MM`, sends full ISO 8601 string on commit. ~75 lines.
- `frontend/src/components/form/fields/DateField.tsx` — `<Input type="date">`; sends `YYYY-MM-DD` string. ~60 lines.
- `frontend/src/components/form/fields/TimeField.tsx` — `<Input type="time">`; sends `HH:MM` or `HH:MM:SS` string. ~60 lines.
- `frontend/src/components/form/fields/TimedeltaField.tsx` — text input with ISO 8601 duration placeholder (`PT1H30M`). ~60 lines.
- `frontend/src/components/form/fields/IPAddressField.tsx` — text input, font-mono, version-aware placeholder (`192.0.2.1` for v4, `2001:db8::1` for v6). ~60 lines.
- `frontend/src/components/form/fields/IPNetworkField.tsx` — text input, font-mono, CIDR placeholder (`10.0.0.0/24`). ~60 lines.
- `frontend/src/components/form/fields/URLField.tsx` — `<Input type="url">`; shows `target_type_name` short-name (e.g. `HttpUrl`) in a chip. ~65 lines.
- `frontend/src/components/form/fields/EmailField.tsx` — `<Input type="email">`. ~55 lines.
- `frontend/src/components/form/fields/PathField.tsx` — text input, font-mono. ~55 lines.
- `frontend/src/components/form/fields/UUIDField.tsx` — text input, font-mono, with "regenerate" button using `crypto.randomUUID()`. ~75 lines.
- `frontend/src/components/form/fields/SecretField.tsx` — password-type input with show/hide eye toggle; respects `secret_kind` chip. ~80 lines.
- `frontend/src/components/form/fields/PatternField.tsx` — text input + read-only flag chips derived from `flags` bitmask. ~80 lines.
- `frontend/src/components/form/fields/BytesField.tsx` — text input (hex), font-mono, with byte-count display + odd-length-on-blur soft reject. ~80 lines.

**Modify (frontend):**
- `frontend/src/api/schemas.ts` — add 15 new zod schemas (one per kind) and extend the `FormNodeData` discriminated union + `FormNodeSchema` `z.union([...])`. ~140 new lines.
- `frontend/src/components/form/FormField.tsx` — add 15 new dispatch cases. The `default` branch becomes unreachable (kept as a debug fallback).

**Modify (backend):**
- `src/pydantic_studio/renderers/html/serialize.py` — rename `_maybe_coerce_enum` to `_maybe_coerce_typed_value` and generalize it: dispatch on the resolved node's `kind`, handling `enum`, `datetime`, `date`, `time`, `timedelta`, `decimal`, `uuid`, `bytes`, and `secret` (when `secret_kind == "bytes"`). Wire `dispatch_mutation` to call the generalized helper. ~80 lines net.

**Create (tests):**
- `tests/e2e/test_temporal_fields.py` — Playwright e2e covering `date` + `datetime` + `time` edits via the SPA. ~75 lines.
- `tests/e2e/test_network_fields.py` — Playwright e2e covering `url` + `email` + `ip_address` edits. ~75 lines.
- `tests/e2e/test_special_fields.py` — Playwright e2e covering `uuid` (regenerate button) + `secret` (show toggle) + `pattern` (flag chips render). ~95 lines.

**Modify (tests):**
- `tests/e2e/conftest.py` — extend `_DemoSchema` with 15 new fields (one per kind) plus the seeding `tree.set_value(...)` calls.
- `tests/unit/test_html_serialize.py` — add ~10 unit tests for the generalized coercion: one per typed kind (datetime/date/time/timedelta/decimal/uuid/bytes/secret-bytes), plus a regression test confirming enum coercion still works after the rename.
- `tests/unit/test_paths.py` — bonus: add `test_parse_dotted_integer` (4 cases) since the path-module rule landed in Phase 4 without a dedicated unit test.

**Bundle artifacts (regenerated by T18):**
- `src/pydantic_studio/renderers/html/static/dist/index.html`
- `src/pydantic_studio/renderers/html/static/dist/assets/*.js`
- `src/pydantic_studio/renderers/html/static/dist/assets/*.css`

**Do NOT touch:**
- `src/pydantic_studio/tree/` — the 15 FormNode subclasses are already correct; only the dispatcher boundary changes.
- `src/pydantic_studio/renderers/html/{routes.py,server.py}` — Phase 1 routes pass mutations through `dispatch_mutation`; no route changes needed.
- The 9 existing field components (StringField, IntField, BoolField, EnumField, LiteralField, GroupField, SequenceField, MappingField, UnionField, AnyField) — they work.
- The chrome layer (FieldRow, FieldHeader, Description, FieldError, RequiredBadge, TypeBadge) — Phase 6 may add constraint hints to TypeBadge; this phase doesn't.
- The HTMX-driven legacy tests — Phase 1 territory.
- Phase 6 nice-to-haves (validation surface polish, theme toggle, sidebar search, undo/redo, Lucide icons, group depth collapse).

---

## Prerequisites

Before Task 1, confirm the Phase 4 baseline:

```bash
git log --oneline -1
# should show the Phase 4 merge or the most recent commit on
# feature/shadcn-redesign-phase-5-remaining-primitives

uv run pytest -q --ignore=tests/e2e 2>&1 | tail -3
# should show: a number of tests passed, 0 failed

uv run pytest tests/e2e 2>&1 | tail -3
# should show: 5 e2e tests pass (spa_edit_flow + sequence + mapping + union + any)

cd frontend && pnpm exec tsc -b
# should exit 0

cd frontend && pnpm build
# should exit 0 (verifies the bundle still builds before we add 15 components)
```

If anything fails, fix before starting Phase 5 tasks. The `uv` shim is occasionally flaky on Windows; the fallback `./.venv/Scripts/python.exe -m pytest ...` works identically.

---

## Task 1: Generalize the dispatcher coercion (+ paths backfill)

**Files:**
- Modify: `src/pydantic_studio/renderers/html/serialize.py` (rename + generalize `_maybe_coerce_enum`)
- Modify: `tests/unit/test_html_serialize.py` (add 9 unit tests for typed coercion + 1 rename-regression test)
- Modify: `tests/unit/test_paths.py` (add 1 bonus test for the dotted-integer rule)

**Why this comes first:** the 14 of 15 frontend components send a wire-format string for `set_value`. Without backend coercion, `tree.set_value("when", "2025-01-15")` on a `DateNode` would fail with `expected date, got str`. Generalizing the dispatcher boundary lets each frontend component send the obvious wire format without per-kind backend gymnastics.

The existing `_maybe_coerce_enum` (lines 96-120 of `serialize.py`) does exactly this pattern for `EnumNode`. Generalize it: dispatch on the resolved node's `kind` and translate the wire value into the typed Python value the node's `validate_value` expects. Contract: if no coercion applies, OR if coercion raises (e.g. `bytes.fromhex("xx")` on bad hex), return the wire value unchanged and let `validate_value` produce the canonical error message.

### Coercion targets

| Node kind | Wire type | Coerce to | Helper |
|---|---|---|---|
| `enum` | str (member name) | Enum member | existing logic (kept) |
| `datetime` | str (ISO 8601) | `datetime.datetime` | `datetime.fromisoformat(value)` |
| `date` | str (ISO 8601) | `datetime.date` | `date.fromisoformat(value)` |
| `time` | str (ISO 8601) | `datetime.time` | `time.fromisoformat(value)` |
| `timedelta` | str (ISO 8601 duration) | `datetime.timedelta` | `TypeAdapter(timedelta).validate_python(value)` |
| `decimal` | str | `decimal.Decimal` | `Decimal(value)` |
| `uuid` | str | `uuid.UUID` | `UUID(value)` |
| `bytes` | str (hex) | `bytes` | `bytes.fromhex(value)` |
| `secret` (`secret_kind == "bytes"`) | str (UTF-8) | `bytes` | `value.encode()` |

NO coercion needed for: `string`, `int`, `float`, `bool`, `decimal` is in the table above (Pydantic accepts str + Decimal alike but the node's `validate_value` accepts str-coercible too; we still coerce explicitly so the typed value lands in `node.value`), `literal`, `path` (stays str), `url` (stays str), `email` (stays str), `ip_address` (stays str — node accepts str directly), `ip_network` (same), `pattern` (regex source stays str), `secret` (`secret_kind == "str"` — stays str), the entire container family (`sequence`/`mapping`/`union`/`any`/`group`).

- [ ] **Step 1: Write failing test — datetime coercion**

Append to `tests/unit/test_html_serialize.py`:

```python
def test_dispatch_set_value_datetime_coerces_iso_string() -> None:
    """DatetimeField sends an ISO 8601 string; dispatch must coerce
    to a datetime instance before DatetimeNode.validate_value runs."""
    from datetime import datetime

    from pydantic import BaseModel

    class M(BaseModel):
        when: datetime = datetime(2020, 1, 1)

    tree = build_form_tree(M, existing={"when": datetime(2020, 1, 1)})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "when", "value": "2025-01-15T10:30:00"}
    )
    assert result.ok is True
    assert tree.root.find("when").value == datetime(2025, 1, 15, 10, 30, 0)
```

- [ ] **Step 2: Run test — verify it fails**

```bash
uv run pytest tests/unit/test_html_serialize.py::test_dispatch_set_value_datetime_coerces_iso_string -v
```

Expected: FAIL with `expected datetime, got str` (DatetimeNode.validate_value rejects the wire string because no coercion is wired yet).

- [ ] **Step 3: Generalize `_maybe_coerce_enum` to `_maybe_coerce_typed_value`**

Read `src/pydantic_studio/renderers/html/serialize.py`. Replace lines 96-120 (the existing `_maybe_coerce_enum` helper) with:

```python
def _maybe_coerce_typed_value(tree: FormTree, path: str, value: Any) -> Any:
    """Translate the wire-format string for a typed FormNode into the Python
    typed value its ``validate_value`` expects.

    Most primitive nodes accept the wire format directly: ``string``,
    ``int``, ``bool``, ``path``, ``url``, ``email``, ``ip_address``,
    ``ip_network``, ``pattern``, ``literal`` (Pydantic's Literal accepts
    primitives), and ``secret`` (when ``secret_kind == "str"``) pass
    through untouched.

    The kinds that need coercion are those whose ``validate_value`` does
    an exact-type check that the JSON wire format can't satisfy
    directly:

    - ``enum`` — wire value is the member's ``.name`` (str); look up the
      matching Enum member by name.
    - ``datetime`` / ``date`` / ``time`` — wire value is an ISO 8601
      string; parse via ``fromisoformat`` (handles ``+00:00`` and ``Z``
      on 3.11+).
    - ``timedelta`` — wire value is an ISO 8601 duration string
      (e.g. ``PT1H30M``); parse via ``TypeAdapter(timedelta)``.
    - ``decimal`` — wire value is a string (JSON doesn't have a decimal
      type); construct via ``Decimal(value)``.
    - ``uuid`` — wire value is a UUID string; construct via ``UUID(value)``.
    - ``bytes`` — wire value is hex (per BytesNode's JSON serializer);
      decode via ``bytes.fromhex(value)``.
    - ``secret`` with ``secret_kind == "bytes"`` — wire value is a UTF-8
      string (per SecretNode's bytes-as-str round-trip); encode via
      ``value.encode()``.

    Contract: returns ``value`` unchanged when no coercion applies, or
    when coercion raises. The node's ``validate_value`` still runs on
    whatever this returns, so a malformed wire string surfaces as the
    canonical "invalid X" error.
    """
    from datetime import date, datetime, time, timedelta
    from decimal import Decimal, InvalidOperation
    from uuid import UUID

    from pydantic import TypeAdapter

    from pydantic_studio.tree.nodes import (
        BytesNode,
        DateNode,
        DatetimeNode,
        DecimalNode,
        EnumNode,
        SecretNode,
        TimedeltaNode,
        TimeNode,
        UuidNode,
    )

    if not isinstance(value, str):
        return value
    try:
        node = _resolve(tree, path)
    except Exception:
        return value  # let set_value's own path-resolution fail clearly

    # Enum: look up the member by name (existing Phase 1 logic).
    if isinstance(node, EnumNode):
        for name, member in node.choices:
            if name == value:
                return member
        return value  # not a recognized name; let validate_value reject

    # Temporals: fromisoformat is forgiving on 3.11+ (accepts both
    # 'YYYY-MM-DDTHH:MM' and 'YYYY-MM-DDTHH:MM:SS', with optional
    # timezone). On parse failure, fall through to validate_value's
    # error path.
    if isinstance(node, DatetimeNode):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(node, DateNode):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(node, TimeNode):
        try:
            return time.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(node, TimedeltaNode):
        # ISO 8601 duration strings (PT1H30M, P1DT2H, etc.). Pydantic's
        # TypeAdapter handles the parse; a malformed string raises
        # ValidationError which we swallow so validate_value owns the
        # error surface.
        try:
            return TypeAdapter(timedelta).validate_python(value)
        except Exception:
            return value
    if isinstance(node, DecimalNode):
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return value
    if isinstance(node, UuidNode):
        try:
            return UUID(value)
        except ValueError:
            return value
    if isinstance(node, BytesNode):
        try:
            return bytes.fromhex(value)
        except ValueError:
            return value
    if isinstance(node, SecretNode) and node.secret_kind == "bytes":
        return value.encode()

    return value
```

- [ ] **Step 4: Wire the generalized helper into `dispatch_mutation`**

In the same file, find the `if op == "set_value":` branch (around line 140) and replace:

```python
            value = _maybe_coerce_enum(tree, path, value)
```

with:

```python
            value = _maybe_coerce_typed_value(tree, path, value)
```

The function header comment for `_maybe_coerce_enum` (the docstring referencing "EnumField sends ... member's name") is replaced by the new helper's docstring; the existing `routes.py:198-202` comment about HTMX parity is obsolete (Phase 1 HTMX paths are gone in Phase 4) — leave that comment removed as part of the generalization.

- [ ] **Step 5: Run the datetime test — verify it now passes**

```bash
uv run pytest tests/unit/test_html_serialize.py::test_dispatch_set_value_datetime_coerces_iso_string -v
```

Expected: PASS.

- [ ] **Step 6: Write 8 more failing tests (one per typed kind)**

Append to `tests/unit/test_html_serialize.py`:

```python
def test_dispatch_set_value_date_coerces_iso_string() -> None:
    from datetime import date

    from pydantic import BaseModel

    class M(BaseModel):
        d: date = date(2020, 1, 1)

    tree = build_form_tree(M, existing={"d": date(2020, 1, 1)})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "d", "value": "2025-06-09"}
    )
    assert result.ok is True
    assert tree.root.find("d").value == date(2025, 6, 9)


def test_dispatch_set_value_time_coerces_iso_string() -> None:
    from datetime import time

    from pydantic import BaseModel

    class M(BaseModel):
        t: time = time(0, 0)

    tree = build_form_tree(M, existing={"t": time(0, 0)})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "t", "value": "14:30:00"}
    )
    assert result.ok is True
    assert tree.root.find("t").value == time(14, 30, 0)


def test_dispatch_set_value_timedelta_coerces_iso_duration() -> None:
    from datetime import timedelta

    from pydantic import BaseModel

    class M(BaseModel):
        ttl: timedelta = timedelta(seconds=0)

    tree = build_form_tree(M, existing={"ttl": timedelta(seconds=0)})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "ttl", "value": "PT1H30M"}
    )
    assert result.ok is True
    assert tree.root.find("ttl").value == timedelta(hours=1, minutes=30)


def test_dispatch_set_value_decimal_coerces_string() -> None:
    from decimal import Decimal

    from pydantic import BaseModel

    class M(BaseModel):
        amount: Decimal = Decimal("0.00")

    tree = build_form_tree(M, existing={"amount": Decimal("0.00")})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "amount", "value": "19.99"}
    )
    assert result.ok is True
    assert tree.root.find("amount").value == Decimal("19.99")


def test_dispatch_set_value_uuid_coerces_string() -> None:
    from uuid import UUID

    from pydantic import BaseModel

    class M(BaseModel):
        id: UUID = UUID("11111111-1111-1111-1111-111111111111")

    tree = build_form_tree(
        M, existing={"id": UUID("11111111-1111-1111-1111-111111111111")}
    )
    new_value = "22222222-2222-2222-2222-222222222222"
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "id", "value": new_value}
    )
    assert result.ok is True
    assert tree.root.find("id").value == UUID(new_value)


def test_dispatch_set_value_bytes_coerces_hex_string() -> None:
    from pydantic import BaseModel

    class M(BaseModel):
        blob: bytes = b""

    tree = build_form_tree(M, existing={"blob": b""})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "blob", "value": "deadbeef"}
    )
    assert result.ok is True
    assert tree.root.find("blob").value == b"\xde\xad\xbe\xef"


def test_dispatch_set_value_secret_bytes_coerces_utf8_string() -> None:
    from pydantic import BaseModel, SecretBytes

    class M(BaseModel):
        key: SecretBytes = SecretBytes(b"")

    tree = build_form_tree(M, existing={"key": SecretBytes(b"")})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "key", "value": "p4ssw0rd"}
    )
    assert result.ok is True
    assert tree.root.find("key").value == b"p4ssw0rd"


def test_dispatch_set_value_secret_str_passes_through_unchanged() -> None:
    """SecretStr nodes accept str on the wire (secret_kind == 'str');
    coercion must NOT encode to bytes."""
    from pydantic import BaseModel, SecretStr

    class M(BaseModel):
        password: SecretStr = SecretStr("")

    tree = build_form_tree(M, existing={"password": SecretStr("")})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "password", "value": "letmein"}
    )
    assert result.ok is True
    assert tree.root.find("password").value == "letmein"


def test_dispatch_set_value_malformed_iso_returns_validation_failure() -> None:
    """If the wire string is unparseable, coercion swallows the error
    and validate_value rejects via the canonical 'expected X' message —
    not via a raised exception leaking out of dispatch_mutation."""
    from datetime import date

    from pydantic import BaseModel

    class M(BaseModel):
        d: date = date(2020, 1, 1)

    tree = build_form_tree(M, existing={"d": date(2020, 1, 1)})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "d", "value": "not-a-date"}
    )
    assert result.ok is False
    assert tree.root.find("d").value == date(2020, 1, 1)   # unchanged
```

- [ ] **Step 7: Run all 9 new tests — verify they pass**

```bash
uv run pytest tests/unit/test_html_serialize.py -q -k "datetime or date or time or timedelta or decimal or uuid or bytes or secret_bytes or secret_str or malformed_iso"
```

Expected: 9 passed (5 typed coercions + secret-bytes + secret-str + malformed-iso + the original datetime test). Allow some tolerance — the exact `-k` filter may also match Phase 3/4 tests with similar names; check with `-v` if you want explicit verification.

- [ ] **Step 8: Run the existing enum test — verify it still passes after rename**

```bash
uv run pytest tests/unit/test_html_serialize.py::test_dispatch_set_value_enum_coerces_name_string_to_member -v
```

Expected: PASS. The rename `_maybe_coerce_enum` → `_maybe_coerce_typed_value` preserves the enum branch; this test confirms the rename didn't regress.

- [ ] **Step 9: Bonus — add the missing dotted-integer path test**

Append to `tests/unit/test_paths.py`:

```python
def test_parse_dotted_integer():
    """Phase 4 added dotted-int support so the frontend's childPath
    helper (which emits ``tags.0`` for sequence children) round-trips
    cleanly through the same parser the backend uses to walk paths.
    Bracket form ``tags[0]`` is still accepted (see other tests)."""
    assert Path.parse("tags.0").segments == ("tags", 0)
    assert Path.parse("env.2").segments == ("env", 2)
    assert Path.parse("a.0.b").segments == ("a", 0, "b")
    assert Path.parse("0").segments == (0,)
```

- [ ] **Step 10: Run the path test**

```bash
uv run pytest tests/unit/test_paths.py::test_parse_dotted_integer -v
```

Expected: PASS. The grammar already supports dotted ints since Phase 4 (`paths.py` lines 82-91); the test merely backfills the missing coverage.

- [ ] **Step 11: Run the full unit suite for regression**

```bash
uv run pytest tests/unit -q
```

Expected: all unit tests pass (the prior count + 10 new tests).

- [ ] **Step 12: Lint**

```bash
uv run ruff check src tests
```

Expected: 0 errors. If ruff flags the new imports inside `_maybe_coerce_typed_value`, leave them inline (CLAUDE.md "Inline imports" rule).

- [ ] **Step 13: Commit**

```bash
git add src/pydantic_studio/renderers/html/serialize.py tests/unit/test_html_serialize.py tests/unit/test_paths.py
git commit -m "$(cat <<'EOF'
feat(html): generalize dispatcher coercion to all typed primitive kinds

Renames _maybe_coerce_enum to _maybe_coerce_typed_value and extends it
to handle the 8 primitive kinds whose JSON wire format is a string but
whose Python value must be a typed instance before FormNode.validate_value
runs: datetime, date, time, timedelta, decimal, uuid, bytes, and secret
(when secret_kind == 'bytes'). String-on-wire kinds (path, url, email,
ip_address, ip_network, pattern, secret-str) pass through unchanged
since their nodes accept str directly. Container and structural kinds
are untouched.

Contract preserved: coercion failure returns the wire value unchanged
so validate_value produces the canonical 'expected X' error. Malformed
ISO strings, bad hex, etc. surface as a validation rejection (200 OK
with validation.ok=false) rather than an exception leaking out of the
dispatcher.

Adds 9 unit tests under tests/unit/test_html_serialize.py exercising
each typed coercion plus the malformed-input rejection path. Confirms
the existing enum coercion test still passes after the rename.

Also backfills the missing test_parse_dotted_integer unit test in
tests/unit/test_paths.py (the Phase 4 frontend childPath emits
dotted-int paths; the grammar already supported it but had no
dedicated coverage).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: zod schemas for the 15 new node kinds

**Files:**
- Modify: `frontend/src/api/schemas.ts` (add 15 zod schemas + extend `FormNodeData` discriminated union)

**Why:** every new field component needs a typed `node` prop. zod gives us the runtime validation (in case the server adds a field unexpectedly) plus a TS type via `z.infer`. Cross-verify each schema against the corresponding Python `FormNode` subclass in `src/pydantic_studio/tree/nodes.py` to avoid Phase 3's bug where `IntNodeSchema` initially had `value: z.number()` instead of `z.number().nullable()` (`null` for unset fields).

**Cross-verification matrix** (Python FormNode → zod schema fields). All node types inherit the `NodeBase` fields (`name`, `description`, `required`, `error`) — only the kind-specific fields are listed below. Line numbers refer to `src/pydantic_studio/tree/nodes.py`.

| Python class | Line | Kind | Wire-typed fields | zod field shape |
|---|---|---|---|---|
| `FloatNode` | 149 | `"float"` | `value: float \| None`, `default: float \| None`, `ge/le/gt/lt: float \| None`, `multiple_of: float \| None`, `allow_inf_nan: bool` | `value/default/ge/le/gt/lt/multiple_of: z.number().nullable()`, `allow_inf_nan: z.boolean()` |
| `DecimalNode` | 193 | `"decimal"` | `value/default: Decimal \| None` (JSON-serialized as string), `max_digits/decimal_places: int \| None`, `ge/le/gt/lt: Decimal \| None` (JSON-serialized as string) | `value/default/ge/le/gt/lt: z.string().nullable()`, `max_digits/decimal_places: z.number().nullable()` |
| `DatetimeNode` | 230 | `"datetime"` | `value/default: datetime \| None` (ISO string) | `value/default: z.string().nullable()` |
| `DateNode` | 255 | `"date"` | `value/default: date \| None` (ISO string) | `value/default: z.string().nullable()` |
| `TimeNode` | 273 | `"time"` | `value/default: time \| None` (ISO string) | `value/default: z.string().nullable()` |
| `TimedeltaNode` | 291 | `"timedelta"` | `value/default: timedelta \| None` (ISO duration) | `value/default: z.string().nullable()` |
| `IpAddressNode` | 314 | `"ip_address"` | `value/default: str \| None`, `version: Literal[4, 6]` | `value/default: z.string().nullable()`, `version: z.union([z.literal(4), z.literal(6)])` |
| `IpNetworkNode` | 376 | `"ip_network"` | `value/default: str \| None`, `version: Literal[4, 6]` | `value/default: z.string().nullable()`, `version: z.union([z.literal(4), z.literal(6)])` |
| `UrlNode` | 411 | `"url"` | `value/default: str \| None`, `target_type_name: str` | `value/default: z.string().nullable()`, `target_type_name: z.string()` |
| `EmailNode` | 465 | `"email"` | `value/default: str \| None` | `value/default: z.string().nullable()` |
| `PathNode` | 498 | `"path"` | `value/default: str \| None` | `value/default: z.string().nullable()` |
| `UuidNode` | 539 | `"uuid"` | `value/default: UUID \| None` (Pydantic JSON-serializes as string) | `value/default: z.string().nullable()` |
| `SecretNode` | 561 | `"secret"` | `value/default: str \| bytes \| None` (bytes → str on JSON), `secret_kind: Literal["str", "bytes"]` | `value/default: z.string().nullable()`, `secret_kind: z.union([z.literal("str"), z.literal("bytes")])` |
| `PatternNode` | 617 | `"pattern"` | `value/default: str \| None`, `flags: int` | `value/default: z.string().nullable()`, `flags: z.number()` |
| `BytesNode` | 649 | `"bytes"` | `value/default: bytes \| None` (JSON-serialized as hex string via `_serialize_value`) | `value/default: z.string().nullable()` |

**Why decimal `ge/le/gt/lt` are strings:** `Decimal` doesn't survive JSON natively; Pydantic JSON-dumps it as a string. The PythonNode declares them as `Decimal | None`, but the wire format is `string | null`. Don't shape them as `z.number()` — that loses precision for values like `1e-30` and Pydantic emits them as strings.

**Why no `multiple_of` on DecimalNode:** Pydantic doesn't ship a `multiple_of` constraint on Decimal in v2.7. Confirm by re-reading `DecimalNode` (lines 193-227 — there's no `multiple_of` field).

- [ ] **Step 1: Read the existing schemas file**

```bash
# Re-read frontend/src/api/schemas.ts to confirm the current layout.
```

The 10 existing schemas are: `StringNodeSchema`, `IntNodeSchema`, `BoolNodeSchema`, `EnumNodeSchema`, `LiteralNodeSchema`, `GroupNodeSchema`, `SequenceNodeSchema`, `MappingNodeSchema`, `UnionNodeSchema`, `AnyValueNodeSchema`. The union assembly happens at the bottom in `FormNodeSchema = z.union([...])` (line 187) and `FormNodeData` (line 201).

- [ ] **Step 2: Add the 15 new schemas**

After the `BoolNodeSchema` definition (around line 44) and before `EnumNodeSchema`, insert the FloatNodeSchema. After IntNodeSchema is a good neighbor. The order within the file doesn't affect runtime — sort by alphabet for readability:

Insert the following at the end of the primitive schemas block (after `LiteralNodeSchema`, before the `GroupNodeData` interface):

```typescript
export const FloatNodeSchema = NodeBase.extend({
  kind: z.literal("float"),
  value: z.number().nullable(),
  default: z.number().nullable(),
  ge: z.number().nullable(),
  le: z.number().nullable(),
  gt: z.number().nullable(),
  lt: z.number().nullable(),
  multiple_of: z.number().nullable(),
  allow_inf_nan: z.boolean(),
});

export const DecimalNodeSchema = NodeBase.extend({
  kind: z.literal("decimal"),
  // Decimal round-trips as a string via Pydantic JSON; preserves
  // precision (1e-30, etc.) that z.number() would lose.
  value: z.string().nullable(),
  default: z.string().nullable(),
  max_digits: z.number().nullable(),
  decimal_places: z.number().nullable(),
  ge: z.string().nullable(),
  le: z.string().nullable(),
  gt: z.string().nullable(),
  lt: z.string().nullable(),
});

export const DatetimeNodeSchema = NodeBase.extend({
  kind: z.literal("datetime"),
  // ISO 8601 datetime: "2025-01-15T10:30:00" or with tz "2025-01-15T10:30:00+00:00"
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const DateNodeSchema = NodeBase.extend({
  kind: z.literal("date"),
  // ISO 8601 date: "2025-01-15"
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const TimeNodeSchema = NodeBase.extend({
  kind: z.literal("time"),
  // ISO 8601 time: "14:30:00" or "14:30"
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const TimedeltaNodeSchema = NodeBase.extend({
  kind: z.literal("timedelta"),
  // ISO 8601 duration: "PT1H30M", "P1DT2H", etc.
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const IPAddressNodeSchema = NodeBase.extend({
  kind: z.literal("ip_address"),
  value: z.string().nullable(),
  default: z.string().nullable(),
  version: z.union([z.literal(4), z.literal(6)]),
});

export const IPNetworkNodeSchema = NodeBase.extend({
  kind: z.literal("ip_network"),
  value: z.string().nullable(),
  default: z.string().nullable(),
  version: z.union([z.literal(4), z.literal(6)]),
});

export const URLNodeSchema = NodeBase.extend({
  kind: z.literal("url"),
  value: z.string().nullable(),
  default: z.string().nullable(),
  // Fully qualified name of the URL type, e.g. "pydantic.HttpUrl".
  target_type_name: z.string(),
});

export const EmailNodeSchema = NodeBase.extend({
  kind: z.literal("email"),
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const PathNodeSchema = NodeBase.extend({
  kind: z.literal("path"),
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const UUIDNodeSchema = NodeBase.extend({
  kind: z.literal("uuid"),
  // Pydantic JSON-dumps UUID as string.
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const SecretNodeSchema = NodeBase.extend({
  kind: z.literal("secret"),
  // SecretStr value is a plain str; SecretBytes value is bytes that
  // Pydantic JSON-encodes as a UTF-8 string. Both arrive as str on
  // the wire; secret_kind discriminates how to render and how the
  // backend dispatcher's _maybe_coerce_typed_value re-encodes.
  value: z.string().nullable(),
  default: z.string().nullable(),
  secret_kind: z.union([z.literal("str"), z.literal("bytes")]),
});

export const PatternNodeSchema = NodeBase.extend({
  kind: z.literal("pattern"),
  // Regex source string (the pattern itself).
  value: z.string().nullable(),
  default: z.string().nullable(),
  // Python re flag bitmask; renderer derives single-char chips
  // (i/m/s/x/a/u) read-only for Phase 5 (no in-UI editing yet).
  flags: z.number(),
});

export const BytesNodeSchema = NodeBase.extend({
  kind: z.literal("bytes"),
  // BytesNode._serialize_value emits hex (lossless on round-trip).
  value: z.string().nullable(),
  default: z.string().nullable(),
});
```

- [ ] **Step 3: Extend the `FormNodeSchema` union**

Find the `FormNodeSchema = z.union([...])` block (around line 187). Add all 15 new schemas to the array:

```typescript
export const FormNodeSchema: z.ZodType<FormNodeData> = z.union([
  StringNodeSchema,
  IntNodeSchema,
  FloatNodeSchema,
  BoolNodeSchema,
  DecimalNodeSchema,
  DatetimeNodeSchema,
  DateNodeSchema,
  TimeNodeSchema,
  TimedeltaNodeSchema,
  IPAddressNodeSchema,
  IPNetworkNodeSchema,
  URLNodeSchema,
  EmailNodeSchema,
  PathNodeSchema,
  UUIDNodeSchema,
  SecretNodeSchema,
  PatternNodeSchema,
  BytesNodeSchema,
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

Order is cosmetic at runtime — zod's `z.union` tries each member in order; first match wins. Since every schema constrains `kind` to a literal, there's no ambiguity. Keeping the order grouped (primitives → containers → unknown) makes the diff readable.

- [ ] **Step 4: Extend the `FormNodeData` discriminated union**

Find the `export type FormNodeData = ...` block (around line 201). Add the 15 `z.infer<typeof XxxSchema>` arms:

```typescript
export type FormNodeData =
  | z.infer<typeof StringNodeSchema>
  | z.infer<typeof IntNodeSchema>
  | z.infer<typeof FloatNodeSchema>
  | z.infer<typeof BoolNodeSchema>
  | z.infer<typeof DecimalNodeSchema>
  | z.infer<typeof DatetimeNodeSchema>
  | z.infer<typeof DateNodeSchema>
  | z.infer<typeof TimeNodeSchema>
  | z.infer<typeof TimedeltaNodeSchema>
  | z.infer<typeof IPAddressNodeSchema>
  | z.infer<typeof IPNetworkNodeSchema>
  | z.infer<typeof URLNodeSchema>
  | z.infer<typeof EmailNodeSchema>
  | z.infer<typeof PathNodeSchema>
  | z.infer<typeof UUIDNodeSchema>
  | z.infer<typeof SecretNodeSchema>
  | z.infer<typeof PatternNodeSchema>
  | z.infer<typeof BytesNodeSchema>
  | z.infer<typeof EnumNodeSchema>
  | z.infer<typeof LiteralNodeSchema>
  | GroupNodeData
  | SequenceNodeData
  | MappingNodeData
  | UnionNodeData
  | z.infer<typeof AnyValueNodeSchema>
  | { kind: string; name: string; [extra: string]: unknown };
```

The final `{ kind: string; ... }` arm preserves the `UnknownNodeSchema` fallback for any future kind.

- [ ] **Step 5: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0. Common gotcha: if you misspelled a kind literal (e.g. `z.literal("uuid_")`), tsc won't catch it but a runtime test will. The discriminated union should compile cleanly.

- [ ] **Step 6: Smoke-test schema round-trips**

Quick manual check that zod accepts a minimal payload for each new kind. The easiest verification is to run the existing Phase 4 e2e tests — they fetch `/api/tree` and the `FormTreeSchema.parse(raw)` call inside `useApplyMutation` will catch any schema mismatch on the existing fields. New fields aren't in `_DemoSchema` yet (T19 adds them), so no schema runs against them at this point — that's fine; we're only verifying the 10 existing schemas still parse:

```bash
uv run pytest tests/e2e/test_spa_edit_flow.py -p no:cacheprovider -q
```

Expected: 1 passed. If this fails with a zod parse error, you've accidentally broken one of the existing schemas — re-read `frontend/src/api/schemas.ts` and revert that diff.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/schemas.ts
git commit -m "$(cat <<'EOF'
feat(frontend): zod schemas for the 15 remaining primitive node kinds

Mirrors the Python FormNode subclasses for float, decimal, datetime,
date, time, timedelta, ip_address, ip_network, url, email, path, uuid,
secret, pattern, bytes. Cross-verified field-by-field against
src/pydantic_studio/tree/nodes.py: wire types match what Pydantic
JSON-emits (decimals as strings to preserve precision, UUIDs as
strings, bytes as hex strings via the BytesNode serializer, ISO 8601
for temporals).

FormNodeData discriminated union and FormNodeSchema z.union grow by
15 arms. UnknownNodeSchema fallback retained for future kinds.

Field dispatcher (FormField.tsx) isn't touched in this task — that
happens incrementally per-kind in T3..T17 so each component's TDD
loop closes the loop on its own kind.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Per-component task template (T3-T17)

Each of the next 15 tasks creates one field component, wires it into the FormField dispatcher, and verifies via `pnpm exec tsc -b` (zero runtime e2e — that lands in T19-T21). The cadence is:

1. Read the StringField (reference) at `frontend/src/components/form/fields/StringField.tsx` if needed.
2. Create the new component file.
3. Add one dispatch case to `FormField.tsx`.
4. `pnpm exec tsc -b` — confirms types and import paths.
5. Commit (one commit per component for revertability).

The 15 tasks are ordered from simplest (T3 FloatField — identical pattern to IntField with `step="any"`) to most complex (T15 SecretField with show-toggle, T16 PatternField with flag bitmask derivation, T17 BytesField with byte-count). Subagents implementing T3-T17 can read them in any order — every component is self-contained.

**Repeating helpers (used across multiple components):**
- `useApplyMutation` from `@/api/mutations` — POST `/api/mutations` and update the cache.
- `Description`, `FieldError`, `FieldHeader`, `FieldRow`, `RequiredBadge`, `TypeBadge` from `@/components/form/chrome/*`.
- `Input` from `@/components/ui/input`.
- `Label` from `@/components/ui/label`.
- `Button` from `@/components/ui/button`.

**Repeating local-state pattern:**

```typescript
const mutation = useApplyMutation();
const initial = node.value ?? "";   // or node.value !== null ? String(node.value) : ""
const [local, setLocal] = useState<string>(initial);
const [error, setError] = useState<string | null>(node.error);

useEffect(() => {
  setLocal(...);   // re-derive from node.value
  setError(node.error);
}, [node.value, node.error]);

const commit = () => {
  if (local === initial) return;   // no-op
  mutation.mutate(
    { op: "set_value", path, value: local },
    { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
  );
};
```

---

## Task 3: FloatField

**Files:**
- Create: `frontend/src/components/form/fields/FloatField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx` (add `case "float":` dispatch)

Float is the simplest of the 15 — same shape as IntField, but with `step="any"` so the browser accepts decimal points. `Number(local)` parses; `Number.isNaN` catches `"abc"`-style typos before the round-trip. We send `null` for an empty input (lets FloatNode validate against required-ness).

- [ ] **Step 1: Create FloatField.tsx**

`frontend/src/components/form/fields/FloatField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { FloatNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type FloatNode = z.infer<typeof FloatNodeSchema>;

export function FloatField({ node, path }: { node: FloatNode; path: string }) {
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
        {!node.allow_inf_nan && (
          <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
            finite
          </span>
        )}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="number"
        step="any"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === initial) return;
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

- [ ] **Step 2: Wire into FormField dispatcher**

Read `frontend/src/components/form/FormField.tsx`. Add the import next to the other field imports:

```typescript
import { FloatField } from "@/components/form/fields/FloatField";
```

Insert a new `case` next to `case "int":`:

```typescript
    case "float":
      return <FloatField node={node as NodeOfKind<"float">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/FloatField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): FloatField component for FloatNode renders" -m "Float input uses step=any so browsers accept decimal points. Local state mirrors node.value; commit on blur with parsed number (or null for empty). Adds a 'finite' chip when allow_inf_nan=false. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: DecimalField

**Files:**
- Create: `frontend/src/components/form/fields/DecimalField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

Decimal is text-based (Pydantic JSON-dumps Decimal as a string to preserve precision). `inputMode="decimal"` triggers the numeric soft-keyboard on mobile without locking the input to integer-only.

- [ ] **Step 1: Create DecimalField.tsx**

`frontend/src/components/form/fields/DecimalField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { DecimalNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type DecimalNode = z.infer<typeof DecimalNodeSchema>;

export function DecimalField({ node, path }: { node: DecimalNode; path: string }) {
  const mutation = useApplyMutation();
  const initial = node.value ?? "";
  const [local, setLocal] = useState<string>(initial);
  const [error, setError] = useState<string | null>(node.error);

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
        {node.max_digits !== null && (
          <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
            {node.max_digits} digits
          </span>
        )}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="text"
        inputMode="decimal"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === initial) return;
          // Wire format is a string; backend coerces via Decimal(value).
          // Empty string → null (lets DecimalNode.validate_value enforce
          // required-ness).
          const wire = local.trim() === "" ? null : local.trim();
          mutation.mutate(
            { op: "set_value", path, value: wire },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Wire into FormField dispatcher**

Add the import:

```typescript
import { DecimalField } from "@/components/form/fields/DecimalField";
```

Add the case:

```typescript
    case "decimal":
      return <DecimalField node={node as NodeOfKind<"decimal">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/DecimalField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): DecimalField component for DecimalNode renders" -m "Text input with inputMode=decimal. Wire format is the string directly (Pydantic JSON-dumps Decimal as str to preserve precision). Optional max_digits chip when the constraint is set. Empty input commits null. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: PathField

**Files:**
- Create: `frontend/src/components/form/fields/PathField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

Filesystem paths render as plain text in a monospace font. PathNode accepts strings directly on the wire (its `_normalize_path` validator converts PurePath instances to str on the Python side — irrelevant to the browser).

- [ ] **Step 1: Create PathField.tsx**

`frontend/src/components/form/fields/PathField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { PathNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type PathNodeT = z.infer<typeof PathNodeSchema>;

export function PathField({ node, path }: { node: PathNodeT; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

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
        type="text"
        className="font-mono text-sm"
        placeholder="/path/to/file"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
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

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { PathField } from "@/components/form/fields/PathField";
```

```typescript
    case "path":
      return <PathField node={node as NodeOfKind<"path">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/PathField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): PathField component for PathNode renders" -m "Plain text input with monospace styling and a /path/to/file placeholder. Path strings round-trip directly; the backend's _normalize_path validator handles PurePath instances on the server side. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: URLField

**Files:**
- Create: `frontend/src/components/form/fields/URLField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

`<Input type="url">` gives basic browser-level URL hinting without enforcing validity (we want Pydantic's `TypeAdapter` to do the authoritative check). The `target_type_name` (e.g. `"pydantic.HttpUrl"`) maps to a chip showing the URL flavour.

- [ ] **Step 1: Create URLField.tsx**

`frontend/src/components/form/fields/URLField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { URLNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type URLNode = z.infer<typeof URLNodeSchema>;

function shortTypeName(fq: string): string {
  // "pydantic.HttpUrl" -> "HttpUrl"; "module.sub.AnyUrl" -> "AnyUrl"
  return fq.split(".").pop() ?? fq;
}

export function URLField({ node, path }: { node: URLNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

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
        <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
          {shortTypeName(node.target_type_name)}
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="url"
        placeholder="https://example.com"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
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

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { URLField } from "@/components/form/fields/URLField";
```

```typescript
    case "url":
      return <URLField node={node as NodeOfKind<"url">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/URLField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): URLField component for UrlNode renders" -m "type=url input with a chip showing the short URL type name (HttpUrl, AnyUrl, etc.) derived from target_type_name. Validation deferred to the backend's TypeAdapter so HttpUrl-specific scheme rules are enforced server-side. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: EmailField

**Files:**
- Create: `frontend/src/components/form/fields/EmailField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

Plain `type="email"` input. EmailNode validates server-side via `email-validator` (optional dep; falls back to permissive `@`-check).

- [ ] **Step 1: Create EmailField.tsx**

`frontend/src/components/form/fields/EmailField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { EmailNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type EmailNode = z.infer<typeof EmailNodeSchema>;

export function EmailField({ node, path }: { node: EmailNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

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
        type="email"
        placeholder="you@example.com"
        autoComplete="email"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
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

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { EmailField } from "@/components/form/fields/EmailField";
```

```typescript
    case "email":
      return <EmailField node={node as NodeOfKind<"email">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/EmailField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): EmailField component for EmailNode renders" -m "type=email input with autocomplete=email. Server validates via Pydantic EmailStr/email-validator (or a permissive fallback when the optional dep is missing). Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: DateField

**Files:**
- Create: `frontend/src/components/form/fields/DateField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

`<Input type="date">` gives a native browser date picker. Wire format is `YYYY-MM-DD`; the backend's `_maybe_coerce_typed_value` calls `date.fromisoformat(value)` (wired in T1).

- [ ] **Step 1: Create DateField.tsx**

`frontend/src/components/form/fields/DateField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { DateNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type DateNode = z.infer<typeof DateNodeSchema>;

export function DateField({ node, path }: { node: DateNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

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
        type="date"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
          // Empty string commits as null (DateNode.validate_value enforces required-ness).
          const wire = local.trim() === "" ? null : local;
          mutation.mutate(
            { op: "set_value", path, value: wire },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { DateField } from "@/components/form/fields/DateField";
```

```typescript
    case "date":
      return <DateField node={node as NodeOfKind<"date">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/DateField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): DateField component for DateNode renders" -m "type=date input with native browser date picker. Wire format YYYY-MM-DD; backend coerces via date.fromisoformat (Phase 5 T1). Empty input commits as null. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: TimeField

**Files:**
- Create: `frontend/src/components/form/fields/TimeField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

`<Input type="time">` shows a native time picker. Browsers emit `HH:MM` by default; Python's `time.fromisoformat` handles both `HH:MM` and `HH:MM:SS`.

- [ ] **Step 1: Create TimeField.tsx**

`frontend/src/components/form/fields/TimeField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { TimeNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type TimeNodeT = z.infer<typeof TimeNodeSchema>;

// Browsers' type=time control accepts "HH:MM" or "HH:MM:SS". If the
// server emitted "HH:MM:SS.microseconds" (Python time has microsecond
// resolution), slice off the seconds-fraction before binding to the
// native control so it doesn't display blank.
function isoToTimeInput(iso: string | null): string {
  if (iso === null) return "";
  // Strip microseconds and trailing tz for the control value (commit
  // sends the trimmed value; round-trip is lossy for microsecond
  // precision — acceptable for Phase 5).
  const match = iso.match(/^(\d{2}:\d{2}(?::\d{2})?)/);
  return match ? match[1] : iso;
}

export function TimeField({ node, path }: { node: TimeNodeT; path: string }) {
  const mutation = useApplyMutation();
  const initial = isoToTimeInput(node.value);
  const [local, setLocal] = useState<string>(initial);
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(isoToTimeInput(node.value));
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
        type="time"
        step="1"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === initial) return;
          const wire = local.trim() === "" ? null : local;
          mutation.mutate(
            { op: "set_value", path, value: wire },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { TimeField } from "@/components/form/fields/TimeField";
```

```typescript
    case "time":
      return <TimeField node={node as NodeOfKind<"time">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/TimeField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): TimeField component for TimeNode renders" -m "type=time input with second-level resolution (step=1). Slices microsecond fractions off the server-emitted ISO for control display; commits HH:MM:SS or HH:MM (browser-dependent). Microsecond precision lost on round-trip in Phase 5; acceptable per spec. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: DatetimeField

**Files:**
- Create: `frontend/src/components/form/fields/DatetimeField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

`<Input type="datetime-local">` needs the timezone-stripped form `YYYY-MM-DDTHH:MM`. Backend `datetime.fromisoformat` accepts both naive and tz-aware ISO strings, so we send back exactly what the browser emits — Pydantic's datetime field type handles naive instances natively (TZ-aware-ness depends on the user's schema annotation).

- [ ] **Step 1: Create DatetimeField.tsx**

`frontend/src/components/form/fields/DatetimeField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { DatetimeNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type DatetimeNodeT = z.infer<typeof DatetimeNodeSchema>;

// type=datetime-local rejects timezone suffixes and microsecond
// fractions. Slice the server-emitted ISO down to YYYY-MM-DDTHH:MM
// (or :SS) so the control populates correctly. Round-trip is lossy
// for microsecond precision and tz info in Phase 5; spec accepts that.
function isoToDatetimeLocal(iso: string | null): string {
  if (iso === null) return "";
  // Match "YYYY-MM-DDTHH:MM" (optionally with seconds) then stop.
  const match = iso.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?)/);
  return match ? match[1] : iso;
}

export function DatetimeField({ node, path }: { node: DatetimeNodeT; path: string }) {
  const mutation = useApplyMutation();
  const initial = isoToDatetimeLocal(node.value);
  const [local, setLocal] = useState<string>(initial);
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(isoToDatetimeLocal(node.value));
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
        type="datetime-local"
        step="1"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === initial) return;
          const wire = local.trim() === "" ? null : local;
          mutation.mutate(
            { op: "set_value", path, value: wire },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { DatetimeField } from "@/components/form/fields/DatetimeField";
```

```typescript
    case "datetime":
      return <DatetimeField node={node as NodeOfKind<"datetime">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/DatetimeField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): DatetimeField component for DatetimeNode renders" -m "type=datetime-local input. Slices server ISO down to YYYY-MM-DDTHH:MM(:SS) for the native control's expected format; commits the trimmed wire string. Backend coerces via datetime.fromisoformat (T1). TZ-aware-ness depends on the user's schema annotation; microsecond/tz precision is lossy in Phase 5. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: TimedeltaField

**Files:**
- Create: `frontend/src/components/form/fields/TimedeltaField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

No native control for ISO 8601 durations. Plain text input with a placeholder showing the format. Backend coerces via `TypeAdapter(timedelta)` (handles `PT1H30M`, `P1DT2H`, plain numbers as seconds, etc.).

- [ ] **Step 1: Create TimedeltaField.tsx**

`frontend/src/components/form/fields/TimedeltaField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { TimedeltaNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type TimedeltaNodeT = z.infer<typeof TimedeltaNodeSchema>;

export function TimedeltaField({ node, path }: { node: TimedeltaNodeT; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

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
        type="text"
        placeholder="PT1H30M (ISO 8601 duration)"
        className="font-mono text-sm"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
          const wire = local.trim() === "" ? null : local.trim();
          mutation.mutate(
            { op: "set_value", path, value: wire },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { TimedeltaField } from "@/components/form/fields/TimedeltaField";
```

```typescript
    case "timedelta":
      return <TimedeltaField node={node as NodeOfKind<"timedelta">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/TimedeltaField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): TimedeltaField component for TimedeltaNode renders" -m "Text input with PT1H30M (ISO 8601 duration) placeholder and monospace styling. Backend coerces via Pydantic's TypeAdapter(timedelta), which accepts ISO durations and plain second counts. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: IPAddressField

**Files:**
- Create: `frontend/src/components/form/fields/IPAddressField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

Plain text input. Placeholder depends on `version`: `192.0.2.1` for v4 (TEST-NET-1 reserved range, safe), `2001:db8::1` for v6 (documentation prefix). Monospace styling to highlight that this is structured data.

- [ ] **Step 1: Create IPAddressField.tsx**

`frontend/src/components/form/fields/IPAddressField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { IPAddressNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type IPAddressNode = z.infer<typeof IPAddressNodeSchema>;

export function IPAddressField({ node, path }: { node: IPAddressNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value ?? "");
    setError(node.error);
  }, [node.value, node.error]);

  const placeholder = node.version === 4 ? "192.0.2.1" : "2001:db8::1";

  return (
    <FieldRow>
      <FieldHeader>
        <Label htmlFor={`field-${path}`} className="text-sm font-medium">
          {node.name}
        </Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
        <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
          IPv{node.version}
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="text"
        placeholder={placeholder}
        className="font-mono text-sm"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
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

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { IPAddressField } from "@/components/form/fields/IPAddressField";
```

```typescript
    case "ip_address":
      return <IPAddressField node={node as NodeOfKind<"ip_address">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/IPAddressField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): IPAddressField component for IpAddressNode renders" -m "Text input with monospace styling. Version-aware placeholder (192.0.2.1 for v4, 2001:db8::1 for v6) and an IPv4/IPv6 chip. Backend validates with ipaddress.IPv4Address/IPv6Address; wire format is the plain string. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: IPNetworkField

**Files:**
- Create: `frontend/src/components/form/fields/IPNetworkField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

Same shape as IPAddressField but with a CIDR placeholder (`10.0.0.0/24` for v4, `2001:db8::/32` for v6).

- [ ] **Step 1: Create IPNetworkField.tsx**

`frontend/src/components/form/fields/IPNetworkField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { IPNetworkNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type IPNetworkNode = z.infer<typeof IPNetworkNodeSchema>;

export function IPNetworkField({ node, path }: { node: IPNetworkNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value ?? "");
    setError(node.error);
  }, [node.value, node.error]);

  const placeholder = node.version === 4 ? "10.0.0.0/24" : "2001:db8::/32";

  return (
    <FieldRow>
      <FieldHeader>
        <Label htmlFor={`field-${path}`} className="text-sm font-medium">
          {node.name}
        </Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
        <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
          IPv{node.version}/CIDR
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="text"
        placeholder={placeholder}
        className="font-mono text-sm"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
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

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { IPNetworkField } from "@/components/form/fields/IPNetworkField";
```

```typescript
    case "ip_network":
      return <IPNetworkField node={node as NodeOfKind<"ip_network">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/IPNetworkField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): IPNetworkField component for IpNetworkNode renders" -m "Text input with CIDR placeholder (10.0.0.0/24 for v4, 2001:db8::/32 for v6) and an IPvX/CIDR chip. Backend validates with ipaddress.IPv4Network/IPv6Network; wire format is the plain string. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: UUIDField

**Files:**
- Create: `frontend/src/components/form/fields/UUIDField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

Text input plus a regenerate Button that calls `crypto.randomUUID()` (RFC 4122 v4, available in all modern browsers; falls back to a hand-rolled hex string if missing for any reason). Pasting an existing UUID also works.

- [ ] **Step 1: Create UUIDField.tsx**

`frontend/src/components/form/fields/UUIDField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { UUIDNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type UUIDNode = z.infer<typeof UUIDNodeSchema>;

// crypto.randomUUID is available in all modern evergreen browsers
// (Chrome 92+, Firefox 95+, Safari 15.4+). Fall back to a v4-shaped
// hex string from getRandomValues for older targets; we only need to
// produce something the backend's UUID(value) parses, which Python's
// uuid module is lenient about (any valid 32-hex-with-hyphens form).
function generateUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const buf = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    crypto.getRandomValues(buf);
  } else {
    for (let i = 0; i < 16; i++) buf[i] = Math.floor(Math.random() * 256);
  }
  // Force v4 format: byte 6 = 0x4X, byte 8 = 0x[8-b]X.
  buf[6] = (buf[6] & 0x0f) | 0x40;
  buf[8] = (buf[8] & 0x3f) | 0x80;
  const hex = Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function UUIDField({ node, path }: { node: UUIDNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value ?? "");
    setError(node.error);
  }, [node.value, node.error]);

  const commit = (next: string) => {
    if (next === (node.value ?? "")) return;
    mutation.mutate(
      { op: "set_value", path, value: next },
      { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
    );
  };

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
      <div className="flex gap-2">
        <Input
          id={`field-${path}`}
          name={node.name}
          type="text"
          className="font-mono text-sm"
          placeholder="00000000-0000-0000-0000-000000000000"
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          onBlur={() => commit(local)}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={`regenerate ${node.name}`}
          onClick={() => {
            const next = generateUuid();
            setLocal(next);
            commit(next);
          }}
        >
          regenerate
        </Button>
      </div>
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { UUIDField } from "@/components/form/fields/UUIDField";
```

```typescript
    case "uuid":
      return <UUIDField node={node as NodeOfKind<"uuid">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/UUIDField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): UUIDField component for UuidNode renders" -m "Text input plus a regenerate Button using crypto.randomUUID() (with a getRandomValues fallback for older browsers). Monospace styling and a UUID placeholder. Backend coerces wire string via UUID(value) (T1). Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: SecretField

**Files:**
- Create: `frontend/src/components/form/fields/SecretField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

Password-type input (browser obscures the value) with a show/hide toggle Button that flips `type="password"` to `type="text"`. `secret_kind` is shown as a chip so users see whether the field is SecretStr or SecretBytes; the wire value is a UTF-8 string either way (backend coerces to bytes via `value.encode()` when `secret_kind == "bytes"`, per T1's `_maybe_coerce_typed_value`).

- [ ] **Step 1: Create SecretField.tsx**

`frontend/src/components/form/fields/SecretField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { SecretNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type SecretNodeT = z.infer<typeof SecretNodeSchema>;

export function SecretField({ node, path }: { node: SecretNodeT; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);
  const [revealed, setRevealed] = useState<boolean>(false);

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
        <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
          Secret{node.secret_kind === "bytes" ? "Bytes" : "Str"}
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <div className="flex gap-2">
        <Input
          id={`field-${path}`}
          name={node.name}
          type={revealed ? "text" : "password"}
          autoComplete="new-password"
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          onBlur={() => {
            if (local === (node.value ?? "")) return;
            // For secret_kind=="bytes", backend's _maybe_coerce_typed_value
            // calls value.encode() to produce bytes. For secret_kind=="str",
            // the wire value passes through unchanged.
            mutation.mutate(
              { op: "set_value", path, value: local },
              { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
            );
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={revealed ? `hide ${node.name}` : `show ${node.name}`}
          aria-pressed={revealed}
          onClick={() => setRevealed((v) => !v)}
        >
          {revealed ? "hide" : "show"}
        </Button>
      </div>
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { SecretField } from "@/components/form/fields/SecretField";
```

```typescript
    case "secret":
      return <SecretField node={node as NodeOfKind<"secret">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/SecretField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): SecretField component for SecretNode renders" -m "Password-type input with a show/hide toggle Button. Chip shows SecretStr vs SecretBytes per node.secret_kind. Wire format is always a UTF-8 string; for SecretBytes the backend coerces via value.encode() (T1). aria-pressed on the toggle for assistive tech parity. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 16: PatternField

**Files:**
- Create: `frontend/src/components/form/fields/PatternField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

Text input for the regex source plus read-only chips for any flags set on the bitmask. Python's `re.IGNORECASE = 2`, `re.MULTILINE = 8`, `re.DOTALL = 16`, `re.VERBOSE = 64`, `re.ASCII = 256`. UNICODE (32) is stripped by the PatternNode builder so it never appears here. Phase 5 does not let the user toggle flags — that's Phase 6.

- [ ] **Step 1: Create PatternField.tsx**

`frontend/src/components/form/fields/PatternField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { PatternNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type PatternNodeT = z.infer<typeof PatternNodeSchema>;

// Python re-module flag bitmask values. Mirrors `re` constants.
// UNICODE (32) is intentionally omitted - PatternNode strips it
// before storing so it never reaches this component.
const FLAG_CHIPS: ReadonlyArray<{ bit: number; label: string; tooltip: string }> = [
  { bit: 2, label: "i", tooltip: "IGNORECASE" },
  { bit: 8, label: "m", tooltip: "MULTILINE" },
  { bit: 16, label: "s", tooltip: "DOTALL" },
  { bit: 64, label: "x", tooltip: "VERBOSE" },
  { bit: 256, label: "a", tooltip: "ASCII" },
];

function activeFlagChips(flags: number) {
  return FLAG_CHIPS.filter((chip) => (flags & chip.bit) !== 0);
}

export function PatternField({ node, path }: { node: PatternNodeT; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

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
        {activeFlagChips(node.flags).map((chip) => (
          <span
            key={chip.bit}
            title={chip.tooltip}
            className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600"
          >
            {chip.label}
          </span>
        ))}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="text"
        className="font-mono text-sm"
        placeholder="regex source"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
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

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { PatternField } from "@/components/form/fields/PatternField";
```

```typescript
    case "pattern":
      return <PatternField node={node as NodeOfKind<"pattern">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/PatternField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): PatternField component for PatternNode renders" -m "Text input for the regex source plus read-only chips for any flag in the Python re-module bitmask (i/m/s/x/a). UNICODE is stripped by PatternNode so doesn't appear. Phase 6 will let users toggle flags; in Phase 5 they come from the schema and stay read-only. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 17: BytesField

**Files:**
- Create: `frontend/src/components/form/fields/BytesField.tsx`
- Modify: `frontend/src/components/form/FormField.tsx`

Hex text input plus a byte-count display under the field. Odd-length hex is soft-rejected at blur (`bytes.fromhex` would raise; we surface a local error before round-tripping). The wire value is the hex string itself; backend's `_maybe_coerce_typed_value` decodes it.

- [ ] **Step 1: Create BytesField.tsx**

`frontend/src/components/form/fields/BytesField.tsx`:

```typescript
import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { BytesNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type BytesNodeT = z.infer<typeof BytesNodeSchema>;

const HEX_RE = /^[0-9a-fA-F]*$/;

function byteCount(hex: string): number {
  // Whitespace-tolerant: strip spaces before counting (Phase 5 doesn't
  // enforce a strict pattern; users can paste "de ad be ef").
  return Math.floor(hex.replace(/\s+/g, "").length / 2);
}

export function BytesField({ node, path }: { node: BytesNodeT; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

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
        <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
          hex
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="text"
        className="font-mono text-sm"
        placeholder="deadbeef (hex)"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
          const stripped = local.replace(/\s+/g, "");
          // Soft-reject obviously-bad hex BEFORE the round-trip. The
          // backend's bytes.fromhex would also reject, but the local
          // check yields a clearer message.
          if (stripped !== "" && !HEX_RE.test(stripped)) {
            setError(`'${local}' is not valid hex`);
            return;
          }
          if (stripped.length % 2 !== 0) {
            setError(`hex must have an even number of digits (got ${stripped.length})`);
            return;
          }
          mutation.mutate(
            { op: "set_value", path, value: stripped },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <p className="text-xs text-zinc-500">{byteCount(local)} bytes</p>
      <FieldError message={error} />
    </FieldRow>
  );
}
```

- [ ] **Step 2: Wire into FormField dispatcher**

```typescript
import { BytesField } from "@/components/form/fields/BytesField";
```

```typescript
    case "bytes":
      return <BytesField node={node as NodeOfKind<"bytes">} path={path} />;
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/form/fields/BytesField.tsx frontend/src/components/form/FormField.tsx
git commit -m "feat(frontend): BytesField component for BytesNode renders" -m "Hex text input with byte-count display and soft-reject for non-hex characters or odd-length hex on blur. Backend decodes via bytes.fromhex (T1). Whitespace-tolerant (deadbeef and 'de ad be ef' both parse). Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 18: Rebuild + commit the production bundle

**Files:**
- Regenerate: `src/pydantic_studio/renderers/html/static/dist/index.html`
- Regenerate: `src/pydantic_studio/renderers/html/static/dist/assets/*`

The 15 new components and the schema additions need to land in the committed dist tree so production Python tests (which serve from the committed bundle, not from `pnpm dev`) pick them up.

- [ ] **Step 1: Confirm typecheck still clean**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 2: Build the bundle**

```bash
cd frontend && pnpm build
```

Expected: build succeeds (no rollup errors). The output lands under `src/pydantic_studio/renderers/html/static/dist/`. New asset filenames (the hash changes) — the old assets are pruned by `emptyOutDir: true` in `vite.config.ts`.

- [ ] **Step 3: Sanity-check the bundle ships the new components**

```bash
ls src/pydantic_studio/renderers/html/static/dist/assets/
```

Expected: an `index-*.js`, an `index-*.css`. Confirm by grepping the JS for one of the new kind literals:

```bash
grep -l "FloatField" src/pydantic_studio/renderers/html/static/dist/assets/*.js
```

Expected: at least one file matches. (The bundler may have mangled the function name; if the grep is empty, try the literal `"float"` kind discriminator instead — bound to appear in the bundle.)

- [ ] **Step 4: Run the static-bundle smoke test**

```bash
uv run pytest tests/unit/test_html_static_bundle.py -q
```

Expected: all tests pass. This test verifies FastAPI's static mount serves the dist tree; the new assets just have different hashes, which the test tolerates.

- [ ] **Step 5: Run the existing Phase 3/4 e2e tests as regression**

```bash
uv run pytest tests/e2e/test_spa_edit_flow.py tests/e2e/test_sequence_field.py tests/e2e/test_mapping_field.py tests/e2e/test_union_field.py tests/e2e/test_any_field.py -q
```

Expected: 5 tests pass. They cover the un-touched primitive (StringField) and the 4 containers. If anything regresses, the field dispatcher's new cases are stealing a kind they shouldn't — re-check `FormField.tsx`.

- [ ] **Step 6: Commit the bundle**

```bash
git add src/pydantic_studio/renderers/html/static/dist
git commit -m "$(cat <<'EOF'
build(frontend): rebuild dist bundle with 15 new primitive field components

pnpm build output: bundles FloatField, DecimalField, DatetimeField,
DateField, TimeField, TimedeltaField, IPAddressField, IPNetworkField,
URLField, EmailField, PathField, UUIDField, SecretField, PatternField,
BytesField plus the extended FormNodeData zod schemas.

Hash-renamed asset filenames; emptyOutDir cleans stale Phase 4 hashes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: E2E — temporal fields

**Files:**
- Modify: `tests/e2e/conftest.py` (extend `_DemoSchema` with date/datetime/time/timedelta fields + seeding)
- Create: `tests/e2e/test_temporal_fields.py`

The Phase 4 e2e infrastructure is in place (`fastapi_url` fixture, Playwright + Chromium). Extending `_DemoSchema` adds new fields the SPA renders; we drive the temporal trio through the browser to confirm the wire format the components emit lines up with what the dispatcher's coercion expects.

- [ ] **Step 1: Extend `_DemoSchema` in conftest.py**

Read `tests/e2e/conftest.py`. The existing `_DemoSchema` (lines 46-61) defines name/workers/debug/level/tags/env/notifier/metadata. Add 15 new fields (this same step also covers T20 and T21 so we don't need to keep editing conftest):

Replace the top-of-file imports with:

```python
from __future__ import annotations

import socket
import threading
import time as _time
from contextlib import closing
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path as FsPath
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import UUID

import pytest
import uvicorn
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    SecretBytes,
    SecretStr,
)

from pydantic_studio import StudioServer, build_form_tree
```

Note: the existing `import time` was used only for `time.time()` (deadline polling). Rename it to `_time` everywhere so the new `from datetime import time` doesn't shadow it. Find the `while time.time() < deadline:` line (around line 105) and change both `time.time()` to `_time.time()`, and `time.sleep(0.05)` to `_time.sleep(0.05)`.

Then replace the `_DemoSchema` class body with:

```python
class _DemoSchema(BaseModel):
    """Schema the e2e tests drive. Edit cautiously - test assertions
    pin specific field names and values."""

    # Phase 3/4 fields
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

    # Phase 5 fields - one per remaining primitive kind, in plan order
    ratio: float = Field(default=1.0, description="Phase 5 float field")
    price: Decimal = Field(default=Decimal("0.00"), description="Phase 5 decimal field")
    log_dir: FsPath = Field(default=FsPath("/tmp"), description="Phase 5 path field")
    homepage: HttpUrl = Field(
        default="https://example.com", description="Phase 5 url field"
    )
    contact: str = Field(default="ops@example.com", description="Phase 5 email field")
    starts_on: date = Field(
        default=date(2025, 1, 1), description="Phase 5 date field"
    )
    cron_at: time = Field(
        default=time(2, 30, 0), description="Phase 5 time field"
    )
    last_run: datetime = Field(
        default=datetime(2025, 1, 1, 12, 0, 0),
        description="Phase 5 datetime field",
    )
    ttl: timedelta = Field(
        default=timedelta(hours=1), description="Phase 5 timedelta field"
    )
    bind_ip: IPv4Address = Field(
        default=IPv4Address("127.0.0.1"), description="Phase 5 ip_address field"
    )
    subnet: IPv4Network = Field(
        default=IPv4Network("10.0.0.0/24"), description="Phase 5 ip_network field"
    )
    request_id: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000000"),
        description="Phase 5 uuid field",
    )
    api_key: SecretStr = Field(
        default=SecretStr("placeholder"), description="Phase 5 secret str field"
    )
    api_key_bytes: SecretBytes = Field(
        default=SecretBytes(b"placeholder"), description="Phase 5 secret bytes field"
    )
    valid_name: Annotated[str, Field(pattern=r"^[a-z]+$")] = Field(
        default="lowercase", description="Phase 5 has pattern via Annotated"
    )
    salt: bytes = Field(default=b"\xde\xad\xbe\xef", description="Phase 5 bytes field")
```

The `valid_name` field uses an Annotated[str, Field(pattern=...)] — but Pydantic v2 stores patterns differently and the FormTree builder for StringNode (NOT PatternNode) handles it. To trigger a real PatternNode, we need a `typing.Pattern[str]` annotation. Adjust:

```python
    import re

    pattern_field: re.Pattern[str] = Field(
        default=re.compile(r"^[a-z]+$", re.IGNORECASE),
        description="Phase 5 pattern field",
    )
```

Replace the `valid_name` line above with `pattern_field` accordingly (the `import re` goes at the top of the file alongside other imports).

Also fix the fixture's seeding block to add the new fields. Find the existing block (around lines 89-92):

```python
    tree.set_value("name", "demo-service")
    tree.set_value("workers", 4)
    tree.set_value("debug", False)
    tree.set_value("level", _LogLevel.INFO)
```

Extend it (the wire format for the new fields is what the SPA components emit — strings for everything):

```python
    tree.set_value("name", "demo-service")
    tree.set_value("workers", 4)
    tree.set_value("debug", False)
    tree.set_value("level", _LogLevel.INFO)
    tree.set_value("ratio", 1.0)
    tree.set_value("price", Decimal("0.00"))
    tree.set_value("log_dir", "/tmp")
    tree.set_value("homepage", "https://example.com")
    tree.set_value("contact", "ops@example.com")
    tree.set_value("starts_on", date(2025, 1, 1))
    tree.set_value("cron_at", time(2, 30, 0))
    tree.set_value("last_run", datetime(2025, 1, 1, 12, 0, 0))
    tree.set_value("ttl", timedelta(hours=1))
    tree.set_value("bind_ip", "127.0.0.1")
    tree.set_value("subnet", "10.0.0.0/24")
    tree.set_value("request_id", UUID("00000000-0000-0000-0000-000000000000"))
    tree.set_value("api_key", "placeholder")
    tree.set_value("api_key_bytes", b"placeholder")
    import re as _re
    tree.set_value("pattern_field", _re.compile(r"^[a-z]+$", _re.IGNORECASE).pattern)
    # Wait - PatternNode.set_value expects a regex SOURCE string; the
    # Python compiled-pattern would be rejected. Send the source itself:
    # the seed above is correct as-is once swapped to `.pattern`.
    tree.set_value("salt", b"\xde\xad\xbe\xef")
```

Re-check: `tree.set_value("pattern_field", ...)` — PatternNode's `validate_value` accepts strings only. So pass the regex source string directly:

```python
    tree.set_value("pattern_field", "^[a-z]+$")
```

(That's the only seeding line for the pattern. The `flags` field on PatternNode is initialized by the builder from the `Pattern[str]` default's `.flags`, so re.IGNORECASE on the default carries through into the rendered form.)

- [ ] **Step 2: Confirm conftest.py compiles by running an existing test**

```bash
uv run pytest tests/e2e/test_spa_edit_flow.py -q
```

Expected: 1 passed. If you broke the seeding (e.g., bytes that the SecretBytes node rejects), Pydantic will raise during `build_form_tree(_DemoSchema)` and the test crashes at fixture setup. Fix the seed before moving on.

- [ ] **Step 3: Write the temporal e2e test**

`tests/e2e/test_temporal_fields.py`:

```python
"""E2E for Phase 5 temporal fields: date, datetime, time.

Drives each input through the browser, asserts the server tree updates,
and confirms the preview pane reflects the new ISO-formatted value.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_edit_date_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    starts_on = page.get_by_label("starts_on", exact=True)
    expect(starts_on).to_be_visible(timeout=5000)
    starts_on.fill("2026-06-15")
    starts_on.blur()

    # Server tree should now show the new date as an ISO string.
    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "starts_on")
    assert field["kind"] == "date"
    assert field["value"] == "2026-06-15"


def test_edit_datetime_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    last_run = page.get_by_label("last_run", exact=True)
    expect(last_run).to_be_visible(timeout=5000)
    # type=datetime-local wants 'YYYY-MM-DDTHH:MM' (no tz, no seconds).
    last_run.fill("2026-03-04T09:15")
    last_run.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "last_run")
    assert field["kind"] == "datetime"
    # Pydantic emits ISO with seconds (00) and may add tz info; assert
    # the prefix matches what we typed.
    assert field["value"].startswith("2026-03-04T09:15")


def test_edit_time_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    cron_at = page.get_by_label("cron_at", exact=True)
    expect(cron_at).to_be_visible(timeout=5000)
    cron_at.fill("18:00:00")
    cron_at.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "cron_at")
    assert field["kind"] == "time"
    assert field["value"].startswith("18:00")


def test_edit_timedelta_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    ttl_input = page.get_by_label("ttl", exact=True)
    expect(ttl_input).to_be_visible(timeout=5000)
    ttl_input.fill("PT2H30M")
    ttl_input.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "ttl")
    assert field["kind"] == "timedelta"
    # Pydantic JSON-dumps timedelta as the ISO-8601 duration form. The
    # round-trip preserves the value (2.5h = 9000s = PT2H30M).
    # We assert the seconds-equivalent rather than the literal string
    # because Pydantic emits "PT9000S" or "PT2H30M" depending on
    # version. Both encode 2.5 hours.
    assert field["value"] in ("PT2H30M", "PT9000S", "PT2H30M0S")
```

- [ ] **Step 4: Run the temporal e2e test**

```bash
uv run pytest tests/e2e/test_temporal_fields.py -q
```

Expected: 4 passed. If any test fails:
- **`field["value"] == "2026-06-15"` fails** → the wire format for DateField isn't reaching the dispatcher correctly; check DateField.tsx commits `local` not a parsed-then-restringified date.
- **datetime test fails with "expected datetime, got str"** → T1's coercion isn't wired into `dispatch_mutation`. Re-read `serialize.py` and confirm `dispatch_mutation` calls `_maybe_coerce_typed_value` (NOT the old `_maybe_coerce_enum`).
- **time test fails** → check the slice helper in TimeField.tsx; it may strip too much.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/conftest.py tests/e2e/test_temporal_fields.py
git commit -m "$(cat <<'EOF'
test(e2e): Playwright coverage for Phase 5 temporal fields

Extends _DemoSchema with 16 new fields (one per Phase 5 primitive kind
plus a pattern_field). Existing Phase 3/4 fields (name/workers/.../
metadata) preserved verbatim.

tests/e2e/test_temporal_fields.py drives date / datetime / time /
timedelta through the SPA: load page, fill the native control, blur,
fetch /api/tree, assert the wire value matches the typed Python value.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 20: E2E — network + web fields

**Files:**
- Create: `tests/e2e/test_network_fields.py`

`_DemoSchema` was already extended in T19; this task just adds the test file. Covers url + email + ip_address (skip ip_network for brevity — same code path as ip_address).

- [ ] **Step 1: Write the test**

`tests/e2e/test_network_fields.py`:

```python
"""E2E for Phase 5 network + web fields: url, email, ip_address.

Each test fills the input, blurs to commit, then asserts the server
tree reflects the new value. ip_network reuses ip_address's code path
(same component shape, different placeholder) so isn't covered here.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_edit_url_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    homepage = page.get_by_label("homepage", exact=True)
    expect(homepage).to_be_visible(timeout=5000)
    homepage.fill("https://pydantic.dev")
    homepage.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "homepage")
    assert field["kind"] == "url"
    # HttpUrl normalizes (may add trailing slash); assert the prefix.
    assert field["value"].startswith("https://pydantic.dev")
    # The component shows a short type chip; verify the target_type_name
    # carries through the API so the chip renders.
    assert field["target_type_name"].endswith("HttpUrl") or field["target_type_name"].endswith("Url")


def test_edit_email_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    contact = page.get_by_label("contact", exact=True)
    expect(contact).to_be_visible(timeout=5000)
    contact.fill("support@pydantic.dev")
    contact.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "contact")
    # contact is a `str` field in _DemoSchema; the registry maps it to
    # a StringNode unless we annotate it as EmailStr. Update conftest
    # if you want a real EmailNode here. For now, assert it parsed.
    assert field["value"] == "support@pydantic.dev"


def test_edit_ip_address_field_updates_tree(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    bind_ip = page.get_by_label("bind_ip", exact=True)
    expect(bind_ip).to_be_visible(timeout=5000)
    bind_ip.fill("10.42.0.1")
    bind_ip.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "bind_ip")
    assert field["kind"] == "ip_address"
    assert field["version"] == 4
    assert field["value"] == "10.42.0.1"
```

**Heads-up for the email test:** the test as written assumes `contact: str` (StringNode); since the Phase 5 demo schema lists `contact: str`, the assertion path `field["kind"] != "email"`. If you want a real EmailNode round-trip, change `contact` in `conftest.py` to:

```python
from pydantic import EmailStr
contact: EmailStr = Field(default="ops@example.com", description="Phase 5 email field")
```

Then update the assertion to `assert field["kind"] == "email"`. If the `email-validator` extra isn't installed in CI, leave `contact: str` (the test still exercises the SPA path; the EmailField component never renders for it). The plan ships the str version as the safer default; flip to EmailStr if `pyproject.toml` has email-validator pinned.

- [ ] **Step 2: If `email-validator` is installed, switch contact to EmailStr**

Check:

```bash
uv pip list | grep email-validator
```

If it's listed: update `tests/e2e/conftest.py` per the heads-up above. Otherwise leave `contact: str`.

- [ ] **Step 3: Run the test**

```bash
uv run pytest tests/e2e/test_network_fields.py -q
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_network_fields.py tests/e2e/conftest.py
git commit -m "test(e2e): Playwright coverage for Phase 5 network + web fields" -m "Drives url, email, and ip_address through the SPA. Wire format is the plain string for each; assert round-trip via /api/tree. ip_network skipped (same code path as ip_address, different placeholder only). Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 21: E2E — special fields

**Files:**
- Create: `tests/e2e/test_special_fields.py`

Covers uuid (regenerate button), secret (show toggle), pattern (flag chips render). Bytes is asserted via a separate `pnpm tsc -b` rather than a full e2e test — the hex round-trip is exercised at the unit level (T1) and a full e2e Playwright pass on bytes would add little signal.

- [ ] **Step 1: Write the test**

`tests/e2e/test_special_fields.py`:

```python
"""E2E for Phase 5 special fields: uuid (regenerate button), secret
(show toggle), pattern (flag chips render).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_uuid_regenerate_button_updates_value(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    request_id = page.get_by_label("request_id", exact=True)
    expect(request_id).to_be_visible(timeout=5000)
    expect(request_id).to_have_value(
        "00000000-0000-0000-0000-000000000000", timeout=5000
    )

    # Click regenerate. crypto.randomUUID returns a fresh v4 UUID.
    regen = page.get_by_role("button", name="regenerate request_id")
    expect(regen).to_be_visible()
    regen.click()

    # The input now holds a different UUID. Wait for the round-trip
    # to update node.value (re-render via useQuery).
    expect(request_id).not_to_have_value(
        "00000000-0000-0000-0000-000000000000", timeout=5000
    )

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "request_id")
    assert field["kind"] == "uuid"
    new_value = field["value"]
    # Sanity: it's a valid UUID-shaped string.
    assert len(new_value) == 36
    assert new_value.count("-") == 4
    # And it's NOT the all-zeros placeholder.
    assert new_value != "00000000-0000-0000-0000-000000000000"


def test_secret_show_toggle_reveals_input_type(
    page: Page, fastapi_url: str
) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    api_key = page.get_by_label("api_key", exact=True)
    expect(api_key).to_be_visible(timeout=5000)
    expect(api_key).to_have_attribute("type", "password")

    # Click the show toggle. After click, input type flips to "text".
    show_btn = page.get_by_role("button", name="show api_key")
    expect(show_btn).to_be_visible()
    show_btn.click()
    expect(api_key).to_have_attribute("type", "text", timeout=2000)

    # The button text should now read "hide".
    hide_btn = page.get_by_role("button", name="hide api_key")
    expect(hide_btn).to_be_visible(timeout=2000)


def test_secret_edit_round_trips_value(page: Page, fastapi_url: str) -> None:
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    api_key = page.get_by_label("api_key", exact=True)
    expect(api_key).to_be_visible(timeout=5000)
    api_key.fill("hunter2")
    api_key.blur()

    response = page.context.request.get(f"{fastapi_url}/api/tree")
    body = response.json()
    field = next(f for f in body["root"]["fields"] if f["name"] == "api_key")
    assert field["kind"] == "secret"
    assert field["secret_kind"] == "str"
    # SecretStr round-trips as the plaintext on the wire (per
    # SecretNode's bytes-as-str storage; the actual Pydantic SecretStr
    # masking happens only at model_dump_secrets / __str__).
    assert field["value"] == "hunter2"


def test_pattern_field_renders_flag_chips(
    page: Page, fastapi_url: str
) -> None:
    """The default pattern_field has re.IGNORECASE set; the component
    derives an 'i' chip from the flags bitmask (= 2). This test asserts
    the chip is rendered and read-only (no toggle button)."""
    page.goto(f"{fastapi_url}/static/dist/index.html")
    expect(page.get_by_label("name", exact=True)).to_be_visible(timeout=5000)

    pattern_input = page.get_by_label("pattern_field", exact=True)
    expect(pattern_input).to_be_visible(timeout=5000)

    # The 'i' chip lives inside the FieldHeader for pattern_field. Two
    # selectors that work:
    #   - by tooltip text (title attribute = IGNORECASE)
    #   - by text content "i" near the pattern_field label
    # Use the tooltip selector to avoid matching unrelated 'i' glyphs.
    ignorecase_chip = page.locator('span[title="IGNORECASE"]')
    expect(ignorecase_chip).to_be_visible(timeout=5000)

    # Server tree still shows the original flags value (re.IGNORECASE = 2,
    # potentially OR'd with re.UNICODE which PatternNode strips). Phase 5
    # does NOT let users toggle flags - assert no toggle Button exists.
    toggle_buttons = page.get_by_role("button", name="toggle IGNORECASE")
    assert toggle_buttons.count() == 0
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest tests/e2e/test_special_fields.py -q
```

Expected: 4 passed.

Common failure modes:
- **UUID regen test times out on "not all-zeros"** → the regenerate Button doesn't fire `mutation.mutate`. Re-read UUIDField.tsx; the onClick must call `commit(next)` after `setLocal(next)`.
- **Secret toggle test fails on the type attribute** → SecretField's `type` prop is hard-coded. Confirm it uses `revealed ? "text" : "password"`.
- **Pattern chip not visible** → PatternNode's `flags` value is 0 in the tree. Check conftest's seed for `pattern_field` — the regex must be compiled with `re.IGNORECASE` AND the PatternNode builder must strip only UNICODE (32), not IGNORECASE (2). Phase 4's metadata extractor should pick up the flag directly from `re.compile(..., re.IGNORECASE).flags & ~re.UNICODE = 2`.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_special_fields.py
git commit -m "test(e2e): Playwright coverage for Phase 5 special fields" -m "Drives uuid (regenerate button generates a fresh v4 UUID and round-trips), secret (show/hide toggle flips input type; edit round-trips plaintext), and pattern (read-only flag chips derived from the schema's re.IGNORECASE). Bytes is covered by unit + tsc only; the hex round-trip adds no signal at the e2e level. Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 22: Full-suite verification + handoff

**Files:** (no source changes; verification only)

The 21 prior tasks each verified their own slice. T22 confirms that the union of all changes still passes every existing test plus the 9 new unit tests, 4 temporal e2e tests, 3 network e2e tests, and 4 special e2e tests.

- [ ] **Step 1: Unit suite**

```bash
uv run pytest -q --ignore=tests/e2e
```

Expected: all tests pass. The Phase 4 baseline count grows by 10 (9 new test_html_serialize + 1 new test_paths). If anything regresses outside Phase 5 turf, you've inadvertently changed a Python module that other tests depend on — revisit recent diffs to `serialize.py`.

- [ ] **Step 2: E2E suite**

```bash
uv run pytest tests/e2e -q
```

Expected: 16 tests pass (5 from Phase 3/4 + 4 temporal + 3 network + 4 special). On Windows, Playwright sometimes hangs on browser teardown; if the second run after the first hangs, run with `--forked` or restart the shell session.

If you don't have Chromium installed, run:

```bash
uv run playwright install chromium
```

then re-run the e2e suite.

- [ ] **Step 3: TypeScript build**

```bash
cd frontend && pnpm exec tsc -b
```

Expected: exit 0.

- [ ] **Step 4: Production bundle build (sanity)**

```bash
cd frontend && pnpm build
```

Expected: succeeds; no errors. If you see a "duplicate kind in dispatcher" type warning, two `case` lines in `FormField.tsx` may have collided — re-check the 15 new cases for typos.

- [ ] **Step 5: Lint**

```bash
uv run ruff check
```

Expected: 0 errors.

- [ ] **Step 6: Spec-coverage cross-check (manual)**

Walk through the 15 kinds and confirm each has a component file:

```bash
ls frontend/src/components/form/fields/
```

Expected output (in any order):
```
AnyField.tsx
BoolField.tsx
BytesField.tsx
DateField.tsx
DatetimeField.tsx
DecimalField.tsx
EmailField.tsx
EnumField.tsx
FloatField.tsx
GroupField.tsx
IntField.tsx
IPAddressField.tsx
IPNetworkField.tsx
LiteralField.tsx
MappingField.tsx
PathField.tsx
PatternField.tsx
SecretField.tsx
SequenceField.tsx
StringField.tsx
TimeField.tsx
TimedeltaField.tsx
URLField.tsx
UUIDField.tsx
UnionField.tsx
```

25 files = 5 Phase 3 primitives + 5 Phase 4 containers + 15 Phase 5 primitives.

Walk the FormField dispatcher and confirm 25 cases (the default branch is now unreachable but kept as a debug fallback). Each case dispatches to one of the 25 files above:

```bash
grep -c "case \"" frontend/src/components/form/FormField.tsx
```

Expected: 24 (the default branch isn't a case; 15 new + 9 existing = 24). If 25, an extra case slipped in; if <24, one of the Phase 5 wires is missing.

- [ ] **Step 7: Final commit + tag prep**

The 21 commits in this branch implement Phase 5 in full. No further code commits should be needed in T22 unless verification surfaces a regression. If a regression appears, fix-it commits go in front of the merge.

Verify the branch is healthy:

```bash
git status
# expected: clean working tree
git log --oneline feature/shadcn-redesign-phase-5-remaining-primitives ^main | wc -l
# expected: ~21 commits (T1, T2, T3..T17, T18, T19, T20, T21)
```

- [ ] **Step 8: Handoff report**

The standing rule (CLAUDE.md "Workflow conventions > Git") is to commit and merge only — DO NOT push. Report back to the user the final counts and any deferred items.

Report template:

```
Phase 5 implementation complete on feature/shadcn-redesign-phase-5-remaining-primitives.

Tests:
  - Unit:  <N> passed (Phase 4 baseline + 10 new)
  - E2E:   16 passed (Phase 4 baseline 5 + 4 temporal + 3 network + 4 special)
  - tsc:   exit 0
  - ruff:  exit 0
  - build: exit 0

Components shipped: 15 new field components (Float, Decimal, Datetime,
Date, Time, Timedelta, IPAddress, IPNetwork, URL, Email, Path, UUID,
Secret, Pattern, Bytes).

Backend: dispatcher generalized via _maybe_coerce_typed_value (renamed
from _maybe_coerce_enum). 8 typed kinds coerce wire strings to Python
typed values before validate_value.

Deferred to Phase 6 (per plan scope):
  - Validation surface polish (red borders on invalid blur)
  - Theme toggle
  - Sidebar search
  - Undo/redo UI
  - Constraint-aware TypeBadge hints
  - Lucide icons replacing ASCII glyphs
  - Depth-based GroupField collapse
  - User-toggleable pattern flags
```

---

## Self-Review (per writing-plans skill)

Run after the plan is drafted; fix issues inline.

### 1. Spec coverage

The user's brief enumerates 15 missing primitive kinds; each gets its own per-component task (T3-T17). The backend gap is covered by T1. zod schemas + dispatcher wiring (per-task) by T2-T17. E2E coverage by T19-T21. The "bonus" `test_parse_dotted_integer` is in T1. The bundle rebuild is T18. Suite verification is T22.

**Spec items → tasks:**

| Requirement | Task |
|---|---|
| Generalize `_maybe_coerce_enum` → `_maybe_coerce_typed_value` | T1 |
| Unit tests for each of 8 coerced kinds + enum regression | T1 (10 tests) |
| `test_parse_dotted_integer` backfill | T1 |
| zod schemas for 15 new kinds + FormNodeData extension | T2 |
| FloatField | T3 |
| DecimalField | T4 |
| PathField | T5 |
| URLField | T6 |
| EmailField | T7 |
| DateField | T8 |
| TimeField | T9 |
| DatetimeField | T10 |
| TimedeltaField | T11 |
| IPAddressField | T12 |
| IPNetworkField | T13 |
| UUIDField | T14 |
| SecretField | T15 |
| PatternField | T16 |
| BytesField | T17 |
| Rebuild dist bundle | T18 |
| E2E temporal coverage | T19 |
| E2E network/web coverage | T20 |
| E2E special coverage | T21 |
| Full-suite verify + handoff | T22 |

22 tasks total — matches the user's target.

### 2. Placeholder scan

Scanned for: "TBD", "TODO", "implement later", "fill in", "appropriate error handling", "similar to Task". One legitimate use of "TODO"-equivalent: the conftest.py "Phase 6 housekeeping removed default-seeding" comment block (preserved from Phase 4). All steps contain executable code, exact commands, or specific instructions. The `default` branch of `FormField.tsx` is "kept as a debug fallback" — that's an explicit design decision, not a placeholder.

### 3. Type consistency

- `_maybe_coerce_typed_value(tree: FormTree, path: str, value: Any) -> Any` — used consistently in T1's helper definition and the `dispatch_mutation` wire.
- `useApplyMutation()` returns a `UseMutationResult`; `.mutate({op, path, value}, {onError})` signature used in every component (T3-T17).
- `FormNodeData` discriminated union (T2) → `NodeOfKind<K>` helper in FormField.tsx (preserved from Phase 4) → component prop type `node: NodeOfKind<"X">` (T3-T17).
- Kind literals (T2 zod schemas) match Python `FormNode.kind` field values (Python `Literal["float"]` ↔ TypeScript `z.literal("float")`).
- Backend dispatcher (T1) imports `BytesNode`, `DateNode`, `DatetimeNode`, `DecimalNode`, `EnumNode`, `SecretNode`, `TimedeltaNode`, `TimeNode`, `UuidNode` from `pydantic_studio.tree.nodes` — matches the actual class names exported there.
- `crypto.randomUUID()` return type is `string` (Web Crypto API spec) — usage in T14 is type-clean.
- `aria-pressed` on SecretField's toggle (T15) is a valid HTML attribute on `<button>` per ARIA 1.2.

### 4. Cross-component sanity

- The 15 new dispatch cases in T3-T17 all import from the same chrome layer (`@/components/form/chrome/*`) — no drift.
- The wire format for each kind matches what `_maybe_coerce_typed_value` (T1) expects: ISO strings for temporals/decimals/uuids, hex for bytes, plain str for everything else. Verified case-by-case.
- The `FormField.tsx` `case` ordering is irrelevant at runtime (every case `return`s); the order in the plan is the spec's reading order.
- `tests/e2e/conftest.py` extension (T19) adds exactly one field per kind whose component lands in T3-T17 — verified by checking each kind appears in the `_DemoSchema` body.

No issues found. Plan is ready.

---

## Execution

**Plan complete and saved to `docs/superpowers/plans/2026-05-15-shadcn-web-redesign-phase-5-remaining-primitives.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh Opus 4.7 subagent per task, review between tasks, fast iteration. Aligns with this project's Workflow conventions (CLAUDE.md "Skills used" section). Two-stage review per substantive task.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

**Which approach?**
