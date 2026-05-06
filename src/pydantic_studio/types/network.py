"""Builders for IP / URL / Email annotations."""

from __future__ import annotations

from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
)
from typing import TYPE_CHECKING, Any, Literal, get_origin

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import EmailNode, IpAddressNode, IpNetworkNode, UrlNode
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


def _is_pydantic_url_type(type_: Any) -> bool:
    """Detect Pydantic's URL types.

    Pydantic v2 URL classes (``AnyUrl``, ``HttpUrl``, ``FileUrl``, etc.) are
    plain Python classes whose ``__module__`` is ``pydantic.networks`` and
    whose name ends with ``"Url"``.  We check the unwrapped type (after
    stripping any ``Annotated`` wrapper) and its ``get_origin`` fallback to
    handle both direct references and any future ``Annotated`` variants.
    """
    unwrapped = strip_annotated(type_)
    # If strip_annotated left an Annotated alias (nested), resolve one more level.
    candidate = get_origin(unwrapped) or unwrapped
    if not isinstance(candidate, type):
        return False
    module = getattr(candidate, "__module__", "")
    if not (module == "pydantic" or module.startswith("pydantic.")):
        return False
    name = getattr(candidate, "__name__", "")
    return name == "Url" or name.endswith("Url")


class UrlBuilder:
    """Matches Pydantic's URL family (``AnyUrl``, ``HttpUrl``, etc.)."""

    def matches(self, type_: type) -> bool:
        return _is_pydantic_url_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> UrlNode:
        unwrapped = strip_annotated(type_)
        url_cls = get_origin(unwrapped) or unwrapped
        target_type_name = f"{url_cls.__module__}.{url_cls.__name__}"
        default = _default(field_info)
        default_str = str(default) if default is not None else None
        existing_str = str(existing) if existing is not None else None
        return UrlNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing_str if existing_str is not None else default_str,
            default=default_str,
            target_type_name=target_type_name,
        )


def _is_email_str(type_: Any) -> bool:
    """Detect ``pydantic.EmailStr`` regardless of how it was annotated.

    EmailStr in Pydantic v2 is a plain class in ``pydantic.networks``; we
    check the raw type directly (not via strip_annotated) so the name/module
    check always hits the EmailStr class object itself.
    """
    name = getattr(type_, "__name__", "")
    module = getattr(type_, "__module__", "")
    return name == "EmailStr" and module.startswith("pydantic")


class EmailBuilder:
    """Matches ``pydantic.EmailStr``."""

    def matches(self, type_: type) -> bool:
        return _is_email_str(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        default = _default(field_info)
        return EmailNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )
