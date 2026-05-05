"""Builder for ``dict[K, V]`` containers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, get_args, get_origin

from pydantic_studio.tree.nodes import MappingNode
from pydantic_studio.types.annotated import strip_annotated
from pydantic_studio.types.metadata import extract_constraints

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry


def _fq(t: Any) -> str:
    return f"{getattr(t, '__module__', 'builtins')}.{getattr(t, '__qualname__', repr(t))}"


class DictBuilder:
    """Builds a MappingNode for ``dict[K, V]`` annotations."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return get_origin(strip_annotated(type_)) is dict

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> MappingNode:
        from pydantic.fields import FieldInfo as _FI

        unwrapped = strip_annotated(type_)
        args = get_args(unwrapped)
        key_type = args[0] if len(args) >= 1 else str
        value_type = args[1] if len(args) >= 2 else str
        c = extract_constraints(field_info)

        entries: list[tuple[Any, Any]] = []
        if isinstance(existing, dict):
            key_builder = self._registry.find(key_type)
            value_builder = self._registry.find(value_type)
            key_finfo = _FI(annotation=key_type)
            value_finfo = _FI(annotation=value_type)
            for raw_key, raw_value in existing.items():
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
            min_length=c.get("min_length"),
            max_length=c.get("max_length"),
        )
