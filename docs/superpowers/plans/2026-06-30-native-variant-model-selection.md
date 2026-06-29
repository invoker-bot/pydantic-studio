# Native Variant Model Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add generic first-class model/class selection to pydantic-studio so console, TUI, and web can choose a model variant before editing its fields.

**Architecture:** Keep pydantic-studio independent of any host project by introducing a small `VariantSpec` / `VariantRegistry` API that callers populate with Pydantic model classes. `FormTree.root` stays a `GroupNode`; optional root-level variant metadata on `FormTree` records the selectable models, selected id, and output persistence behavior. Web selection happens inside the web page through the same JSON mutation loop as other edits, not as a pre-launch CLI prompt.

**Tech Stack:** Python 3.11, Pydantic v2, Typer/Rich console prompts, Textual, FastAPI JSON API, React/Vite, Zod, pytest, Playwright.

---

## File Structure

- Create `src/pydantic_studio/variants.py`: public generic variant API (`VariantSpec`, `VariantRegistry`, `build_variant_form_tree`).
- Modify `src/pydantic_studio/tree/nodes.py`: serializable variant metadata on `FormTree`, `select_root_variant()`, and `to_output_python()`.
- Modify `src/pydantic_studio/io/yaml.py`, `src/pydantic_studio/io/json_.py`, `src/pydantic_studio/io/toml.py`: write `tree.to_output_python()` so variant discriminator output is preserved.
- Modify `src/pydantic_studio/renderers/html/render.py`, `src/pydantic_studio/renderers/html/serialize.py`: preview and mutation support for root variant selection.
- Modify `frontend/src/api/schemas.ts`, `frontend/src/api/mutations.ts`, `frontend/src/App.tsx`: expose variant metadata and render a page-level selector.
- Create `frontend/src/components/form/VariantSelector.tsx`: reusable web selector for root variants.
- Modify `src/pydantic_studio/renderers/console.py`: prompt for root variant in console mode before field prompts.
- Modify `src/pydantic_studio/renderers/textual_/app.py` and `src/pydantic_studio/renderers/textual_/widgets/field_list.py`: show and change root variant in TUI.
- Modify `src/pydantic_studio/__init__.py`: export the new public API.
- Add focused tests under `tests/unit/` and one browser e2e test under `tests/e2e/`.
- Update `README.md`, `docs/site/api.md`, and `docs/site/architecture.md` with the generic API and frontend behavior.

## Scope Rules

- No import from HFT-Python or any host project.
- No hard-coded `class_name`; callers can choose any discriminator field name.
- Web variant selection is in-page. `run_html_app(...)` opens the app first; the user chooses the variant in the browser.
- Existing `UnionNode` remains the static field-level union implementation. This plan adds root-level dynamic model selection and shares naming/metadata conventions with union rendering.

---

### Task 1: Public Variant API

**Files:**
- Create: `src/pydantic_studio/variants.py`
- Modify: `src/pydantic_studio/__init__.py`
- Test: `tests/unit/test_variants.py`

- [ ] **Step 1: Write failing tests for variant registry validation**

Add `tests/unit/test_variants.py`:

```python
from __future__ import annotations

import pytest
from pydantic import BaseModel

from pydantic_studio.variants import VariantRegistry, VariantSpec


class EmailSettings(BaseModel):
    address: str = "ops@example.com"


class SlackSettings(BaseModel):
    channel: str = "#ops"


def test_variant_registry_keeps_order_and_labels() -> None:
    registry = VariantRegistry(
        [
            VariantSpec(id="email", model=EmailSettings, label="Email"),
            VariantSpec(id="slack", model=SlackSettings),
        ]
    )

    assert [spec.id for spec in registry] == ["email", "slack"]
    assert registry.get("email").label == "Email"
    assert registry.get("slack").label == "SlackSettings"


def test_variant_registry_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="duplicate variant id: email"):
        VariantRegistry(
            [
                VariantSpec(id="email", model=EmailSettings),
                VariantSpec(id="email", model=SlackSettings),
            ]
        )


def test_variant_registry_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="variant id must be non-empty"):
        VariantSpec(id=" ", model=EmailSettings)
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run python -m pytest tests/unit/test_variants.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pydantic_studio.variants'`.

- [ ] **Step 3: Implement the public variant API**

Create `src/pydantic_studio/variants.py`:

```python
"""Generic selectable Pydantic model variants."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree


def _model_type_name(model: type[BaseModel]) -> str:
    return f"{model.__module__}.{model.__qualname__}"


@dataclass(frozen=True)
class VariantSpec:
    """One selectable Pydantic model variant."""

    id: str
    model: type[BaseModel]
    label: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        normalized = self.id.strip()
        if not normalized:
            msg = "variant id must be non-empty"
            raise ValueError(msg)
        if not isinstance(self.model, type) or not issubclass(self.model, BaseModel):
            msg = f"variant {normalized!r} model must be a Pydantic BaseModel subclass"
            raise TypeError(msg)
        object.__setattr__(self, "id", normalized)

    @property
    def display_label(self) -> str:
        return self.label or self.model.__name__

    @property
    def model_type_name(self) -> str:
        return _model_type_name(self.model)


class VariantRegistry:
    """Ordered lookup for selectable Pydantic model variants."""

    def __init__(self, variants: Iterable[VariantSpec]) -> None:
        self._variants = list(variants)
        self._by_id: dict[str, VariantSpec] = {}
        for spec in self._variants:
            if spec.id in self._by_id:
                msg = f"duplicate variant id: {spec.id}"
                raise ValueError(msg)
            self._by_id[spec.id] = spec

    def __iter__(self) -> Iterator[VariantSpec]:
        return iter(self._variants)

    def __len__(self) -> int:
        return len(self._variants)

    def get(self, id_: str) -> VariantSpec:
        try:
            return self._by_id[id_]
        except KeyError as exc:
            known = ", ".join(self._by_id)
            msg = f"unknown variant id {id_!r}; known variants: {known}"
            raise ValueError(msg) from exc

    @property
    def default_id(self) -> str:
        if not self._variants:
            msg = "at least one variant is required"
            raise ValueError(msg)
        return self._variants[0].id


def build_variant_form_tree(
    variants: VariantRegistry,
    *,
    selected_id: str | None = None,
    existing: dict[str, object] | None = None,
    discriminator: str | None = None,
    persistence: str = "metadata",
) -> FormTree:
    """Build a FormTree for a selectable set of root model variants."""

    from pydantic_studio.tree.builder import build_form_tree

    selected = selected_id or variants.default_id
    spec = variants.get(selected)
    tree = build_form_tree(spec.model, existing=existing)
    tree.attach_variant_registry(
        variants,
        selected_id=selected,
        discriminator=discriminator,
        persistence=persistence,
    )
    return tree
```

- [ ] **Step 4: Export the public API**

Modify `src/pydantic_studio/__init__.py` to import and export:

```python
from pydantic_studio.variants import (
    VariantRegistry,
    VariantSpec,
    build_variant_form_tree,
)
```

Add these names to `__all__`:

```python
"VariantRegistry",
"VariantSpec",
"build_variant_form_tree",
```

- [ ] **Step 5: Run the registry tests**

Run:

```bash
uv run python -m pytest tests/unit/test_variants.py -q
```

Expected: PASS for the registry tests that do not call `build_variant_form_tree`; failures that mention `attach_variant_registry` are expected until Task 2.

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/variants.py src/pydantic_studio/__init__.py tests/unit/test_variants.py
git commit -m "feat: add generic variant registry"
```

---

### Task 2: FormTree Root Variant State

**Files:**
- Modify: `src/pydantic_studio/tree/nodes.py`
- Modify: `src/pydantic_studio/variants.py`
- Test: `tests/unit/test_variants.py`

- [ ] **Step 1: Add failing tests for root variant selection**

Append to `tests/unit/test_variants.py`:

```python
from pydantic_studio.variants import build_variant_form_tree


def _registry() -> VariantRegistry:
    return VariantRegistry(
        [
            VariantSpec(id="email", model=EmailSettings, label="Email"),
            VariantSpec(id="slack", model=SlackSettings, label="Slack"),
        ]
    )


def test_build_variant_form_tree_attaches_metadata() -> None:
    tree = build_variant_form_tree(
        _registry(),
        selected_id="email",
        discriminator="class_name",
        persistence="inline_discriminator",
    )

    assert tree.schema_class is EmailSettings
    assert tree.variant is not None
    assert tree.variant.selected_id == "email"
    assert [option.id for option in tree.variant.options] == ["email", "slack"]
    assert tree.to_output_python()["class_name"] == "email"


def test_select_root_variant_rebuilds_schema_and_root() -> None:
    tree = build_variant_form_tree(_registry(), selected_id="email")

    result = tree.select_root_variant("slack")

    assert result.ok is True
    assert tree.schema_class is SlackSettings
    assert tree.variant is not None
    assert tree.variant.selected_id == "slack"
    assert tree.root.find("channel") is not None
    assert tree.root.find("address") is None


def test_select_root_variant_rejects_unknown_id_without_mutating() -> None:
    tree = build_variant_form_tree(_registry(), selected_id="email")

    result = tree.select_root_variant("pager")

    assert result.ok is False
    assert tree.schema_class is EmailSettings
    assert tree.variant is not None
    assert tree.variant.selected_id == "email"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
uv run python -m pytest tests/unit/test_variants.py -q
```

Expected: FAIL with `AttributeError: 'FormTree' object has no attribute 'attach_variant_registry'`.

- [ ] **Step 3: Add serializable variant models**

Modify `src/pydantic_studio/tree/nodes.py` above `class FormTree`:

```python
class VariantOption(BaseModel):
    """Serializable metadata for one selectable root model variant."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    description: str | None = None
    model_type_name: str


class VariantState(BaseModel):
    """Root-level variant selector state for a FormTree."""

    model_config = ConfigDict(extra="forbid")

    options: list[VariantOption]
    selected_id: str
    discriminator: str | None = None
    persistence: Literal["metadata", "inline_discriminator", "model_field"] = "metadata"
```

- [ ] **Step 4: Attach variant state to FormTree**

Modify `FormTree` fields in `src/pydantic_studio/tree/nodes.py`:

```python
variant: VariantState | None = None
```

Add methods to `FormTree`:

```python
    def attach_variant_registry(
        self,
        variants: Any,
        *,
        selected_id: str,
        discriminator: str | None = None,
        persistence: str = "metadata",
    ) -> None:
        options = [
            VariantOption(
                id=spec.id,
                label=spec.display_label,
                description=spec.description,
                model_type_name=spec.model_type_name,
            )
            for spec in variants
        ]
        ids = {option.id for option in options}
        if selected_id not in ids:
            msg = f"selected variant {selected_id!r} is not in registry"
            raise ValueError(msg)
        self.variant = VariantState(
            options=options,
            selected_id=selected_id,
            discriminator=discriminator,
            persistence=persistence,
        )

    def to_output_python(self) -> dict[str, Any]:
        instance = self.to_instance()
        data = instance.model_dump(mode="json")
        if (
            self.variant is not None
            and self.variant.persistence == "inline_discriminator"
            and self.variant.discriminator
        ):
            data = {self.variant.discriminator: self.variant.selected_id, **data}
        return data

    def select_root_variant(self, variant_id: str, seed: Any = None) -> ValidationResult:
        if self.variant is None:
            return ValidationResult.fail(["tree does not have root variants"])
        option = next(
            (candidate for candidate in self.variant.options if candidate.id == variant_id),
            None,
        )
        if option is None:
            known = ", ".join(candidate.id for candidate in self.variant.options)
            return ValidationResult.fail(
                [f"unknown variant id {variant_id!r}; known variants: {known}"]
            )

        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        model = _resolve_type_name(option.model_type_name)
        builder = default_registry().find(model)
        new_root = builder.build(model, FieldInfo(annotation=model), seed or {})
        if not isinstance(new_root, GroupNode):
            return ValidationResult.fail([f"variant {variant_id!r} did not build a group root"])

        self._push_snapshot(_snap.take(self.root))
        self.schema_class = model
        self.schema_name = f"{model.__module__}:{model.__qualname__}"
        self.root = new_root
        self.variant.selected_id = variant_id
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()
```

- [ ] **Step 5: Harden persistence validation in `variants.py`**

Modify `build_variant_form_tree` in `src/pydantic_studio/variants.py` before calling `attach_variant_registry`:

```python
    allowed = {"metadata", "inline_discriminator", "model_field"}
    if persistence not in allowed:
        msg = f"unknown variant persistence {persistence!r}; use one of {sorted(allowed)}"
        raise ValueError(msg)
    if persistence == "inline_discriminator" and not discriminator:
        msg = "inline_discriminator persistence requires a discriminator"
        raise ValueError(msg)
```

- [ ] **Step 6: Run root variant tests**

Run:

```bash
uv run python -m pytest tests/unit/test_variants.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/pydantic_studio/tree/nodes.py src/pydantic_studio/variants.py tests/unit/test_variants.py
git commit -m "feat: add root variant state to form tree"
```

---

### Task 3: Output, Preview, and HTML API Mutation

**Files:**
- Modify: `src/pydantic_studio/io/yaml.py`
- Modify: `src/pydantic_studio/io/json_.py`
- Modify: `src/pydantic_studio/io/toml.py`
- Modify: `src/pydantic_studio/renderers/html/render.py`
- Modify: `src/pydantic_studio/renderers/html/serialize.py`
- Test: `tests/unit/test_variants.py`
- Test: `tests/unit/test_html_serialize.py`

- [ ] **Step 1: Add failing tests for output and mutation**

Append to `tests/unit/test_variants.py`:

```python
from pydantic_studio.io.yaml import save_yaml


def test_save_yaml_includes_inline_discriminator(tmp_path) -> None:
    tree = build_variant_form_tree(
        _registry(),
        selected_id="email",
        discriminator="class_name",
        persistence="inline_discriminator",
    )
    out = tmp_path / "settings.yaml"

    save_yaml(tree, out)

    assert out.read_text(encoding="utf-8").splitlines()[0] == "class_name: email"
    assert "address: ops@example.com" in out.read_text(encoding="utf-8")
```

Append to `tests/unit/test_html_serialize.py`:

```python
from pydantic_studio.variants import VariantRegistry, VariantSpec, build_variant_form_tree


class _VariantEmail(BaseModel):
    address: str = "ops@example.com"


class _VariantSlack(BaseModel):
    channel: str = "#ops"


def test_tree_to_json_includes_root_variant_metadata() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_VariantEmail, label="Email"),
                VariantSpec(id="slack", model=_VariantSlack, label="Slack"),
            ]
        ),
        selected_id="email",
        discriminator="class_name",
        persistence="inline_discriminator",
    )

    data = tree_to_json(tree)

    assert data["variant"]["selected_id"] == "email"
    assert data["variant"]["options"][0]["label"] == "Email"
    assert "class_name: email" in data["preview"]


def test_dispatch_select_root_variant_switches_root_model() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_VariantEmail),
                VariantSpec(id="slack", model=_VariantSlack),
            ]
        ),
        selected_id="email",
    )

    result = dispatch_mutation(tree, {"op": "select_root_variant", "variant_id": "slack"})

    assert result.ok is True
    assert tree.schema_class is _VariantSlack
    assert tree.root.find("channel") is not None
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
uv run python -m pytest tests/unit/test_variants.py::test_save_yaml_includes_inline_discriminator tests/unit/test_html_serialize.py::test_tree_to_json_includes_root_variant_metadata tests/unit/test_html_serialize.py::test_dispatch_select_root_variant_switches_root_model -q
```

Expected: FAIL because save/preview still use `to_instance().model_dump(...)`, and `dispatch_mutation` does not know `select_root_variant`.

- [ ] **Step 3: Use `to_output_python()` for YAML**

Modify `src/pydantic_studio/io/yaml.py` in `save_yaml`:

```python
    data = tree.to_output_python()
    cm = _build_commented_map(data, schema, source)
```

Modify `_build_commented_map` after the schema-field loop:

```python
    for key, value in data.items():
        if key in cm:
            continue
        cm[key] = value
        _copy_comment_if_present(source, cm, key)
```

- [ ] **Step 4: Use `to_output_python()` for JSON and TOML**

Modify `src/pydantic_studio/io/json_.py`:

```python
    payload = json.dumps(tree.to_output_python(), indent=2)
```

Modify `src/pydantic_studio/io/toml.py`:

```python
    data = tree.to_output_python()
    doc = _build_document(data, schema)
```

Modify `_build_document` after the schema-field loop:

```python
    for field_name, value in data.items():
        if field_name in doc:
            continue
        doc.add(field_name, value)
```

- [ ] **Step 5: Use `to_output_python()` for preview**

Modify `src/pydantic_studio/renderers/html/render.py`:

```python
    try:
        data = tree.to_output_python()
    except Exception:
        data = tree.to_python()
```

- [ ] **Step 6: Include variant metadata and mutation support in JSON API**

Modify `src/pydantic_studio/renderers/html/serialize.py` in `tree_to_json`:

```python
    data["variant"] = (
        tree.variant.model_dump(mode="json") if tree.variant is not None else None
    )
```

Modify `dispatch_mutation`:

```python
        if op == "select_root_variant":
            return tree.select_root_variant(str(mutation["variant_id"]))
```

- [ ] **Step 7: Run the focused tests**

Run:

```bash
uv run python -m pytest tests/unit/test_variants.py tests/unit/test_html_serialize.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/io/yaml.py src/pydantic_studio/io/json_.py src/pydantic_studio/io/toml.py src/pydantic_studio/renderers/html/render.py src/pydantic_studio/renderers/html/serialize.py tests/unit/test_variants.py tests/unit/test_html_serialize.py
git commit -m "feat: serialize root variant selection"
```

---

### Task 4: Console Selector

**Files:**
- Modify: `src/pydantic_studio/renderers/console.py`
- Test: `tests/unit/test_console_renderer.py`

- [ ] **Step 1: Add failing console test**

Append to `tests/unit/test_console_renderer.py`:

```python
from pydantic_studio.variants import VariantRegistry, VariantSpec, build_variant_form_tree


class ConsoleEmail(BaseModel):
    address: str = "ops@example.com"


class ConsoleSlack(BaseModel):
    channel: str = "#ops"


def test_console_prompts_for_root_variant_before_fields(tmp_path) -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=ConsoleEmail, label="Email"),
                VariantSpec(id="slack", model=ConsoleSlack, label="Slack"),
            ]
        ),
        selected_id="email",
        discriminator="class_name",
        persistence="inline_discriminator",
    )
    out = tmp_path / "config.yaml"
    input_func, prompts = _input_from(["slack", "#alerts"])

    run_console_app(tree, out, input_func=input_func, print_func=lambda _: None)

    assert prompts[0] == "variant (email/slack) [email]: "
    assert prompts[1] == "channel [#ops]: "
    assert "class_name: slack" in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the failing console test**

Run:

```bash
uv run python -m pytest tests/unit/test_console_renderer.py::test_console_prompts_for_root_variant_before_fields -q
```

Expected: FAIL because console mode does not prompt for root variants.

- [ ] **Step 3: Implement root variant prompt**

Modify `src/pydantic_studio/renderers/console.py`.

Add helper:

```python
def _prompt_root_variant(
    tree: Any,
    input_func: InputFunc,
    print_func: PrintFunc,
) -> None:
    variant = getattr(tree, "variant", None)
    if variant is None:
        return
    labels = [option.id for option in variant.options]
    current = variant.selected_id
    while True:
        raw = input_func(f"variant ({'/'.join(labels)}) [{current}]: ")
        if raw == "":
            return
        if raw not in labels:
            print_func(f"choose one of: {', '.join(labels)}")
            continue
        result = tree.select_root_variant(raw)
        if result.ok:
            return
        print_func("; ".join(result.errors) or "invalid variant")
```

Call it near the start of `run_console_app` before `_edit_group`:

```python
        _prompt_root_variant(tree, input_func, print_func)
```

- [ ] **Step 4: Run console tests**

Run:

```bash
uv run python -m pytest tests/unit/test_console_renderer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/console.py tests/unit/test_console_renderer.py
git commit -m "feat: support console root variant selection"
```

---

### Task 5: Web Page Selector

**Files:**
- Modify: `frontend/src/api/schemas.ts`
- Modify: `frontend/src/api/mutations.ts`
- Create: `frontend/src/components/form/VariantSelector.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `tests/e2e/test_variant_selector.py`

- [ ] **Step 1: Add failing Playwright e2e test**

Create `tests/e2e/test_variant_selector.py`:

```python
from __future__ import annotations

from pydantic import BaseModel

from pydantic_studio.variants import VariantRegistry, VariantSpec, build_variant_form_tree


class WebEmail(BaseModel):
    address: str = "ops@example.com"


class WebSlack(BaseModel):
    channel: str = "#ops"


def test_web_variant_selector_switches_root_model(page, fastapi_server):
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=WebEmail, label="Email"),
                VariantSpec(id="slack", model=WebSlack, label="Slack"),
            ]
        ),
        selected_id="email",
        discriminator="class_name",
        persistence="inline_discriminator",
    )
    with fastapi_server(tree) as base_url:
        page.goto(f"{base_url}/static/dist/index.html")
        page.get_by_label("Variant").select_option("slack")

        page.get_by_label("channel").fill("#alerts")
        preview = page.get_by_test_id("tree-preview")
        assert "class_name: slack" in preview.inner_text()
        assert "channel: '#alerts'" in preview.inner_text()
```

- [ ] **Step 2: Run the failing e2e test**

Run:

```bash
uv run python -m pytest tests/e2e/test_variant_selector.py -p playwright -o "addopts=-ra" -q
```

Expected: FAIL because the SPA does not parse or render `variant`.

- [ ] **Step 3: Add variant schemas and mutation type**

Modify `frontend/src/api/schemas.ts`:

```ts
export interface VariantOptionData {
  id: string;
  label: string;
  description: string | null;
  model_type_name: string;
}

export interface VariantStateData {
  options: VariantOptionData[];
  selected_id: string;
  discriminator: string | null;
  persistence: "metadata" | "inline_discriminator" | "model_field";
}

export const VariantOptionSchema = z.object({
  id: z.string(),
  label: z.string(),
  description: z.string().nullable(),
  model_type_name: z.string(),
});

export const VariantStateSchema = z.object({
  options: z.array(VariantOptionSchema),
  selected_id: z.string(),
  discriminator: z.string().nullable(),
  persistence: z.enum(["metadata", "inline_discriminator", "model_field"]),
});
```

Add to the form tree schema:

```ts
variant: VariantStateSchema.nullable(),
```

Modify `frontend/src/api/mutations.ts`:

```ts
| { op: "select_root_variant"; variant_id: string };
```

- [ ] **Step 4: Add the web VariantSelector component**

Create `frontend/src/components/form/VariantSelector.tsx`:

```tsx
import type { VariantStateData } from "@/api/schemas";
import { useApplyMutation } from "@/api/mutations";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

export function VariantSelector({ variant }: { variant: VariantStateData }) {
  const mutation = useApplyMutation();
  const selected = variant.options.find((option) => option.id === variant.selected_id);

  return (
    <div className="space-y-2 rounded-md border border-zinc-200 bg-zinc-50 p-3">
      <Label htmlFor="variant-selector" className="text-sm font-medium">
        Variant
      </Label>
      <Select
        value={variant.selected_id}
        onValueChange={(variant_id) =>
          mutation.mutate({ op: "select_root_variant", variant_id })
        }
      >
        <SelectTrigger id="variant-selector" aria-label="Variant">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {variant.options.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {selected?.description && (
        <p className="text-xs text-zinc-500">{selected.description}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Render the selector inside the web page**

Modify `frontend/src/App.tsx`:

```tsx
import { VariantSelector } from "@/components/form/VariantSelector";
```

Render it between the header and submit error banner:

```tsx
{data.variant && <VariantSelector variant={data.variant} />}
```

- [ ] **Step 6: Build the SPA bundle**

Run:

```bash
cd frontend && pnpm build
```

Expected: PASS and updates under `src/pydantic_studio/renderers/html/static/dist/`.

- [ ] **Step 7: Run focused web tests**

Run:

```bash
uv run python -m pytest tests/unit/test_html_static_bundle.py tests/e2e/test_variant_selector.py -p playwright -o "addopts=-ra" -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/schemas.ts frontend/src/api/mutations.ts frontend/src/components/form/VariantSelector.tsx frontend/src/App.tsx src/pydantic_studio/renderers/html/static/dist tests/e2e/test_variant_selector.py
git commit -m "feat: add web root variant selector"
```

---

### Task 6: Textual TUI Selector

**Files:**
- Modify: `src/pydantic_studio/renderers/textual_/app.py`
- Modify: `src/pydantic_studio/renderers/textual_/widgets/field_list.py`
- Test: `tests/unit/test_tui_v2_type_matrix.py`

- [ ] **Step 1: Add failing TUI test**

Append to `tests/unit/test_tui_v2_type_matrix.py`:

```python
from pydantic_studio.variants import VariantRegistry, VariantSpec, build_variant_form_tree


class _TuiEmail(BaseModel):
    address: str = "ops@example.com"


class _TuiSlack(BaseModel):
    channel: str = "#ops"


@pytest.mark.asyncio
async def test_tui_root_variant_cycles_and_rebuilds_fields() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_TuiEmail),
                VariantSpec(id="slack", model=_TuiSlack),
            ]
        ),
        selected_id="email",
    )
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        field_list = app.screen.query_one(FieldListView)

        field_list.action_cycle_root_variant()
        await pilot.pause()

    assert tree.variant is not None
    assert tree.variant.selected_id == "slack"
    assert tree.root.find("channel") is not None
    assert tree.root.find("address") is None
```

- [ ] **Step 2: Run the failing TUI test**

Run:

```bash
uv run python -m pytest tests/unit/test_tui_v2_type_matrix.py::test_tui_root_variant_cycles_and_rebuilds_fields -q
```

Expected: FAIL because `FieldListView` has no `action_cycle_root_variant`.

- [ ] **Step 3: Add TUI cycle action**

Modify `src/pydantic_studio/renderers/textual_/widgets/field_list.py`:

```python
    def action_cycle_root_variant(self) -> None:
        variant = getattr(self._form_tree, "variant", None)
        if variant is None:
            self.notify("No root variants", severity="warning")
            return
        ids = [option.id for option in variant.options]
        current = ids.index(variant.selected_id)
        next_id = ids[(current + 1) % len(ids)]
        result = self._form_tree.select_root_variant(next_id)
        if not result.ok:
            self.notify("; ".join(result.errors), severity="error")
            return
        self._refresh_rows()
```

- [ ] **Step 4: Add a visible TUI selector row**

Modify the field-list composition so a variant row appears before normal root fields when `tree.variant` is not `None`. The row label must include the current selected id:

```python
label = f"Variant: {variant.selected_id}"
```

Bind `right` or `space` on that row to `action_cycle_root_variant()`, matching existing choice/union cycling behavior.

- [ ] **Step 5: Run TUI focused tests**

Run:

```bash
uv run python -m pytest tests/unit/test_tui_v2_type_matrix.py tests/unit/test_tui_v2_field_list.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/renderers/textual_/app.py src/pydantic_studio/renderers/textual_/widgets/field_list.py tests/unit/test_tui_v2_type_matrix.py
git commit -m "feat: support tui root variant selection"
```

---

### Task 7: Documentation and Examples

**Files:**
- Modify: `README.md`
- Modify: `docs/site/api.md`
- Modify: `docs/site/architecture.md`
- Create: `docs/site/examples/variant-selection.md`
- Modify: `docs/site/examples/index.md`
- Test: `tests/unit/test_docs_build.py`

- [ ] **Step 1: Document the generic API in README**

Add a short section under the CLI/frontend overview:

```markdown
### Variant Model Selection

For schemas where the user must choose one model from a registry, build a
variant tree instead of hard-coding the choice in your host CLI:

```python
from pydantic import BaseModel
from pydantic_studio import VariantRegistry, VariantSpec, build_variant_form_tree


class EmailSettings(BaseModel):
    address: str = "ops@example.com"


class SlackSettings(BaseModel):
    channel: str = "#ops"


tree = build_variant_form_tree(
    VariantRegistry(
        [
            VariantSpec(id="email", model=EmailSettings, label="Email"),
            VariantSpec(id="slack", model=SlackSettings, label="Slack"),
        ]
    ),
    discriminator="class_name",
    persistence="inline_discriminator",
)
```

Console prompts ask for the variant first. TUI and web render the selector
inside the editor; the web selector is part of the browser page and uses the
same mutation API as field edits.
```

- [ ] **Step 2: Add docs example page**

Create `docs/site/examples/variant-selection.md` with the same two-model example, the generated YAML:

```yaml
class_name: slack
channel: '#ops'
```

and the explicit statement:

```markdown
The registry is supplied by the caller. pydantic-studio does not import or
scan application packages to discover variants.
```

- [ ] **Step 3: Link docs navigation**

Modify `docs/site/examples/index.md`:

```markdown
- [Variant model selection](variant-selection.md) — choose one Pydantic model from a caller-supplied registry, then edit its fields.
```

Modify `docs/site/api.md` to list `VariantSpec`, `VariantRegistry`, and `build_variant_form_tree`.

Modify `docs/site/architecture.md` to describe root-level variant state as renderer metadata layered on top of the FormTree. State that `UnionNode` remains the static field-level union feature.

- [ ] **Step 4: Run docs validation**

Run:

```bash
uv run mkdocs build --strict
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/site/api.md docs/site/architecture.md docs/site/examples/variant-selection.md docs/site/examples/index.md
git commit -m "docs: describe variant model selection"
```

---

### Task 8: Full Validation

**Files:**
- No new files.

- [ ] **Step 1: Run Python unit suite**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run lint and type checks**

Run:

```bash
uv run ruff check
uv run pyright src/pydantic_studio
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend && pnpm build
```

Expected: PASS.

- [ ] **Step 4: Run browser e2e test**

Run:

```bash
uv run python -m pytest tests/e2e/test_variant_selector.py -p playwright -o "addopts=-ra" -q
```

Expected: PASS.

- [ ] **Step 5: Run docs build**

Run:

```bash
uv run mkdocs build --strict
```

Expected: PASS.

- [ ] **Step 6: Final commit if validation adjustments were needed**

```bash
git add .
git commit -m "test: validate variant model selection"
```

Skip this commit when the validation steps produce no file changes.

---

## Self-Review

- Spec coverage: The plan covers generic caller-supplied variants, web in-page selection, console/TUI/web parity, output persistence without host-project coupling, tests, and docs.
- Placeholder scan: The plan avoids host-specific identifiers and does not leave unspecified implementation surfaces.
- Type consistency: `VariantSpec`, `VariantRegistry`, `VariantState`, `VariantOption`, `build_variant_form_tree`, `select_root_variant`, and `to_output_python` are named consistently across tasks.
