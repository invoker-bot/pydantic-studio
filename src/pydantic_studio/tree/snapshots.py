"""Snapshot serialization helpers used by FormTree.

A snapshot is the bytes from ``model_dump_json`` of the FormTree's root.
We store the *root only* (not the full FormTree) so the snapshot list
itself doesn't appear inside snapshots.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import GroupNode


def take(root: GroupNode) -> bytes:
    """Serialize a root node into a snapshot."""
    return root.model_dump_json().encode("utf-8")


def restore(snapshot: bytes) -> GroupNode:
    """Reconstruct a root node from a snapshot."""
    from pydantic_studio.tree.nodes import GroupNode

    return GroupNode.model_validate_json(snapshot)
