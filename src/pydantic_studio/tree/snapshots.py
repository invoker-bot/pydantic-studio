"""Snapshot serialization helpers used by FormTree.

A snapshot is the bytes from ``model_dump_json`` of a ``GroupNode``; the
snapshot ring lives on ``FormTree.snapshots``. ``draft_save`` /
``draft_load`` handle full-FormTree persistence to disk.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path as FsPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel

    from pydantic_studio.tree.nodes import FormTree, GroupNode


def take(root: GroupNode) -> bytes:
    """Serialize a root node into a snapshot."""
    return root.model_dump_json().encode("utf-8")


def restore(snapshot: bytes) -> GroupNode:
    """Reconstruct a root node from a snapshot."""
    from pydantic_studio.tree.nodes import GroupNode

    return GroupNode.model_validate_json(snapshot)


def draft_save(tree: FormTree, target: FsPath) -> None:
    """Atomically write the FormTree (excluding schema_class) to ``target``.

    ``schema_class`` is omitted because it is a Python type object with no
    JSON representation; ``draft_load`` re-attaches it from the caller's
    ``schema`` argument via validation context.
    """
    target = FsPath(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = tree.model_dump_json(exclude={"schema_class"}).encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=".tmp-draft-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp, target)
    except Exception:
        FsPath(tmp).unlink(missing_ok=True)
        raise


def draft_load(source: FsPath, schema: type[BaseModel]) -> FormTree:
    """Load a previously-saved draft and re-bind ``schema_class`` from ``schema``."""
    from pydantic_studio.tree.nodes import FormTree

    raw = FsPath(source).read_bytes()
    return FormTree.model_validate_json(raw, context={"schema_class": schema})
