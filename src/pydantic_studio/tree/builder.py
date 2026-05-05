"""Type-to-Node dispatch via a pluggable registry.

The registry is a list of ``NodeBuilder`` instances. ``find`` returns the
first builder whose ``matches`` method returns True; new builders are
prepended so user registrations override defaults.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from pydantic_studio.exceptions import NoBuilderError
from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    FloatNode,
    GroupNode,
    IntNode,
    StringNode,
)

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.nodes import AnyNode


@runtime_checkable
class NodeBuilder(Protocol):
    """A builder turns one Python type into a FormNode."""

    def matches(self, type_: type) -> bool: ...

    def build(
        self,
        type_: type,
        field_info: FieldInfo,
        existing: Any,
    ) -> AnyNode: ...


class Registry:
    """Ordered list of builders. First match wins."""

    def __init__(self) -> None:
        self._builders: list[NodeBuilder] = []

    def register(self, builder: NodeBuilder) -> None:
        """Prepend ``builder``; new registrations take priority."""
        self._builders.insert(0, builder)

    def find(self, type_: type) -> NodeBuilder:
        for b in self._builders:
            if b.matches(type_):
                return b
        raise NoBuilderError(type_)

    def __len__(self) -> int:
        return len(self._builders)


_DEFAULT_REGISTRY: Registry | None = None


class GroupBuilder:
    """Recursive builder for any ``BaseModel`` subclass.

    This builder is special: it owns a reference to the registry so it can
    dispatch each field to whichever builder matches the field's annotation.
    """

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return isinstance(type_, type) and issubclass(type_, BaseModel)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> GroupNode:
        assert issubclass(type_, BaseModel)
        existing_dict: dict[str, Any] = existing if isinstance(existing, dict) else {}

        children: list[Any] = []
        for fname, finfo in type_.model_fields.items():
            child_type = finfo.annotation
            if child_type is None:
                child_type = str  # fallback — shouldn't happen in practice
            child_builder = self._registry.find(child_type)
            child = child_builder.build(child_type, finfo, existing_dict.get(fname))
            # The child builder didn't know the field name (it sees only the
            # type); we set it here from the parent's perspective. This avoids
            # the `FieldInfo.alias` hack and respects users' real aliases.
            child.name = fname
            children.append(child)

        return GroupNode(
            name=field_info.alias or type_.__name__,
            description=field_info.description,
            required=field_info.is_required(),
            schema_class=type_,
            fields=children,
        )


def default_registry() -> Registry:
    """Return the global default registry (lazily constructed).

    Subsequent tasks register concrete builders into this registry. v0.1
    stays single-process and does not need cross-thread isolation.
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        reg = Registry()
        # Register in *reverse* priority order — last registered wins for same type.
        # Primitive builders are mutually exclusive on type, so order doesn't matter
        # within this group, but we follow a stable convention.
        reg.register(StringBuilder())
        reg.register(IntBuilder())
        reg.register(FloatBuilder())
        reg.register(BoolBuilder())
        reg.register(DecimalBuilder())
        # GroupBuilder is registered last so it matches *any* BaseModel
        # only when no more-specific builder did. It also needs a back-
        # reference to the registry for recursive dispatch.
        reg.register(GroupBuilder(reg))
        _DEFAULT_REGISTRY = reg
    return _DEFAULT_REGISTRY


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
