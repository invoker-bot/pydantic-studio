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
    ``root`` (the root GroupNode), and a top-level ``unsaved_count``
    (derived from the snapshot ring) for the header badge.
    """
    data = tree.model_dump(mode="json", exclude=_TREE_EXCLUDE)
    data["unsaved_count"] = len(tree.snapshots)
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


def dispatch_mutation(tree: FormTree, mutation: dict[str, Any]) -> ValidationResult:
    """Apply one mutation from the JSON API onto the FormTree.

    Translates the JSON op into the matching ``FormTree`` mutator. Returns
    the mutator's ``ValidationResult`` on success or a failure result if:
    - the ``op`` is unknown / missing
    - the request is missing a required key (``index``, ``key``, etc.)
    - a coercion fails (e.g., non-numeric ``index``)
    - the path doesn't resolve to a node

    Any of these surface to the client via the route layer's standard
    200 response (with ``validation.ok = false``); the route only 500s
    on a real server bug, never on a malformed request.
    """
    op = mutation.get("op")
    path = mutation.get("path", "")
    try:
        if op == "set_value":
            value = mutation.get("value")
            # If the target node is an EnumNode, the wire format is the
            # member's NAME (per EnumNode._serialize_member); coerce it
            # back to the actual enum member before validate_value sees
            # it. (The HTMX route does the same at routes.py:198-202.)
            value = _maybe_coerce_enum(tree, path, value)
            return tree.set_value(path, value)
        if op == "add_item":
            return tree.add_item(path)
        if op == "remove_item":
            return tree.remove_item(path, int(mutation["index"]))
        if op == "move_item":
            return tree.move_item(path, int(mutation["from"]), int(mutation["to"]))
        if op == "add_entry":
            return tree.add_entry(path, key=str(mutation["key"]))
        if op == "remove_entry":
            return tree.remove_entry(path, int(mutation["index"]))
        if op == "rename_key":
            return tree.rename_key(
                path, int(mutation["index"]), str(mutation["new_key"])
            )
        if op == "select_variant":
            return tree.select_variant(path, int(mutation["variant_index"]))
    except (KeyError, ValueError, TypeError) as exc:
        return ValidationResult.fail([f"mutation failed: {exc}"])
    return ValidationResult.fail([f"unknown op: {op!r}"])


def _maybe_coerce_enum(tree: FormTree, path: str, value: Any) -> Any:
    """If the node at ``path`` is an EnumNode and ``value`` is a string
    matching one of its choices' NAMES, return the corresponding enum
    member. Otherwise return ``value`` unchanged.

    Phase 1's JSON API serializes EnumNode.value as the member's name
    (see EnumNode._serialize_member). The reverse coercion belongs at
    the route/dispatcher layer because EnumNode.validate_value
    intentionally enforces the isinstance(value, Enum) invariant on
    its own boundary.
    """
    from pydantic_studio.tree.nodes import EnumNode

    if not isinstance(value, str):
        return value
    try:
        node = _resolve(tree, path)
    except Exception:
        return value   # let set_value's own path-resolution fail clearly
    if not isinstance(node, EnumNode):
        return value
    for name, member in node.choices:
        if name == value:
            return member
    return value  # not a recognized name; let validate_value reject


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
