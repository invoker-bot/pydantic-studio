"""JSON serialization + mutation dispatch for the HTML renderer's JSON API.

The browser SPA built in later phases consumes ``tree_to_json`` to render
the form, and ``dispatch_mutation`` to apply edits. Both functions are
pure (no I/O, no FastAPI imports) so they can be unit-tested in isolation
from the route layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_studio.tree.validation import ValidationResult

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree


# Fields on FormTree itself that should not ship over the wire:
# - schema_class: a Python class object, not JSON-serialisable
# - snapshots:    list[bytes] of prior tree states (undo ring); each
#                 snapshot is ~the size of the tree, so including it N
#                 times bloats every response by Nx
_TREE_EXCLUDE: set[str] = {"schema_class", "snapshots"}


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
    data["variant"] = (
        tree.variant.model_dump(mode="json") if tree.variant is not None else None
    )
    data["unsaved_count"] = len(tree.snapshots)
    data["preview"] = render_yaml_preview(tree)
    return data


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
    """Walk path segments to find the target node. Returns the node
    or raises if the path doesn't resolve."""
    from pydantic_studio.tree.nodes import GroupNode

    if not path:
        return tree.root
    node: Any = tree.root
    for seg in path.split("."):
        if isinstance(node, GroupNode):
            child = node.find(seg)
            if child is None:
                raise KeyError(seg)
            node = child
        else:
            raise KeyError(seg)
    return node


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
    value = mutation.get("path", "")
    if not isinstance(value, str):
        msg = "path must be a string"
        raise TypeError(msg)
    return value


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
        path = _path_arg(mutation)
        if op == "set_value":
            value = _required_arg(mutation, "value")
            value = _maybe_coerce_typed_value(tree, path, value)
            return tree.set_value(path, value)
        if op == "add_item":
            return tree.add_item(path)
        if op == "remove_item":
            return tree.remove_item(path, _required_int_arg(mutation, "index"))
        if op == "move_item":
            return tree.move_item(
                path,
                _required_int_arg(mutation, "from"),
                _required_int_arg(mutation, "to"),
            )
        if op == "add_entry":
            return tree.add_entry(path, key=_required_string_arg(mutation, "key"))
        if op == "remove_entry":
            return tree.remove_entry(path, _required_int_arg(mutation, "index"))
        if op == "rename_key":
            return tree.rename_key(
                path,
                _required_int_arg(mutation, "index"),
                _required_string_arg(mutation, "new_key"),
            )
        if op == "select_variant":
            return tree.select_variant(
                path, _required_int_arg(mutation, "variant_index")
            )
        if op == "select_root_variant":
            return tree.select_root_variant(
                _required_string_arg(mutation, "variant_id")
            )
    except (KeyError, ValueError, TypeError) as exc:
        return ValidationResult.fail([f"mutation failed: {exc}"])
    return ValidationResult.fail([f"unknown op: {op!r}"])
