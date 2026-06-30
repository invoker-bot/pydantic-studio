"""Helpers for resolving Pydantic field input keys."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from pydantic import AliasChoices, AliasPath

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

InputPath = tuple[str | int, ...]
_MISSING = object()


def flat_field_input_keys(field_name: str, field_info: FieldInfo) -> tuple[str, ...]:
    """Return flat mapping keys accepted as input for a model field."""
    return tuple(
        path[0]
        for path in field_input_paths(field_name, field_info)
        if len(path) == 1 and isinstance(path[0], str)
    )


def field_input_paths(field_name: str, field_info: FieldInfo) -> tuple[InputPath, ...]:
    """Return mapping paths accepted as input for a model field."""
    paths: list[InputPath] = [(field_name,)]
    if field_info.alias:
        paths.append((field_info.alias,))

    validation_alias = field_info.validation_alias
    if isinstance(validation_alias, str):
        paths.append((validation_alias,))
    elif isinstance(validation_alias, AliasPath):
        paths.append(tuple(validation_alias.path))
    elif isinstance(validation_alias, AliasChoices):
        for choice in validation_alias.choices:
            if isinstance(choice, str):
                paths.append((choice,))
            elif isinstance(choice, AliasPath):
                paths.append(tuple(choice.path))

    serialization_alias = getattr(field_info, "serialization_alias", None)
    if isinstance(serialization_alias, str):
        paths.append((serialization_alias,))

    return tuple(dict.fromkeys(paths))


def input_value_for_field(
    data: Mapping[Any, Any],
    field_name: str,
    field_info: FieldInfo,
) -> Any:
    """Return the first non-None value matching a field input path."""
    for path in field_input_paths(field_name, field_info):
        value = value_at_input_path(data, path)
        if value is not _MISSING and value is not None:
            return value
    return None


def input_value_or_missing_for_field(
    data: Mapping[Any, Any],
    field_name: str,
    field_info: FieldInfo,
) -> Any:
    """Return the first matching field input value, preserving explicit None."""
    for path in field_input_paths(field_name, field_info):
        value = value_at_input_path(data, path)
        if value is not _MISSING:
            return value
    return _MISSING


def is_missing_input_value(value: object) -> bool:
    """True when ``value`` is the sentinel returned for absent input paths."""
    return value is _MISSING


def top_level_input_keys(field_name: str, field_info: FieldInfo) -> tuple[str, ...]:
    """Return first path segments that can address a field in input data."""
    keys = [
        str(path[0])
        for path in field_input_paths(field_name, field_info)
        if path and isinstance(path[0], str)
    ]
    return tuple(dict.fromkeys(keys))


def value_at_input_path(data: Mapping[Any, Any], path: InputPath) -> object:
    current: object = data
    for segment in path:
        if isinstance(current, Mapping):
            if segment not in current:
                return _MISSING
            current = current[segment]
        elif (
            isinstance(current, Sequence)
            and not isinstance(current, str | bytes | bytearray)
            and isinstance(segment, int)
        ):
            if segment < 0 or segment >= len(current):
                return _MISSING
            current = current[segment]
        else:
            return _MISSING
    return current
