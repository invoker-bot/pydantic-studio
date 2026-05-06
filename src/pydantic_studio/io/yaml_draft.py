"""save_draft_yaml — partial-tree YAML writer that skips validation."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_studio.io.yaml import _build_commented_map, _yaml

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree


def save_draft_yaml(tree: FormTree, path: str | Path) -> None:
    """Write the FormTree's current state as YAML, skipping validation.

    Use for mid-edit auto-save / draft recovery. Comments come from
    ``FieldInfo.description`` only.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    schema = tree.schema_class
    if schema is None:
        msg = "tree.schema_class is None"
        raise ValueError(msg)

    data = tree.to_python()
    cm = _build_commented_map(data, schema, source=None)
    yaml = _yaml()

    fd, tmp = tempfile.mkstemp(prefix=".tmp-yaml-draft-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(cm, f)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
