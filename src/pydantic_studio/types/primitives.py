"""Builders for str / int / float / bool / Decimal — constraint-aware."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    FloatNode,
    IntNode,
    StringNode,
)
from pydantic_studio.types.metadata import extract_constraints
from pydantic_studio.types.utils import field_default

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


class StringBuilder:
    """Builds a StringNode for bare ``str`` fields."""

    def matches(self, type_: type) -> bool:
        return type_ is str

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> StringNode:
        c = extract_constraints(field_info)
        return StringNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=field_default(field_info),
            min_length=c.get("min_length"),
            max_length=c.get("max_length"),
            pattern=c.get("pattern"),
        )


class IntBuilder:
    """Builds an IntNode for bare ``int`` fields (excluding ``bool``)."""

    def matches(self, type_: type) -> bool:
        # Exclude bool, which is a subclass of int in Python.
        return type_ is int

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> IntNode:
        c = extract_constraints(field_info)
        return IntNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=field_default(field_info),
            ge=c.get("ge"),
            le=c.get("le"),
            gt=c.get("gt"),
            lt=c.get("lt"),
            multiple_of=c.get("multiple_of"),
        )


class FloatBuilder:
    """Builds a FloatNode for bare ``float`` fields."""

    def matches(self, type_: type) -> bool:
        return type_ is float

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> FloatNode:
        c = extract_constraints(field_info)
        return FloatNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=field_default(field_info),
            ge=c.get("ge"),
            le=c.get("le"),
            gt=c.get("gt"),
            lt=c.get("lt"),
            multiple_of=c.get("multiple_of"),
        )


class BoolBuilder:
    """Builds a BoolNode for bare ``bool`` fields."""

    def matches(self, type_: type) -> bool:
        return type_ is bool

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> BoolNode:
        return BoolNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=field_default(field_info),
        )


class DecimalBuilder:
    """Builds a DecimalNode for bare ``Decimal`` fields."""

    def matches(self, type_: type) -> bool:
        return type_ is Decimal

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> DecimalNode:
        c = extract_constraints(field_info)
        return DecimalNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=field_default(field_info),
            max_digits=c.get("max_digits"),
            decimal_places=c.get("decimal_places"),
            ge=c.get("ge"),
            le=c.get("le"),
            gt=c.get("gt"),
            lt=c.get("lt"),
        )
