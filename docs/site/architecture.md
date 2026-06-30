# Architecture

pydantic-studio has three layers, in dependency order from the bottom up:

## Form tree — the canonical state

The `FormTree` is a Pydantic v2 hierarchy mirroring the user's schema.
Every field is a `FormNode` subclass (24 of them total): `StringNode`,
`IntNode`, `EnumNode`, `SequenceNode`, `MappingNode`, `UnionNode`,
`GroupNode`, etc. The discriminator is the `kind` field; nested nodes
form a tree rooted at a `GroupNode`.

**The tree is the single source of truth.** Renderers translate user
intent into mutations (`tree.set_value("path.to.field", value)`) and
translate tree state into pixels — they own no canonical state.

Mutations follow a **validate-first contract**: `set_value()` runs the
node's `validate_value()` first; on failure, no mutation occurs and the
returned `ValidationResult.fail(errors)` reports the issue. On success,
a snapshot is pushed to the undo ring before the mutation.

## I/O — format-aware load/save

YAML round-trip (`load_yaml` / `save_yaml`) uses `ruamel.yaml.YAML(typ='rt')`
to preserve user-edited comments. New keys get description comments from
`Field(description=...)`. Smart writer rules in spec §10.1 — schema-order
field emission, drop-deleted-fields, etc.

TOML round-trip uses stdlib `tomllib` (read) + `tomlkit` (write). JSON
uses stdlib `json` + `model_dump_json(indent=2)`. The
`load_config`/`save_config` dispatchers pick the right format based on
file extension.

## Renderers — frontends

Three interactive renderers and the CLI commands share the same FormTree
mutation API:

- **Console prompts** (`pydantic_studio.renderers.console`) — sequential
  stdin/stdout questions. Blank answers keep current values, and completion
  writes through the normal save dispatch.
- **Textual TUI** (`pydantic_studio.renderers.textual_`) — `StudioApp` /
  `StudioScreen` + per-node-kind widgets. Tested via `App.run_test()`
  and `Pilot`.
- **HTML browser** (`pydantic_studio.renderers.html`) — ASGI app with a
  bundled React SPA. Heartbeat polling detects abandoned tabs.
- **CLI shorthand** (`pydantic_studio.cli`) — `fill`, `run`, `check`,
  `edit`, `show`, `version`. Uses typer.

Adding another renderer (e.g., a Tk desktop app) means implementing one
new module under `renderers/`. The tree stays untouched.

## Root model variants

Some applications need one editor entry point that can produce different
Pydantic root model classes. pydantic-studio models this with
`VariantRegistry` and `VariantSpec` rather than a project-specific
dependency. `build_variant_form_tree()` builds the selected model's
normal `FormTree` and attaches serializable variant metadata:

- `options` — stable ids, labels, descriptions, and model type names
- `selected_id` — the currently selected root model
- `discriminator` — optional output key such as `class_name`
- `persistence` — `metadata` by default, or `inline_discriminator` to
  write the selected id into the saved config

Renderers own the interaction style. Console asks one root-variant
question before field prompts. Textual TUI renders a synthetic `Variant`
row at the top of the root form and maps `←`/`→` to
`select_root_variant()`. The web SPA renders a page-level selector and
sends the same mutation. The selected model's fields are rebuilt through
the regular builder registry, so this stays generic across domains.

### Standalone launchers vs embedded adapters

`run_app(...)` and `run_html_app(...)` own the process-facing lifecycle:
terminal app startup, browser opening, loopback port binding, and blocking until
`EditOutcome`.

Embedded adapters expose the same editor inside a host lifecycle:
`mount_html_app(...)` mounts the Web renderer into an ASGI host, and
`StudioScreen(EditSession(...))` mounts the TUI renderer inside a Textual app.
Both use the same `FormTree` mutation contract and the same `EditSession`
submit/cancel outcome.

## Cross-frontend identity

A **path** identifies any node in the tree (e.g.,
`database.replicas[2].host`). Renderers send the same path strings;
the tree's `set_value` and friends resolve them. Indexed children may
use either bracket or dotted numeric segments (`tags[0]` and `tags.0`
resolve to the same item). A draft saved from web
can be resumed in TUI, and vice versa, because the persisted format is
the FormTree's own JSON dump.

## Type registry

Each Pydantic type is built into the tree by a `NodeBuilder`. The
default registry knows 26 builders (one per type family — primitive,
choice, sequence, mapping, union, datetime, network, special). Users
can extend via `register_builder(MyCustomBuilder())` to support types
the default registry doesn't recognize.

## Snapshots + draft persistence

Every mutation pushes a snapshot (`tree.model_dump_json()` bytes) to a
bounded ring buffer. `tree.undo()` / `tree.redo()` restore from
snapshots.

The `tree.draft` module persists the full tree to
`<cwd>/.pydantic-studio.draft.json` for crash recovery. On startup, CLI
commands check for a newer draft via `find_draft()` +
`draft_newer_than()` and prompt to resume.

## Validation

Field-level validation runs on every mutation via
`FormNode.validate_value()`. Cross-field validation (Pydantic
`@model_validator`) runs only at submit time via `tree.to_instance()`,
so users can stage incomplete state without errors.
