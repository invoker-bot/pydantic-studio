"""JSON serialization + mutation dispatch for the HTML renderer's JSON API.

The browser SPA built in later phases consumes ``tree_to_json`` to render
the form, and ``dispatch_mutation`` to apply edits. Both functions are
pure (no I/O, no FastAPI imports) so they can be unit-tested in isolation
from the route layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
