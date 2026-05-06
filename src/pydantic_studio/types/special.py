"""Builders for ``pathlib.Path``, ``uuid.UUID``, ``pydantic.SecretStr``,
``re.Pattern``, and ``bytes`` annotations.
"""

from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

from pydantic_studio.types.annotated import strip_annotated

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def _default(field_info: FieldInfo) -> Any:
    d = field_info.get_default(call_default_factory=True)
    return None if d is PydanticUndefined else d


def _path_to_str(value: Any) -> Any:
    """Coerce a Path/PurePath to its string form; pass everything else through."""
    if isinstance(value, PurePath):
        return str(value)
    return value


class PathBuilder:
    """Matches any ``pathlib.PurePath`` subclass (Path, PurePosixPath, etc.)."""

    def matches(self, type_: type) -> bool:
        unwrapped = strip_annotated(type_)
        if not isinstance(unwrapped, type):
            return False
        return issubclass(unwrapped, PurePath)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic_studio.tree.nodes import PathNode as _PathNode

        default = _path_to_str(_default(field_info))
        existing_v = _path_to_str(existing)
        return _PathNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing_v if existing_v is not None else default,
            default=default,
        )


def _is_uuid_type(type_: Any) -> bool:
    from uuid import UUID

    unwrapped = strip_annotated(type_)
    return unwrapped is UUID


class UuidBuilder:
    """Matches ``uuid.UUID``."""

    def matches(self, type_: type) -> bool:
        return _is_uuid_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic_studio.tree.nodes import UuidNode as _UuidNode

        default = _default(field_info)
        return _UuidNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )
