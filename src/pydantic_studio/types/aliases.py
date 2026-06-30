"""Helpers for resolving Pydantic field input keys."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import AliasChoices

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def flat_field_input_keys(field_name: str, field_info: FieldInfo) -> tuple[str, ...]:
    """Return flat mapping keys accepted as input for a model field."""
    keys = [field_name]
    if field_info.alias:
        keys.append(field_info.alias)

    validation_alias = field_info.validation_alias
    if isinstance(validation_alias, str):
        keys.append(validation_alias)
    elif isinstance(validation_alias, AliasChoices):
        keys.extend(choice for choice in validation_alias.choices if isinstance(choice, str))

    return tuple(dict.fromkeys(keys))
