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
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from pydantic_studio.tree.builder import build_form_tree
from pydantic_studio.types.aliases import flat_field_input_keys

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
        the schema are dropped with a stderr warning.
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
    _warn_unknown_yaml_fields(_unknown_key_paths(cm, schema))
    # CommentedMap is a dict subclass — pass directly to build_form_tree.
    # Unknown keys are filtered automatically because GroupBuilder iterates
    # only over schema fields.
    tree = build_form_tree(schema, existing=dict(cm))
    tree.yaml_source = cm
    return tree


def save_yaml(tree: FormTree, path: str | Path) -> None:
    """Write a FormTree to a YAML file with smart-comment generation.

    Resolves the source CommentedMap in this priority order:

    1. ``tree.yaml_source`` (set by ``load_yaml``)
    2. The current contents of ``path`` (if it exists)
    3. None (write a fresh map with description comments)

    User comments from the source are preserved verbatim on fields that
    still exist in the schema (per spec §10.1 rule #3). New fields get
    description comments from ``FieldInfo.description``. Fields removed
    from the schema are dropped with a stderr warning.

    The tree is first materialized via ``tree.to_instance()`` so that
    schema defaults are resolved into the output (a fresh tree with all
    defaults still produces a populated YAML rather than ``{}``).

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

    # Resolve the source CommentedMap (priority: tree.yaml_source > on-disk).
    source: CommentedMap | None = None
    if tree.yaml_source is not None:
        source = (
            tree.yaml_source
            if isinstance(tree.yaml_source, CommentedMap)
            else None
        )
    elif path.exists():
        yaml_loader = _yaml()
        with path.open("r", encoding="utf-8") as f:
            loaded = yaml_loader.load(f)
        if isinstance(loaded, CommentedMap):
            source = loaded

    # Run through validation so schema defaults are resolved into concrete
    # values, with root-variant output metadata injected when configured.
    data = tree.to_output_python()
    _warn_unknown_yaml_fields(_dropped_source_key_paths(source, data, schema))
    cm = _build_commented_map(data, schema, source)
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
    data: dict[str, Any],
    schema: type[BaseModel],
    source: CommentedMap | None = None,
) -> CommentedMap:
    """Construct a CommentedMap with keys in schema definition order.

    Comment selection per key:

    1. If ``source`` has a user comment on this key, copy it forward.
    2. Otherwise, fall back to ``FieldInfo.description``.
    3. If neither, the key gets no comment.

    Document-level (top-of-file) comments on ``source`` are also copied
    onto the returned map — ruamel stores those on ``ca.comment`` rather
    than per-key, so the per-key copy alone would lose them.

    Nested BaseModel fields recurse — the nested source (if any) is
    threaded through.
    """
    cm = CommentedMap()
    # Document-level comment (top-of-file) lives on ca.comment, not in
    # ca.items[key]. Copy it once before per-key processing.
    if source is not None:
        src_ca = getattr(source, "ca", None)
        if src_ca is not None and src_ca.comment is not None:
            cm.ca.comment = src_ca.comment

    for key, value in data.items():
        if key in schema.model_fields:
            continue
        cm[key] = value
        _copy_comment_if_present(source, cm, key)

    for field_name, field_info in schema.model_fields.items():
        if field_name not in data:
            continue
        value = data[field_name]
        nested_schema = _nested_schema_class(field_info)
        nested_source: CommentedMap | None = None
        if (
            source is not None
            and field_name in source
            and isinstance(source[field_name], CommentedMap)
        ):
            nested_source = source[field_name]

        if isinstance(value, dict) and nested_schema is not None:
            cm[field_name] = _build_commented_map(
                value, nested_schema, nested_source
            )
        else:
            cm[field_name] = value

        # Copy the source comment if present, else use the description.
        copied = _copy_comment_if_present(source, cm, field_name)
        if not copied and field_info.description:
            cm.yaml_set_comment_before_after_key(
                field_name,
                before=field_info.description,
            )
    return cm


def _copy_comment_if_present(
    source: CommentedMap | None, target: CommentedMap, key: str
) -> bool:
    """If ``source`` has any comments associated with ``key``, copy them
    onto ``target``. Returns True if a comment was copied.

    ruamel.yaml stores per-key comments on the parent CommentedMap in
    ``ca.items`` (a dict keyed by child name → list of CommentToken).
    Copying the entry verbatim preserves every kind of per-key comment
    (before, inline, after) without parsing the structure.
    """
    if source is None or key not in source:
        return False
    src_ca = getattr(source, "ca", None)
    if src_ca is None:
        return False
    src_items = src_ca.items.get(key)
    if not src_items:
        return False
    # Detach the list so subsequent mutations on either side don't alias.
    target.ca.items[key] = list(src_items)
    return True


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


def _field_info_for_key(schema: type[BaseModel], key: str) -> FieldInfo | None:
    """Return field metadata addressed by a model field name or alias."""
    return next(
        (
            field_info
            for field_name, field_info in schema.model_fields.items()
            if key in flat_field_input_keys(field_name, field_info)
        ),
        None,
    )


def _unknown_key_paths(
    data: Mapping[Any, Any],
    schema: type[BaseModel],
    prefix: str = "",
) -> list[str]:
    """Return YAML keys that would be ignored by ``build_form_tree``."""
    paths: list[str] = []
    for key, value in data.items():
        key_str = str(key)
        path = f"{prefix}{key_str}"
        field_info = _field_info_for_key(schema, key_str)
        if field_info is None:
            paths.append(path)
            continue
        nested_schema = _nested_schema_class(field_info)
        if nested_schema is not None and isinstance(value, Mapping):
            paths.extend(_unknown_key_paths(value, nested_schema, f"{path}."))
    return paths


def _dropped_source_key_paths(
    source: Mapping[Any, Any] | None,
    data: Mapping[str, Any],
    schema: type[BaseModel],
    prefix: str = "",
) -> list[str]:
    """Return source keys that will not be written back by ``save_yaml``."""
    if source is None:
        return []

    paths: list[str] = []
    for key, value in source.items():
        key_str = str(key)
        path = f"{prefix}{key_str}"
        field_info = _field_info_for_key(schema, key_str)
        if field_info is None:
            if key_str not in data:
                paths.append(path)
            continue

        nested_schema = _nested_schema_class(field_info)
        nested_data = data.get(key_str)
        if (
            nested_schema is not None
            and isinstance(value, Mapping)
            and isinstance(nested_data, Mapping)
        ):
            paths.extend(
                _dropped_source_key_paths(
                    value,
                    nested_data,
                    nested_schema,
                    f"{path}.",
                )
            )
    return paths


def _warn_unknown_yaml_fields(paths: list[str]) -> None:
    if not paths:
        return
    joined = ", ".join(sorted(paths))
    print(
        f"pydantic-studio: dropping unknown YAML field(s) {joined}",
        file=sys.stderr,
    )
