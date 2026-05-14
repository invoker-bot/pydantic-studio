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

    ``mutation`` is the parsed JSON body — exactly the discriminated union
    described in spec §3.2. Handles ``set_value`` for scalars and the
    three sequence ops (``add_item``, ``remove_item``, ``move_item``);
    mapping / union ops land in later tasks. Unknown ops return a failure
    ValidationResult without touching the tree.
    """
    op = mutation.get("op")
    path = mutation.get("path", "")
    if op == "set_value":
        return tree.set_value(path, mutation.get("value"))
    if op == "add_item":
        return tree.add_item(path)
    if op == "remove_item":
        return tree.remove_item(path, int(mutation["index"]))
    if op == "move_item":
        return tree.move_item(path, int(mutation["from"]), int(mutation["to"]))
    return ValidationResult.fail([f"unknown op: {op!r}"])
