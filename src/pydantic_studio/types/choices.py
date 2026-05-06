"""Builders for choice types: Enum and Literal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, get_args

from pydantic_studio.tree.nodes import EnumNode, LiteralNode
from pydantic_studio.types.annotated import is_enum_type, is_literal_type, strip_annotated
from pydantic_studio.types.utils import field_default

if TYPE_CHECKING:
    from enum import Enum

    from pydantic.fields import FieldInfo


class EnumBuilder:
    """Builds an EnumNode for any Enum subclass."""

    def matches(self, type_: type) -> bool:
        return is_enum_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> EnumNode:
        enum_cls: type[Enum] = strip_annotated(type_)
        default = field_default(field_info)
        choices = [(m.name, m) for m in enum_cls]
        return EnumNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
            enum_class_name=f"{enum_cls.__module__}.{enum_cls.__qualname__}",
            choices=choices,
        )


class LiteralBuilder:
    """Builds a LiteralNode for any ``Literal[...]`` annotation."""

    def matches(self, type_: type) -> bool:
        return is_literal_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> LiteralNode:
        choices = list(get_args(strip_annotated(type_)))
        default = field_default(field_info)
        return LiteralNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
            choices=choices,
        )
