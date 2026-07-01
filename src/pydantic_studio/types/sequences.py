"""Builders for list / set / tuple containers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, get_args, get_origin

from pydantic_studio.tree.nodes import SequenceNode
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
    if existing is None:
        return []
    if not isinstance(existing, (list, tuple, set, frozenset)):
        msg = (
            f"expected list/tuple/set for sequence value, got "
            f"{type(existing).__name__}"
        )
        raise TypeError(msg)
    item_finfo = field_info_from_annotation(item_type)
    item_builder = registry.find(item_type)
    items: list[Any] = []
    for i, v in enumerate(existing):
        v = parse_existing_if_transforming(item_finfo, v)
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
        seed = existing if existing is not None else field_default(field_info)
        return SequenceNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            origin="list",
            items=_build_items(self._registry, item_type, seed, field_info),
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
        seed = existing if existing is not None else field_default(field_info)
        return SequenceNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            origin="set",
            items=_build_items(self._registry, item_type, seed, field_info),
            item_type_name=_fq(item_type),
            min_length=c.get("min_length"),
            max_length=c.get("max_length"),
        )


class TupleBuilder:
    """Builds a SequenceNode for ``tuple[T, ...]`` (variadic) and
    ``tuple[T1, T2, ...]`` (fixed-length heterogeneous)."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        unwrapped = strip_annotated(type_)
        return unwrapped is tuple or get_origin(unwrapped) is tuple

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> SequenceNode:
        unwrapped = strip_annotated(type_)
        args = get_args(unwrapped)
        c = extract_constraints(field_info)

        if not args:
            # Plain ``tuple`` with no parameters — treat as ``tuple[Any, ...]``.
            return SequenceNode(
                name=field_info.alias or "<unnamed>",
                description=field_info.description,
                required=field_info.is_required(),
                origin="tuple",
                items=[],
                item_type_name=_fq(object),
                min_length=c.get("min_length"),
                max_length=c.get("max_length"),
            )

        is_variadic = len(args) == 2 and args[1] is Ellipsis
        if is_variadic:
            item_type = args[0]
            seed = existing if existing is not None else field_default(field_info)
            return SequenceNode(
                name=field_info.alias or "<unnamed>",
                description=field_info.description,
                required=field_info.is_required(),
                origin="tuple",
                items=_build_items(self._registry, item_type, seed, field_info),
                item_type_name=_fq(item_type),
                min_length=c.get("min_length"),
                max_length=c.get("max_length"),
            )

        # Fixed-length heterogeneous tuple: one slot per arg.
        items: list[Any] = []
        seed = existing if existing is not None else field_default(field_info)
        existing_seq = list(seed) if seed is not None else [None] * len(args)
        # Pad existing_seq to len(args) so missing slots become None children.
        while len(existing_seq) < len(args):
            existing_seq.append(None)
        for i, slot_type in enumerate(args):
            slot_finfo = field_info_from_annotation(slot_type)
            slot_builder = self._registry.find(slot_type)
            slot_existing = parse_existing_if_transforming(slot_finfo, existing_seq[i])
            child = slot_builder.build(slot_type, slot_finfo, slot_existing)
            child.name = str(i)
            items.append(child)
        return SequenceNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            origin="tuple_fixed",
            items=items,
            item_type_name=None,
            slot_type_names=[_fq(a) for a in args],
            min_length=len(args),
            max_length=len(args),
        )
