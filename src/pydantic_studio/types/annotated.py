"""Type-detection predicates and ``Annotated`` unwrapping.

Vendored from promptantic (MIT, https://github.com/phil65/promptantic,
``src/promptantic/type_utils.py``). Adapted to drop the prompt_toolkit-
specific helpers and to add ``is_optional_type`` / ``get_optional_inner``
which we need for UnionBuilder's None-aware fast path.
"""

from __future__ import annotations

import types as _types
from enum import Enum
from typing import (
    Annotated,
    Any,
    Literal,
    TypeGuard,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel


def strip_annotated(typ: Any) -> Any:
    """Return the underlying type, unwrapping ``Annotated[T, ...]`` once.

    Non-Annotated inputs pass through unchanged.
    """
    if get_origin(typ) is Annotated:
        return get_args(typ)[0]
    return typ


def is_union_type(typ: Any) -> TypeGuard[Any]:
    """True for both ``Union[A, B]`` and PEP 604 ``A | B``."""
    typ = strip_annotated(typ)
    origin = get_origin(typ)
    return origin is Union or origin is _types.UnionType


def get_union_args(typ: Any) -> tuple[Any, ...]:
    """Return the variant types of a union. Empty tuple if not a union."""
    if not is_union_type(typ):
        return ()
    return get_args(strip_annotated(typ))


def is_optional_type(typ: Any) -> bool:
    """True when ``typ`` is a union that includes ``None``.

    Includes single-variant ``T | None`` (the classical Optional) and
    multi-variant unions like ``int | str | None``.
    """
    if not is_union_type(typ):
        return False
    return type(None) in get_union_args(typ)


def get_optional_inner(typ: Any) -> Any:
    """Strip ``None`` from an Optional union.

    Examples:
        ``int | None``         -> ``int``
        ``int | str | None``   -> ``int | str``
        ``int``                -> ``int`` (passthrough)

    Note: when the input has 2+ non-None variants, the multi-variant
    return value is always reconstructed as a PEP 604 ``types.UnionType``
    (``A | B``), regardless of whether the input was ``typing.Union[A, B, None]``
    or ``A | B | None``. This means ``get_origin(result) is types.UnionType``
    on a multi-variant return; ``is_union_type`` (this module) covers both
    origins so internal callers are unaffected. External callers that
    branch on ``get_origin`` directly should be aware.
    """
    if not is_optional_type(typ):
        return typ
    non_none = tuple(t for t in get_union_args(typ) if t is not type(None))
    if len(non_none) == 1:
        return non_none[0]
    # Reconstruct a union of the remaining members.
    result: Any = non_none[0]
    for t in non_none[1:]:
        result = result | t
    return result


def is_literal_type(typ: Any) -> TypeGuard[Any]:
    """True for ``Literal[...]`` annotations."""
    typ = strip_annotated(typ)
    return get_origin(typ) is Literal


def is_enum_type(typ: Any) -> TypeGuard[type[Enum]]:
    """True for ``Enum`` subclasses."""
    typ = strip_annotated(typ)
    return isinstance(typ, type) and issubclass(typ, Enum)


def is_pydantic_model(typ: Any) -> TypeGuard[type[BaseModel]]:
    """True for ``BaseModel`` subclasses."""
    typ = strip_annotated(typ)
    return isinstance(typ, type) and issubclass(typ, BaseModel)
