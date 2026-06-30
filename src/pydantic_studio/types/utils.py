"""Shared helpers for type builders.

Exports ``field_default`` (the field's default normalized to None when
Pydantic considers it undefined) and ``_fq`` (the fully-qualified,
round-trippable type-name encoder every container builder uses to persist
its element types).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, get_args, get_origin

from pydantic_core import PydanticUndefined

from pydantic_studio.types.annotated import (
    get_union_args,
    is_literal_type,
    is_union_type,
    strip_annotated,
)

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def field_default(field_info: FieldInfo) -> Any:
    """Return ``field_info``'s default value, or ``None`` if undefined.

    Pydantic uses ``PydanticUndefined`` as the sentinel for "no default";
    builders work with concrete values + None, so we normalize here.
    Calls the default factory if present, since the field exists exactly
    when the factory has run successfully.
    """
    d = field_info.get_default(call_default_factory=True)
    return None if d is PydanticUndefined else d


def _fq(t: Any) -> str:
    """Fully-qualified, round-trippable name of a type.

    ``Annotated[T, ...]`` is unwrapped to ``T`` first: the bare alias's name is
    just ``typing.Annotated`` (the inner type lost), so the registry can't
    rebuild it and raises NoBuilderError — e.g. a union variant typed
    ``StrictBool`` (``Annotated[bool, Strict()]``) crashed ``select_variant``
    (Sentry hft-python #15). The metadata can't survive string serialization
    anyway, and every builder strips ``Annotated`` internally, so the
    round-trippable name is the inner type's name.

    Parameterized container and union element types are also encoded
    structurally. A PEP 604 union's
    bare ``__module__`` / ``__qualname__`` pair is only a display string
    such as ``types.str | my.Model``, which can't be imported later when a
    container mutator needs to build a new child node. We preserve each
    variant's own ``_fq`` encoding as JSON under ``typing.Union[...]``. The
    same applies to nested containers such as ``list[list[int]]``, where the
    bare name would collapse to ``builtins.list`` and lose its item type.

    Most other types then serialize as ``module.Qualname`` and rebuild via
    ``getattr``. ``Literal[...]`` is special: its bare name is just
    ``typing.Literal`` — the choices are lost, so the registry can't rebuild a
    LiteralNode and raises NoBuilderError when adding into a
    ``list[Literal[...]]`` (Sentry hft-python #13). We preserve the arguments as
    JSON (``typing.Literal["a", "b"]``); ``_resolve_type_name`` parses them back
    into the parametrized form. Exotic members JSON can't encode (bytes, enum)
    fall back to the bare name.
    """
    stripped = strip_annotated(t)
    if is_union_type(stripped):
        payload = json.dumps([_fq(arg) for arg in get_union_args(stripped)])
        return f"typing.Union{payload}"
    origin = get_origin(stripped)
    container_names = {
        list: "typing.List",
        dict: "typing.Dict",
        set: "typing.Set",
        tuple: "typing.Tuple",
    }
    if origin in container_names:
        payload = json.dumps([_fq(arg) for arg in get_args(stripped)])
        return f"{container_names[origin]}{payload}"
    if is_literal_type(stripped):
        choices = get_args(stripped)
        has_unsupported_choice = any(
            choice is not None
            and not isinstance(choice, str | int | float | bool)
            for choice in choices
        )
        if not has_unsupported_choice:
            try:
                payload = json.dumps(list(choices))
            except TypeError:
                pass  # unencodable member — fall through to the bare name
            else:
                return f"typing.Literal{payload}"
    return (
        f"{getattr(stripped, '__module__', 'builtins')}."
        f"{getattr(stripped, '__qualname__', repr(stripped))}"
    )
