"""Fallback builder for user-defined types declaring ``__get_pydantic_core_schema__``.

When a Pydantic model field is typed with a class that is not a ``BaseModel``
subclass and not one of the primitives we have specific builders for (``str``,
``int``, ``list[T]``, etc.), but it *does* declare a Pydantic core schema, we
honour what the type told Pydantic about itself: introspect the schema, find
the underlying primitive (or container), propagate any constraints declared
on the leaf (``ge`` / ``le`` / ``min_length`` / ``pattern`` / ...), and
delegate to whichever builder already handles that primitive.

Round-trip is automatic: ``FormTree.to_instance()`` calls
``schema_class.model_validate(data)``, which routes through the type's own
``_validate`` hook and reconstructs the user-defined instance from the raw
primitive held in the form.

See also: ``Registry`` (`src/pydantic_studio/types/registry.py`),
``default_registry`` (`src/pydantic_studio/tree/builder.py`),
``extract_constraints`` (`src/pydantic_studio/types/metadata.py`).
"""

from __future__ import annotations

import copy
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

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
    "date": date,
    "datetime": datetime,
    "time": time,
    "timedelta": timedelta,
    "uuid": UUID,
}

_NUMERIC_KINDS = frozenset({"int", "float", "decimal"})
_LENGTH_KINDS = frozenset({"str", "bytes", "list", "set", "dict"})


class CoreSchemaFallbackBuilder:
    """Last-resort builder honouring ``__get_pydantic_core_schema__``.

    Matches user-defined types that are neither ``BaseModel`` subclasses
    (handled by ``GroupBuilder``) nor primitives with their own builder.
    Resolves the underlying Python type from the declared core schema,
    extracts any leaf constraints (``ge`` / ``min_length`` / ``pattern`` /
    ...), and delegates to the registry — so the user's custom type ends
    up using ``StringNode`` / ``SequenceNode`` / ``MappingNode`` / etc.
    with the right limits, no explicit builder registration required.
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
        try:
            schema = TypeAdapter(type_).core_schema
        except Exception as exc:  # pragma: no cover — TypeAdapter rarely raises here
            raise NoBuilderError(type_) from exc
        underlying = _schema_to_type(schema)
        if underlying is None:
            # ``matches`` should have rejected this — defensive.
            raise NoBuilderError(type_)
        new_field_info = _augment_field_info(field_info, schema)
        return self._registry.find(underlying).build(underlying, new_field_info, existing)


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
    if kind == "literal":
        expected = schema.get("expected") or []
        if not expected:
            return None
        return Literal[tuple(expected)]  # type: ignore[misc]
    if kind == "union":
        return _resolve_union_members(schema.get("choices") or [])
    if kind == "tagged-union":
        choices = schema.get("choices") or {}
        # Tagged-union choices is a dict mapping tag → schema (or
        # alias-tag → schema). Dropping the discriminator hint is fine —
        # ``UnionBuilder`` probes variants by isinstance, not by tag.
        members = list(choices.values()) if isinstance(choices, dict) else list(choices)
        return _resolve_union_members(members)
    return None


def _resolve_union_members(choices: Any) -> type | None:
    """Resolve a list of core_schema choice entries to a Python ``Union``.

    Each entry is a schema dict — or, in some Pydantic shapes, a
    ``(schema, label)`` tuple where the first element is the schema.
    Returns ``None`` if any choice resolves to an unknown shape so the
    fallback fails open rather than producing a partially-typed union.
    Single-member unions collapse to that member; duplicates dedupe.
    """
    if not isinstance(choices, list) or not choices:
        return None
    members: list[Any] = []
    for choice in choices:
        if isinstance(choice, tuple):
            choice = choice[0]
        resolved = _schema_to_type(choice)
        if resolved is None:
            return None
        if resolved not in members:
            members.append(resolved)
    if not members:
        return None
    if len(members) == 1:
        return members[0]
    # Build a PEP 604 ``T1 | T2 | ...`` chain. ``UnionBuilder`` already
    # handles both ``typing.Union`` and ``types.UnionType`` origins (see
    # ``is_union_type`` in ``types.annotated``).
    result: Any = members[0]
    for t in members[1:]:
        result = result | t
    return result


def _augment_field_info(field_info: FieldInfo, schema: Any) -> FieldInfo:
    """Return a FieldInfo carrying constraints declared on the schema's
    underlying leaf, merged with whatever metadata the caller supplied.

    Schema-derived items go *first* so user-supplied items overwrite on
    conflict — matching ``extract_constraints``'s "last item wins"
    semantics. When the schema declares no constraints the original
    ``field_info`` is returned unchanged (no copy).
    """
    extracted = _extract_metadata_from_schema(schema)
    if not extracted:
        return field_info
    merged = list(extracted) + list(getattr(field_info, "metadata", None) or [])
    new_fi = copy.copy(field_info)
    new_fi.metadata = merged
    return new_fi


def _extract_metadata_from_schema(schema: Any) -> list[Any]:
    """Synthesize ``annotated_types``-shaped metadata items from a
    ``core_schema`` dict.

    Returns at most one ``SimpleNamespace`` carrying whichever of
    ``ge`` / ``le`` / ``gt`` / ``lt`` / ``multiple_of`` / ``min_length`` /
    ``max_length`` / ``pattern`` / ``max_digits`` / ``decimal_places``
    the schema's leaf declares — exactly the attribute names
    ``extract_constraints`` (`metadata.py`) reads. Returns ``[]`` when
    the leaf is unconstrained.

    Recurses through transparent wrappers (function validators,
    nullable, default) so a constraint declared one or more layers deep
    still surfaces on the form node.
    """
    if not isinstance(schema, dict):
        return []
    kind = schema.get("type")
    if kind in _TRANSPARENT_WRAPPERS:
        inner = schema.get("schema")
        return _extract_metadata_from_schema(inner) if inner is not None else []

    captured: dict[str, Any] = {}
    if kind in _NUMERIC_KINDS:
        for key in ("ge", "le", "gt", "lt", "multiple_of"):
            v = schema.get(key)
            if v is not None:
                captured[key] = v
        if kind == "decimal":
            for key in ("max_digits", "decimal_places"):
                v = schema.get(key)
                if v is not None:
                    captured[key] = v
    elif kind in _LENGTH_KINDS:
        for key in ("min_length", "max_length"):
            v = schema.get(key)
            if v is not None:
                captured[key] = v
        if kind == "str":
            pat = schema.get("pattern")
            if isinstance(pat, str):
                captured["pattern"] = pat

    return [SimpleNamespace(**captured)] if captured else []
