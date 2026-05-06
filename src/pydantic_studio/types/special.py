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


def _secret_kind(type_: Any) -> str | None:
    """Detect SecretStr / SecretBytes; return ``"str"``, ``"bytes"``, or None."""
    unwrapped = strip_annotated(type_)
    name = getattr(unwrapped, "__name__", "")
    module = getattr(unwrapped, "__module__", "")
    if not module.startswith("pydantic"):
        return None
    if name == "SecretStr":
        return "str"
    if name == "SecretBytes":
        return "bytes"
    return None


def _coerce_secret_existing(existing: Any) -> Any:
    """Unwrap a SecretStr/SecretBytes instance into its raw value, leaving
    str/bytes/None unchanged."""
    from pydantic import SecretBytes, SecretStr

    if isinstance(existing, (SecretStr, SecretBytes)):
        return existing.get_secret_value()
    return existing


class SecretBuilder:
    """Matches ``pydantic.SecretStr`` and ``pydantic.SecretBytes``."""

    def matches(self, type_: type) -> bool:
        return _secret_kind(type_) is not None

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        from pydantic_studio.tree.nodes import SecretNode as _SecretNode

        kind = _secret_kind(type_)
        if kind is None:  # pragma: no cover
            raise RuntimeError("SecretBuilder.build called with non-secret type")
        default = _coerce_secret_existing(_default(field_info))
        existing_v = _coerce_secret_existing(existing)
        return _SecretNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            secret_kind=kind,  # type: ignore[arg-type]
            value=existing_v if existing_v is not None else default,
            default=default,
        )
