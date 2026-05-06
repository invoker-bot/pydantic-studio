"""Shared helpers for type builders.

Currently exports ``field_default`` — the canonical "give me the field's
default, normalized to None if Pydantic considers it undefined" function
that every builder needs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

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
