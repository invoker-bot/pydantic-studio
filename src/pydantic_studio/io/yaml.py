"""YAML round-trip I/O via ``ruamel.yaml``.

``load_yaml`` reads a file into a ``CommentedMap`` (preserves comments
and key order), builds a ``FormTree`` from the values, and stashes the
CommentedMap on the tree for ``save_yaml`` to use as a comment source.

``save_yaml`` (Tasks 8-9) writes a schema-ordered CommentedMap whose
values come from ``tree.to_python()`` and whose comments come from the
stashed source (preserving user comments) or from ``FieldInfo.description``
(auto-generated for new keys).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML

from pydantic_studio.tree.builder import build_form_tree

if TYPE_CHECKING:
    from pydantic import BaseModel

    from pydantic_studio.tree.nodes import FormTree


def _yaml() -> YAML:
    """Build a ruamel YAML instance configured for round-trip I/O."""
    y = YAML(typ="rt")
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def load_yaml(path: str | Path, schema: type[BaseModel]) -> FormTree:
    """Load a YAML file into a FormTree bound to ``schema``.

    Args:
        path: Path to a YAML file. Accepts either a string or a Path.
        schema: A Pydantic BaseModel subclass — drives field-level
            type construction.

    Returns:
        FormTree with values populated from the file. Fields absent from
        the file get their schema defaults. Fields in the file but not in
        the schema are dropped (silent in v0.0.4; per spec O-1 future
        versions will warn to stderr or fail under ``--strict``).
        ``tree.yaml_source`` carries the parsed CommentedMap for save_yaml's
        comment-preservation pass.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ruamel.yaml.YAMLError: If the file is not valid YAML.
    """
    path = Path(path)
    yaml = _yaml()
    with path.open("r", encoding="utf-8") as f:
        cm: Any = yaml.load(f)
    if cm is None:  # empty file
        cm = {}
    # CommentedMap is a dict subclass — pass directly to build_form_tree.
    # Unknown keys are filtered automatically because GroupBuilder iterates
    # only over schema fields.
    tree = build_form_tree(schema, existing=dict(cm))
    tree.yaml_source = cm
    return tree


# Stub — implemented in Tasks 8-9.
def save_yaml(tree: FormTree, path: Path) -> None:
    raise NotImplementedError("save_yaml lands in Task 8")
