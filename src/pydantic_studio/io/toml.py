"""TOML I/O via tomllib (read) + tomlkit (write).

``load_toml`` uses stdlib ``tomllib`` for parsing. ``save_toml`` uses
tomlkit to emit a Document with description comments derived from each
field's ``FieldInfo.description``.
"""

from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomlkit
from tomlkit import comment, document

from pydantic_studio.tree.builder import build_form_tree
from pydantic_studio.types.annotated import get_union_args, is_optional_type, strip_annotated

if TYPE_CHECKING:
    from pydantic import BaseModel
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.nodes import FormTree


def load_toml(path: str | Path, schema: type[BaseModel]) -> FormTree:
    """Load a TOML file into a FormTree bound to ``schema``.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
    """
    path = Path(path)
    with path.open("rb") as f:
        data = tomllib.load(f)
    return build_form_tree(schema, existing=data)


def save_toml(tree: FormTree, path: str | Path) -> None:
    """Write a FormTree to a TOML file with description comments.

    Tree is materialized via ``to_output_python(by_alias=True)`` so saved keys
    match the schema's external field names.

    Raises:
        ValidationFailedError: If the tree fails validation.
        ValueError: If schema_class is None.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    schema = tree.schema_class
    if schema is None:
        msg = "tree.schema_class is None; cannot derive description comments"
        raise ValueError(msg)

    data = tree.to_output_python(by_alias=True)
    doc = _build_document(data, schema)

    fd, tmp = tempfile.mkstemp(prefix=".tmp-toml-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _build_document(data: dict[str, Any], schema: type[BaseModel]) -> Any:
    """Construct a tomlkit Document with description comments per key."""
    doc = document()
    field_output_keys = {
        _output_key_for_field(field_name, field_info)
        for field_name, field_info in schema.model_fields.items()
    }
    for output_key, value in data.items():
        if value is None:
            continue
        if output_key in field_output_keys:
            continue
        doc.add(output_key, value)
    for field_name, field_info in schema.model_fields.items():
        output_key = _output_key_for_field(field_name, field_info)
        if output_key not in data:
            continue
        value = data[output_key]
        if value is None:
            continue
        nested_schema = _nested_schema_class(field_info)
        if isinstance(value, dict) and nested_schema is not None:
            doc.add(output_key, _build_document(value, nested_schema))
        else:
            if field_info.description:
                doc.add(comment(field_info.description))
            doc.add(output_key, value)
    return doc


def _output_key_for_field(field_name: str, field_info: FieldInfo) -> str:
    serialization_alias = getattr(field_info, "serialization_alias", None)
    if isinstance(serialization_alias, str) and serialization_alias:
        return serialization_alias
    if isinstance(field_info.alias, str) and field_info.alias:
        return field_info.alias
    return field_name


def _nested_schema_class(field_info: FieldInfo) -> type[BaseModel] | None:
    from pydantic import BaseModel

    annotation = strip_annotated(field_info.annotation)
    if annotation is None:
        return None
    if is_optional_type(annotation):
        nested_args = [
            strip_annotated(arg)
            for arg in get_union_args(annotation)
            if arg is not type(None)
        ]
        if len(nested_args) == 1:
            annotation = nested_args[0]
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None
