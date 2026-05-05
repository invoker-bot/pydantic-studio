"""Builders for list / set / tuple containers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, get_args, get_origin

from pydantic_studio.tree.nodes import SequenceNode
from pydantic_studio.types.annotated import strip_annotated
from pydantic_studio.types.metadata import extract_constraints

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry


def _fq(t: Any) -> str:
    """Fully-qualified name of a type, for registry round-trip."""
    return f"{getattr(t, '__module__', 'builtins')}.{getattr(t, '__qualname__', repr(t))}"


def _build_items(
    registry: Registry,
    item_type: Any,
    existing: Any,
    parent_field_info: FieldInfo,
) -> list[Any]:
    """Build a child node for each value in ``existing``.

    Each child gets a synthetic FieldInfo carrying the item annotation —
    the parent's FieldInfo describes the *container*, not the items.
    """
    from pydantic.fields import FieldInfo

    if existing is None:
        return []
    item_finfo = FieldInfo(annotation=item_type)
    item_builder = registry.find(item_type)
    items: list[Any] = []
    for i, v in enumerate(existing):
        child = item_builder.build(item_type, item_finfo, v)
        child.name = str(i)
        items.append(child)
    return items


class ListBuilder:
    """Builds a SequenceNode (origin='list') for ``list[T]`` annotations."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return get_origin(strip_annotated(type_)) is list

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> SequenceNode:
        unwrapped = strip_annotated(type_)
        args = get_args(unwrapped)
        item_type = args[0] if args else str
        c = extract_constraints(field_info)
        return SequenceNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            origin="list",
            items=_build_items(self._registry, item_type, existing, field_info),
            item_type_name=_fq(item_type),
            min_length=c.get("min_length"),
            max_length=c.get("max_length"),
        )


class SetBuilder:
    """Builds a SequenceNode (origin='set') for ``set[T]`` annotations."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return get_origin(strip_annotated(type_)) is set

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> SequenceNode:
        unwrapped = strip_annotated(type_)
        args = get_args(unwrapped)
        item_type = args[0] if args else str
        c = extract_constraints(field_info)
        return SequenceNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            origin="set",
            items=_build_items(self._registry, item_type, existing, field_info),
            item_type_name=_fq(item_type),
            min_length=c.get("min_length"),
            max_length=c.get("max_length"),
        )
