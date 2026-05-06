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

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from pydantic_studio.tree.builder import build_form_tree

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

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


def save_yaml(tree: FormTree, path: str | Path) -> None:
    """Write a FormTree to a YAML file with smart-comment generation.

    The tree is first materialized via ``tree.to_instance()`` so that
    schema defaults are resolved into the output (a fresh tree with all
    defaults still produces a populated YAML rather than ``{}``). The
    resulting model is then dumped, schema-ordered, into a CommentedMap
    whose comments come from each field's ``FieldInfo.description``
    (T8 — new files). T9 will extend this to source comments from a
    stashed CommentedMap when one is available, preserving user edits;
    this docstring will be revised at that time.

    Behavior (T8):
    - Builds a new CommentedMap with description comments derived from
      ``FieldInfo.description``, regardless of whether ``path`` exists
      or ``tree.yaml_source`` is set. (T9 will branch on yaml_source.)

    The write is atomic: writes to a temp file in the same directory,
    then ``os.replace``s into place. Parent directories are created as
    needed (mirroring ``draft_save``).

    Raises:
        pydantic_studio.ValidationFailedError: If ``tree`` does not yet
            represent a valid instance of its schema (e.g. required
            fields are unset). Propagated from ``tree.to_instance()``.
            The temp file is cleaned up.
        ValueError: If ``tree.schema_class`` is None.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    schema = tree.schema_class
    if schema is None:
        msg = "tree.schema_class is None; cannot derive description comments"
        raise ValueError(msg)

    # Run through validation so schema defaults are resolved into concrete
    # values — ``tree.to_python()`` alone omits keys whose nodes are unset,
    # which would produce an empty YAML file for a brand-new tree.
    instance = tree.to_instance()
    data = instance.model_dump(mode="python")
    cm = _build_commented_map(data, schema)
    yaml = _yaml()

    fd, tmp = tempfile.mkstemp(prefix=".tmp-yaml-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(cm, f)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _build_commented_map(
    data: dict[str, Any], schema: type[BaseModel]
) -> CommentedMap:
    """Construct a CommentedMap whose keys follow ``schema``'s definition
    order and whose entries carry description comments.

    Nested BaseModel fields recurse — their nested CommentedMaps also get
    description comments per the nested schema's FieldInfo.
    """
    cm = CommentedMap()
    for field_name, field_info in schema.model_fields.items():
        if field_name not in data:
            continue
        value = data[field_name]
        nested_schema = _nested_schema_class(field_info)
        if isinstance(value, dict) and nested_schema is not None:
            cm[field_name] = _build_commented_map(value, nested_schema)
        else:
            cm[field_name] = value
        if field_info.description:
            # Place description as a comment BEFORE the key.
            cm.yaml_set_comment_before_after_key(
                field_name,
                before=field_info.description,
            )
    return cm


def _nested_schema_class(field_info: FieldInfo) -> type[BaseModel] | None:
    """If ``field_info`` is a BaseModel field, return the model class.
    Otherwise return None.

    Used by ``_build_commented_map`` to recurse into nested groups for
    description-comment generation.
    """
    annotation = field_info.annotation
    if annotation is None:
        return None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None
