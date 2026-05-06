"""Builders for IP / URL / Email annotations."""

from __future__ import annotations

from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
)
from typing import TYPE_CHECKING, Any, Literal

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import IpAddressNode, IpNetworkNode
from pydantic_studio.types.annotated import strip_annotated

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def _default(field_info: FieldInfo) -> Any:
    d = field_info.get_default(call_default_factory=True)
    return None if d is PydanticUndefined else d


def _coerce_existing_to_str(existing: Any) -> str | None:
    """The IpXxxNode stores values as strings. Accept either an instance
    or a string from the caller."""
    if existing is None:
        return None
    if isinstance(existing, str):
        return existing
    return str(existing)


class IpAddressBuilder:
    """Matches ``ipaddress.IPv4Address`` and ``ipaddress.IPv6Address``."""

    def matches(self, type_: type) -> bool:
        unwrapped = strip_annotated(type_)
        return unwrapped is IPv4Address or unwrapped is IPv6Address

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> IpAddressNode:
        unwrapped = strip_annotated(type_)
        version: Literal[4, 6] = 4 if unwrapped is IPv4Address else 6
        default = _coerce_existing_to_str(_default(field_info))
        return IpAddressNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            version=version,
            value=_coerce_existing_to_str(existing) if existing is not None else default,
            default=default,
        )


class IpNetworkBuilder:
    """Matches ``ipaddress.IPv4Network`` and ``ipaddress.IPv6Network``."""

    def matches(self, type_: type) -> bool:
        unwrapped = strip_annotated(type_)
        return unwrapped is IPv4Network or unwrapped is IPv6Network

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> IpNetworkNode:
        unwrapped = strip_annotated(type_)
        version: Literal[4, 6] = 4 if unwrapped is IPv4Network else 6
        default = _coerce_existing_to_str(_default(field_info))
        return IpNetworkNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            version=version,
            value=_coerce_existing_to_str(existing) if existing is not None else default,
            default=default,
        )
