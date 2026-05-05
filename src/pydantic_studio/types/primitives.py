"""Builders for str / int / float / bool / Decimal."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    FloatNode,
    IntNode,
    StringNode,
)

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


class StringBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is str

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> StringNode:
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return StringNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
        )


class IntBuilder:
    def matches(self, type_: type) -> bool:
        # Exclude bool, which is a subclass of int in Python.
        return type_ is int

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> IntNode:
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return IntNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
        )


class FloatBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is float

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> FloatNode:
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return FloatNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
        )


class BoolBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is bool

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> BoolNode:
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return BoolNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
        )


class DecimalBuilder:
    def matches(self, type_: type) -> bool:
        return type_ is Decimal

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> DecimalNode:
        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        return DecimalNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=default,
        )
