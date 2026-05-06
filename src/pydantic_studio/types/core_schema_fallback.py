"""Fallback builder for user-defined types declaring ``__get_pydantic_core_schema__``.

When a Pydantic model field is typed with a class that is not a ``BaseModel``
subclass and not one of the primitives we have specific builders for (``str``,
``int``, ``list[T]``, etc.), but it *does* declare a Pydantic core schema, we
honour what the type told Pydantic about itself: introspect the schema, find
the underlying primitive (or container), and delegate to whichever builder
already handles that primitive.

Round-trip is automatic: ``FormTree.to_instance()`` calls
``schema_class.model_validate(data)``, which routes through the type's own
``_validate`` hook and reconstructs the user-defined instance from the raw
primitive held in the form.

See also: ``Registry`` (`src/pydantic_studio/types/registry.py`),
``default_registry`` (`src/pydantic_studio/tree/builder.py`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, TypeAdapter

from pydantic_studio.exceptions import NoBuilderError

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.nodes import AnyNode
    from pydantic_studio.types.registry import Registry


_TRANSPARENT_WRAPPERS = frozenset(
    {
        "function-after",
        "function-before",
        "function-wrap",
        "nullable",
        "default",
        "json-or-python",
    }
)

_PRIMITIVE_KIND_TO_TYPE: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "bytes": bytes,
    "decimal": Decimal,
}


class CoreSchemaFallbackBuilder:
    """Last-resort builder honouring ``__get_pydantic_core_schema__``.

    Matches user-defined types that are neither ``BaseModel`` subclasses
    (handled by ``GroupBuilder``) nor primitives with their own builder.
    Resolves the underlying Python type from the declared core schema and
    delegates to the registry — so the user's custom type ends up using
    ``StringNode`` / ``SequenceNode`` / ``MappingNode`` / etc. without any
    explicit builder registration.
    """

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: Any) -> bool:
        if not isinstance(type_, type):
            return False
        if issubclass(type_, BaseModel):
            return False  # GroupBuilder territory.
        if not hasattr(type_, "__get_pydantic_core_schema__"):
            return False
        # Builtin primitives don't declare this hook, so we never shadow them.
        return _resolve_underlying(type_) is not None

    def build(
        self,
        type_: type,
        field_info: FieldInfo,
        existing: Any,
    ) -> AnyNode:
        underlying = _resolve_underlying(type_)
        if underlying is None:
            # ``matches`` should have rejected this — defensive.
            raise NoBuilderError(type_)
        return self._registry.find(underlying).build(underlying, field_info, existing)


def _resolve_underlying(type_: type) -> type | None:
    """Inspect ``TypeAdapter(type_).core_schema`` and return the Python
    type that an existing builder can handle, or ``None`` if the schema
    is opaque (e.g. ``function-plain`` with no inner schema).
    """
    try:
        schema = TypeAdapter(type_).core_schema
    except Exception:  # pragma: no cover — TypeAdapter raises for malformed schemas
        return None
    return _schema_to_type(schema)


def _schema_to_type(schema: Any) -> type | None:
    """Recursively map a ``core_schema`` dict to a Python type.

    Returns ``None`` for shapes the fallback cannot serve (e.g. opaque
    function-plain validators, definition references, custom unions).
    Letting these fall through preserves the existing ``NoBuilderError``
    contract so genuinely unsupported types are flagged loudly.
    """
    if not isinstance(schema, dict):
        return None
    kind = schema.get("type")
    if kind in _TRANSPARENT_WRAPPERS:
        inner = schema.get("schema")
        return _schema_to_type(inner) if inner is not None else None
    if kind in _PRIMITIVE_KIND_TO_TYPE:
        return _PRIMITIVE_KIND_TO_TYPE[kind]
    if kind == "list":
        item = _schema_to_type(schema.get("items_schema"))
        return list[item] if item is not None else list[str]
    if kind == "set":
        item = _schema_to_type(schema.get("items_schema"))
        return set[item] if item is not None else set[str]
    if kind == "tuple":
        items = schema.get("items_schema") or []
        if isinstance(items, list) and items:
            resolved = [_schema_to_type(s) for s in items]
            if all(t is not None for t in resolved):
                return tuple[tuple(resolved)]  # type: ignore[misc]
        return None
    if kind == "dict":
        key = _schema_to_type(schema.get("keys_schema") or {"type": "str"}) or str
        value = _schema_to_type(schema.get("values_schema") or {"type": "str"}) or str
        return dict[key, value]
    return None
