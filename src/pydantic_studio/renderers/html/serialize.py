"""JSON serialization + mutation dispatch for the HTML renderer's JSON API.

The browser SPA built in later phases consumes ``tree_to_json`` to render
the form, and ``dispatch_mutation`` to apply edits. Both functions are
pure (no I/O, no FastAPI imports) so they can be unit-tested in isolation
from the route layer.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from pydantic_studio.tree.validation import ValidationResult

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree


# Fields on FormTree itself that should not ship over the wire:
# - schema_class: a Python class object, not JSON-serialisable
# - snapshots:    list[bytes] of prior tree states (undo ring); each
#                 snapshot is ~the size of the tree, so including it N
#                 times bloats every response by Nx
# - created_at, cursor, snapshot_limit, draft_path: internal history/draft controls.
#                 The SPA receives the stable, derived ``history`` state
#                 instead of these implementation details.
_TREE_EXCLUDE: set[str] = {
    "schema_class",
    "snapshots",
    "created_at",
    "cursor",
    "snapshot_limit",
    "draft_path",
}


def tree_to_json(tree: FormTree) -> dict[str, Any]:
    """Serialize a FormTree to a JSON-ready dict.

    The output shape mirrors §5.1 of the design spec: ``schema_name``,
    ``root`` (the root GroupNode), a top-level ``unsaved_count``
    (derived from the snapshot ring) for the header badge, and
    ``preview`` (YAML rendering of the effective config values via
    ``render_yaml_preview``) for the SPA's live-preview pane.
    """
    from pydantic_studio.renderers.html.render import render_yaml_preview

    data = tree.model_dump(mode="json", exclude=_TREE_EXCLUDE)
    _strip_node_internal_fields(data["root"])
    data["variant"] = (
        tree.variant.model_dump(mode="json") if tree.variant is not None else None
    )
    data["history"] = {
        "can_undo": tree.cursor > 0,
        "can_redo": tree.cursor + 1 < len(tree.snapshots),
    }
    data["unsaved_count"] = len(tree.snapshots)
    data["preview"] = render_yaml_preview(tree)
    return _json_safe_non_finite(data)


def _json_safe_non_finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN"
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {key: _json_safe_non_finite(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_json_safe_non_finite(child) for child in value]
    return value


def _strip_node_internal_fields(value: Any) -> None:
    """Remove node implementation details from the JSON API payload."""
    if isinstance(value, dict):
        value.pop("nullable", None)
        value.pop("emit_null", None)
        for child in value.values():
            _strip_node_internal_fields(child)
    elif isinstance(value, list):
        for child in value:
            _strip_node_internal_fields(child)


def validation_envelope(tree: FormTree) -> dict[str, Any]:
    """Aggregate the tree's current validation status as the API envelope.

    The envelope is returned alongside every tree-shaped response so the
    client can flag invalid fields without re-walking the tree. ``path``
    is the dotted form-tree path; ``message`` is the human-readable error.
    """
    from pydantic import ValidationError

    from pydantic_studio.exceptions import ValidationFailedError

    try:
        tree.to_instance()
    except ValidationFailedError as e:
        return {"ok": False, "errors": list(_iter_failed_errors(e))}
    except ValidationError as e:
        return {
            "ok": False,
            "errors": [
                {"path": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
                for err in e.errors()
            ],
        }
    return {"ok": True, "errors": []}


def _iter_failed_errors(e: Any) -> Any:
    """ValidationFailedError stores a list[str] of pre-formatted messages
    shaped ``"<path>: <message>"``. Split each back into structured form."""
    for raw in getattr(e, "errors", []) or []:
        text = str(raw)
        if ": " in text:
            path, _, message = text.partition(": ")
            yield {"path": path, "message": message}
        else:
            yield {"path": "", "message": text}


def _resolve(tree: FormTree, path: str) -> Any:
    """Resolve a target node using FormTree's path semantics."""
    return tree._resolve_path(path)


def _maybe_coerce_typed_value(tree: FormTree, path: str, value: Any) -> Any:
    """Translate wire-format values for a typed FormNode into the Python
    values its builders and ``validate_value`` expect.

    Most primitive nodes accept the SPA's wire format directly. String
    representations for scalar keys and caller-supplied JSON API payloads
    are coerced where the target node expects a concrete Python type. Whole
    structured replacements use the same recursive seed coercion as
    ``select_variant(seed=...)`` so JSON payloads can replace groups,
    sequences, mappings, and structured union variants without requiring
    browser callers to pre-materialize Python-native values.

    The kinds that need coercion are those whose ``validate_value`` does
    an exact-type check that the JSON wire format can't satisfy
    directly:

    - ``enum`` — wire value is the member's ``.name`` (str); look up the
      matching Enum member by name.
    - ``bool`` / ``int`` / ``float`` — mapping key inputs arrive as strings
      in the browser; parse them before node validation.
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
    when node lookup fails. The node's builder / ``validate_value`` still
    runs on whatever this returns, so a malformed wire string surfaces as
    the canonical validation error.
    """
    try:
        node = _resolve(tree, path)
    except Exception:
        return value  # let set_value's own path-resolution fail clearly

    return _maybe_coerce_set_value_for_node(tree, node, value)


def _maybe_coerce_set_value_for_node(tree: FormTree, node: Any, value: Any) -> Any:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.builder import default_registry
    from pydantic_studio.tree.nodes import (
        GroupNode,
        MappingNode,
        SequenceNode,
        UnionNode,
        _resolve_type_name,
    )

    if isinstance(node, UnionNode):
        candidates: list[Any] = []
        if node.selected is not None:
            candidates.append(_maybe_coerce_wire_seed_for_node(node.selected, value))

        registry = default_registry()
        for type_name in node.variant_type_names:
            try:
                variant_type = _resolve_type_name(type_name)
                variant_node = registry.find(variant_type).build(
                    variant_type, FieldInfo(annotation=variant_type), None
                )
            except Exception:
                continue
            candidates.append(_maybe_coerce_wire_seed_for_node(variant_node, value))

        for candidate in candidates:
            result, _, _ = tree._build_union_variant_for_value(node, candidate)
            if result.ok:
                return candidate

        if candidates:
            return candidates[0]
        return value

    if isinstance(node, (GroupNode, SequenceNode, MappingNode)):
        return _maybe_coerce_wire_seed_for_node(node, value)

    return _maybe_coerce_wire_value_for_node(node, value)


def _maybe_coerce_wire_value_for_node(node: Any, value: Any) -> Any:
    if not isinstance(value, str):
        return value

    from datetime import date, datetime, time, timedelta
    from decimal import Decimal, InvalidOperation
    from uuid import UUID

    from pydantic import TypeAdapter

    from pydantic_studio.tree.nodes import (
        BoolNode,
        BytesNode,
        DateNode,
        DatetimeNode,
        DecimalNode,
        EnumNode,
        FloatNode,
        IntNode,
        SecretNode,
        TimedeltaNode,
        TimeNode,
        UnionNode,
        UuidNode,
    )

    if isinstance(node, UnionNode) and node.selected is not None:
        return _maybe_coerce_wire_value_for_node(node.selected, value)
    if isinstance(node, BoolNode):
        lowered = value.strip().lower()
        if lowered in {"y", "yes", "true", "1", "on"}:
            return True
        if lowered in {"n", "no", "false", "0", "off"}:
            return False
        return value
    if isinstance(node, IntNode):
        try:
            return int(value)
        except ValueError:
            return value
    if isinstance(node, FloatNode):
        try:
            return float(value)
        except ValueError:
            return value
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


def _maybe_coerce_wire_seed_for_node(node: Any, seed: Any) -> Any:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.builder import default_registry
    from pydantic_studio.tree.nodes import (
        GroupNode,
        MappingNode,
        SequenceNode,
        UnionNode,
        _resolve_type_name,
    )

    if isinstance(node, GroupNode):
        if not isinstance(seed, dict):
            return seed
        from pydantic_studio.types.aliases import (
            input_value_or_missing_for_field,
            is_missing_input_value,
        )

        coerced_fields: dict[str, Any] = {}
        for child in node.fields:
            field_info = node.schema_class.model_fields.get(child.name)
            if field_info is None:
                continue
            value = input_value_or_missing_for_field(seed, child.name, field_info)
            if is_missing_input_value(value):
                continue
            coerced_fields[child.name] = _maybe_coerce_wire_seed_for_node(child, value)
        return coerced_fields
    if isinstance(node, SequenceNode):
        if not isinstance(seed, list | tuple):
            return seed
        values = list(seed)
        item_type_names = (
            node.slot_type_names
            if node.origin == "tuple_fixed"
            else [node.item_type_name] * len(values)
        )
        coerced_items: list[Any] = []
        registry = default_registry()
        for index, value in enumerate(values):
            if item_type_names is None or index >= len(item_type_names):
                coerced_items.append(value)
                continue
            item_type_name = item_type_names[index]
            if item_type_name is None:
                coerced_items.append(value)
                continue
            item_type = _resolve_type_name(item_type_name)
            item_node = registry.find(item_type).build(
                item_type, FieldInfo(annotation=item_type), None
            )
            coerced_items.append(_maybe_coerce_wire_seed_for_node(item_node, value))
        return coerced_items
    if isinstance(node, MappingNode):
        if not isinstance(seed, dict):
            return seed
        registry = default_registry()
        key_type = _resolve_type_name(node.key_type_name)
        value_type = _resolve_type_name(node.value_type_name)
        key_node = registry.find(key_type).build(
            key_type, FieldInfo(annotation=key_type), None
        )
        value_node = registry.find(value_type).build(
            value_type, FieldInfo(annotation=value_type), None
        )
        coerced_entries: dict[Any, Any] = {}
        for key, value in seed.items():
            coerced_key = _maybe_coerce_wire_seed_for_node(key_node, key)
            if coerced_key in coerced_entries:
                msg = f"duplicate key {coerced_key!r} after coercion"
                raise ValueError(msg)
            coerced_entries[coerced_key] = _maybe_coerce_wire_seed_for_node(
                value_node, value
            )
        return coerced_entries
    if isinstance(node, UnionNode) and node.selected is not None:
        return _maybe_coerce_wire_seed_for_node(node.selected, seed)
    return _maybe_coerce_wire_value_for_node(node, seed)


def _sequence_item_arg(tree: FormTree, path: str, value: Any) -> Any:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.builder import default_registry
    from pydantic_studio.tree.nodes import SequenceNode, _resolve_type_name

    try:
        node = _resolve(tree, path)
        if not isinstance(node, SequenceNode) or node.item_type_name is None:
            return value
        item_type = _resolve_type_name(node.item_type_name)
        item_node = default_registry().find(item_type).build(
            item_type, FieldInfo(annotation=item_type), None
        )
    except Exception:
        return value
    return _maybe_coerce_wire_seed_for_node(item_node, value)


def _union_variant_seed_arg(
    tree: FormTree, path: str, variant_index: int, seed: Any
) -> Any:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.builder import default_registry
    from pydantic_studio.tree.nodes import UnionNode, _resolve_type_name

    try:
        node = _resolve(tree, path)
        if not isinstance(node, UnionNode):
            return seed
        if not (0 <= variant_index < len(node.variant_type_names)):
            return seed
        variant_type = _resolve_type_name(node.variant_type_names[variant_index])
        variant_node = default_registry().find(variant_type).build(
            variant_type, FieldInfo(annotation=variant_type), None
        )
    except Exception:
        return seed
    return _maybe_coerce_wire_seed_for_node(variant_node, seed)


def _root_variant_seed_arg(tree: FormTree, variant_id: str, seed: Any) -> Any:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.builder import default_registry
    from pydantic_studio.tree.nodes import _resolve_type_name

    try:
        if tree.variant is None:
            return seed
        option = next(
            (candidate for candidate in tree.variant.options if candidate.id == variant_id),
            None,
        )
        if option is None:
            return seed
        model = _resolve_type_name(option.model_type_name)
        root_node = default_registry().find(model).build(
            model, FieldInfo(annotation=model), None
        )
    except Exception:
        return seed
    return _maybe_coerce_wire_seed_for_node(root_node, seed)


def _mapping_key_template(tree: FormTree, path: str) -> Any:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.builder import default_registry
    from pydantic_studio.tree.nodes import MappingNode, _resolve_type_name

    node = _resolve(tree, path)
    if not isinstance(node, MappingNode):
        msg = f"{path!r} is not a MappingNode"
        raise TypeError(msg)
    key_type = _resolve_type_name(node.key_type_name)
    return default_registry().find(key_type).build(
        key_type, FieldInfo(annotation=key_type), None
    )


def _mapping_value_template(tree: FormTree, path: str) -> Any:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.builder import default_registry
    from pydantic_studio.tree.nodes import MappingNode, _resolve_type_name

    node = _resolve(tree, path)
    if not isinstance(node, MappingNode):
        msg = f"{path!r} is not a MappingNode"
        raise TypeError(msg)
    value_type = _resolve_type_name(node.value_type_name)
    return default_registry().find(value_type).build(
        value_type, FieldInfo(annotation=value_type), None
    )


def _mapping_key_arg(tree: FormTree, mutation: dict[str, Any], key: str) -> Any:
    path = _path_arg(mutation)
    value = _required_arg(mutation, key)
    key_node = _mapping_key_template(tree, path)
    if key_node.kind == "string" and not isinstance(value, str):
        msg = f"{key} must be a string"
        raise TypeError(msg)
    return _maybe_coerce_wire_seed_for_node(key_node, value)


def _mapping_value_arg(tree: FormTree, path: str, value: Any) -> Any:
    value_node = _mapping_value_template(tree, path)
    return _maybe_coerce_wire_seed_for_node(value_node, value)


def _required_arg(mutation: dict[str, Any], key: str) -> Any:
    try:
        return mutation[key]
    except KeyError as exc:
        msg = f"{key} is required"
        raise ValueError(msg) from exc


def _required_string_arg(mutation: dict[str, Any], key: str) -> str:
    value = _required_arg(mutation, key)
    if not isinstance(value, str):
        msg = f"{key} must be a string"
        raise TypeError(msg)
    return value


def _required_int_arg(mutation: dict[str, Any], key: str) -> int:
    value = _required_arg(mutation, key)
    if type(value) is not int:
        msg = f"{key} must be an integer"
        raise TypeError(msg)
    return value


def _path_arg(mutation: dict[str, Any]) -> str:
    return _required_string_arg(mutation, "path")


def _op_arg(mutation: dict[str, Any]) -> str:
    return _required_string_arg(mutation, "op")


def dispatch_mutation(tree: FormTree, mutation: dict[str, Any]) -> ValidationResult:
    """Apply one mutation from the JSON API onto the FormTree.

    Translates the JSON op into the matching ``FormTree`` mutator. Returns
    the mutator's ``ValidationResult`` on success or a failure result if:
    - the ``op`` is unknown / missing
    - the request is missing a required key (``index``, ``key``, etc.)
    - a coercion fails (e.g., non-numeric ``index``)
    - the path is not a string
    - the path doesn't resolve to a node

    The route layer turns malformed requests into 400 responses and keeps
    valid mutation validation failures in the standard 200 response with
    ``validation.ok = false``.
    """
    try:
        op = _op_arg(mutation)
        if op == "set_value":
            path = _path_arg(mutation)
            value = _required_arg(mutation, "value")
            value = _maybe_coerce_typed_value(tree, path, value)
            return tree.set_value(path, value)
        if op == "undo":
            if tree.undo():
                return ValidationResult.ok()
            return ValidationResult.fail(["nothing to undo"])
        if op == "redo":
            if tree.redo():
                return ValidationResult.ok()
            return ValidationResult.fail(["nothing to redo"])
        if op == "add_item":
            path = _path_arg(mutation)
            if "value" in mutation:
                value = _sequence_item_arg(tree, path, mutation["value"])
                return tree.add_item(path, value)
            return tree.add_item(path)
        if op == "insert_item":
            path = _path_arg(mutation)
            index = _required_int_arg(mutation, "index")
            if "value" in mutation:
                value = _sequence_item_arg(tree, path, mutation["value"])
                return tree.insert_item(path, index, value)
            return tree.insert_item(path, index)
        if op == "remove_item":
            return tree.remove_item(
                _path_arg(mutation), _required_int_arg(mutation, "index")
            )
        if op == "move_item":
            return tree.move_item(
                _path_arg(mutation),
                _required_int_arg(mutation, "from"),
                _required_int_arg(mutation, "to"),
            )
        if op == "add_entry":
            path = _path_arg(mutation)
            key = _mapping_key_arg(tree, mutation, "key")
            if "value" in mutation:
                value = _mapping_value_arg(tree, path, mutation["value"])
                return tree.add_entry(
                    path,
                    key=key,
                    value=value,
                )
            return tree.add_entry(path, key=key)
        if op == "remove_entry":
            return tree.remove_entry(
                _path_arg(mutation), _required_int_arg(mutation, "index")
            )
        if op == "rename_key":
            path = _path_arg(mutation)
            return tree.rename_key(
                path,
                _required_int_arg(mutation, "index"),
                _mapping_key_arg(tree, mutation, "new_key"),
            )
        if op == "select_variant":
            path = _path_arg(mutation)
            variant_index = _required_int_arg(mutation, "variant_index")
            if "seed" in mutation:
                seed = _union_variant_seed_arg(
                    tree, path, variant_index, mutation["seed"]
                )
                return tree.select_variant(path, variant_index, seed)
            return tree.select_variant(
                path,
                variant_index,
            )
        if op == "select_root_variant":
            variant_id = _required_string_arg(mutation, "variant_id")
            if "seed" in mutation:
                seed = _root_variant_seed_arg(tree, variant_id, mutation["seed"])
                return tree.select_root_variant(variant_id, seed)
            return tree.select_root_variant(variant_id)
    except (KeyError, ValueError, TypeError) as exc:
        return ValidationResult.fail([f"mutation failed: {exc}"])
    return ValidationResult.fail([f"unknown op: {op!r}"])
