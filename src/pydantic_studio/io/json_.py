"""JSON load + save for pydantic-studio.

JSON has no comment support (spec line 451 — accepted limitation).
``save_json`` uses ``model_dump_json(indent=2, by_alias=True)``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_studio.tree.builder import build_form_tree

if TYPE_CHECKING:
    from pydantic import BaseModel

    from pydantic_studio.tree.nodes import FormTree


def load_json(path: str | Path, schema: type[BaseModel]) -> FormTree:
    """Load a JSON file into a FormTree bound to ``schema``.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        json.JSONDecodeError: if the file is malformed.
        ValueError: if the JSON top-level value isn't an object.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        msg = f"expected JSON object at top level, got {type(data).__name__}"
        raise ValueError(msg)
    return build_form_tree(schema, existing=data)


def save_json(tree: FormTree, path: str | Path) -> None:
    """Write a FormTree to a JSON file with indent=2.

    Raises:
        ValidationFailedError: if the tree is incomplete/invalid.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(tree.to_output_python(by_alias=True), indent=2)

    fd, tmp = tempfile.mkstemp(prefix=".tmp-json-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
