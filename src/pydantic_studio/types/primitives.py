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
from pydantic_studio.types.annotated import strip_annotated
from pydantic_studio.types.metadata import extract_constraints
from pydantic_studio.types.utils import field_default

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def _is_subclass_of(type_: Any, target: type) -> bool:
    """``True`` when ``type_`` (after Annotated-stripping) is a class
    derived from ``target``. The ``isinstance(..., type)`` guard rejects
    typing special forms (``Any``, ``Literal[...]``, ``Union[...]``)
    that would crash ``issubclass``.
    """
    unwrapped = strip_annotated(type_)
    return isinstance(unwrapped, type) and issubclass(unwrapped, target)


class StringBuilder:
    """Builds a StringNode for ``str`` and any subclass of it."""

    def matches(self, type_: type) -> bool:
        return _is_subclass_of(type_, str)

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
    """Builds an IntNode for ``int`` (and subclasses, excluding ``bool``)."""

    def matches(self, type_: type) -> bool:
        # ``bool`` is a subclass of ``int`` in Python — exclude it so
        # bare bool fields land in BoolBuilder.
        return _is_subclass_of(type_, int) and not _is_subclass_of(type_, bool)

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
    """Builds a FloatNode for ``float`` and any subclass of it."""

    def matches(self, type_: type) -> bool:
        return _is_subclass_of(type_, float)

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
    """Builds a BoolNode for ``bool`` (subclassing ``bool`` is not
    allowed in Python so ``issubclass`` collapses to identity)."""

    def matches(self, type_: type) -> bool:
        return _is_subclass_of(type_, bool)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> BoolNode:
        return BoolNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing,
            default=field_default(field_info),
        )


class DecimalBuilder:
    """Builds a DecimalNode for ``Decimal`` and any subclass of it."""

    def matches(self, type_: type) -> bool:
        return _is_subclass_of(type_, Decimal)

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
