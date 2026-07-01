"""Builder for ``dict[K, V]`` containers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, get_args, get_origin

from pydantic_studio.tree.nodes import MappingNode
from pydantic_studio.types.annotated import strip_annotated
from pydantic_studio.types.metadata import extract_constraints
from pydantic_studio.types.transforms import (
    field_info_from_annotation,
    parse_existing_if_transforming,
)
from pydantic_studio.types.utils import _fq, field_default

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry


class DictBuilder:
    """Builds a MappingNode for ``dict[K, V]`` annotations."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return get_origin(strip_annotated(type_)) is dict

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> MappingNode:
        unwrapped = strip_annotated(type_)
        args = get_args(unwrapped)
        key_type = args[0] if len(args) >= 1 else str
        value_type = args[1] if len(args) >= 2 else str
        c = extract_constraints(field_info)

        entries: list[tuple[Any, Any]] = []
        seed = existing if existing is not None else field_default(field_info)
        if isinstance(seed, dict):
            key_builder = self._registry.find(key_type)
            value_builder = self._registry.find(value_type)
            key_finfo = field_info_from_annotation(key_type)
            value_finfo = field_info_from_annotation(value_type)
            for raw_key, raw_value in seed.items():
                raw_key = parse_existing_if_transforming(key_finfo, raw_key)
                raw_value = parse_existing_if_transforming(value_finfo, raw_value)
                k_node = key_builder.build(key_type, key_finfo, raw_key)
                v_node = value_builder.build(value_type, value_finfo, raw_value)
                k_node.name = "key"
                v_node.name = "value"
                entries.append((k_node, v_node))

        return MappingNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            entries=entries,
            key_type_name=_fq(key_type),
            value_type_name=_fq(value_type),
            key_annotation=key_type,
            value_annotation=value_type,
            min_length=c.get("min_length"),
            max_length=c.get("max_length"),
        )
