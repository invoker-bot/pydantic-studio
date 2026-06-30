"""Form tree node hierarchy.

The tree is a Pydantic v2 hierarchy with a ``kind`` discriminator.
Concrete node types are added in subsequent tasks; this file defines
the abstract base ``FormNode``.
"""

from __future__ import annotations

import contextlib
import json
import math
import sys
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path as FsPath
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from pydantic_studio.tree.validation import ValidationResult

AnyValueMode = Literal["null", "str", "int", "float", "bool", "list", "dict"]
_MISSING_KEY = object()


def _resolve_type_name(name: str) -> Any:
    """Look up a fully-qualified type name (``module.Qualname``).

    Handles ``builtins.str`` etc. specially so unit tests don't need to
    import builtins. ``typing.Literal[...]`` is rebuilt from its JSON-encoded
    arguments (the inverse of ``_fq``'s Literal encoding) so containers of
    ``Literal`` restore the parametrized form instead of the choice-less bare
    ``typing.Literal``. Raises ValueError on miss with a diagnostic message.
    """
    if name.startswith("typing.Literal[") and name.endswith("]"):
        try:
            choices = json.loads(name[len("typing.Literal") :])
        except ValueError as exc:
            msg = f"cannot reconstruct Literal choices from {name!r}"
            raise ValueError(msg) from exc
        return Literal[tuple(choices)]  # type: ignore[misc]
    parts = name.rsplit(".", 1)
    if len(parts) != 2:
        msg = f"malformed type name {name!r} (expected 'module.Qualname')"
        raise ValueError(msg)
    module_name, qualname = parts
    if module_name == "builtins":
        builtin = (
            __builtins__.get(qualname)
            if isinstance(__builtins__, dict)
            else getattr(__builtins__, qualname, None)
        )
        if builtin is None:
            msg = f"unknown builtin {qualname!r}"
            raise ValueError(msg)
        return builtin
    module = sys.modules.get(module_name)
    if module is None:
        msg = (
            f"module {module_name!r} not in sys.modules — "
            f"import it before resolving {name!r}"
        )
        raise ValueError(msg)
    obj: Any = module
    for part in qualname.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            msg = f"{module_name!r} has no {part!r} (resolving {name!r})"
            raise ValueError(msg)
    return obj


def _json_safe_any_value(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(value, allow_nan=False),
            object_pairs_hook=_reject_duplicate_json_key_pairs,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        if _is_duplicate_json_key_error(exc):
            raise
        if isinstance(value, Mapping):
            return _json_safe_any_mapping(value)
        if isinstance(value, (list, tuple, set)):
            return [_json_safe_any_value(item) for item in value]
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).hex()
        if hasattr(value, "get_secret_value"):
            return "**********"
        return str(value)


def _reject_duplicate_json_key_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, item in pairs:
        if key in out:
            msg = f"duplicate JSON key {key!r} after Any value normalization"
            raise ValueError(msg)
        out[key] = item
    return out


def _is_duplicate_json_key_error(exc: BaseException) -> bool:
    return isinstance(exc, ValueError) and str(exc).startswith("duplicate JSON key ")


def _json_safe_any_mapping(value: Mapping[Any, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, item in value.items():
        safe_key = _json_safe_any_key(key)
        if safe_key in out:
            msg = f"duplicate JSON key {safe_key!r} after Any value normalization"
            raise ValueError(msg)
        out[safe_key] = _json_safe_any_value(item)
    return out


def _json_safe_any_key(key: Any) -> str:
    safe_key = _json_safe_any_value(key)
    try:
        pairs = json.loads(
            json.dumps({safe_key: None}, allow_nan=False),
            object_pairs_hook=lambda pairs: pairs,
        )
    except (TypeError, ValueError, OverflowError):
        return str(safe_key)
    return pairs[0][0]


class FormNode(BaseModel):
    """Abstract base. Concrete subclasses set their own ``kind`` literal.

    All FormNodes carry minimal metadata: ``name`` (the field name in the
    parent's schema), ``description`` (markdown, may be None), ``required``
    (mirrors the schema's required-ness), and ``error`` (last validation
    message; None when valid).
    """

    model_config = ConfigDict(extra="forbid")

    kind: str  # set by subclass
    name: str
    description: str | None = None
    required: bool = True
    error: str | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        """Return tuple of error messages for ``value`` against this node's
        type. Empty tuple = valid. Default: accept any value.

        Subclasses override to enforce per-type rules.
        """
        return ()

    # Convenience hook used in subsequent tasks; subclasses may override.
    def to_python(self) -> Any:
        """Return this node's value in a form suitable for `model_validate`."""
        msg = f"{type(self).__name__}.to_python is not implemented"
        raise NotImplementedError(msg)


class StringNode(FormNode):
    """Holds a string value, with optional length / regex / multiline / secret hints."""

    kind: Literal["string"] = "string"
    value: str | None = None
    default: str | None = None

    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    multiline: bool = False
    secret: bool = False

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, str):
            return (f"expected str, got {type(value).__name__}",)
        errors: list[str] = []
        if self.min_length is not None and len(value) < self.min_length:
            errors.append(f"length must be >= {self.min_length}")
        if self.max_length is not None and len(value) > self.max_length:
            errors.append(f"length must be <= {self.max_length}")
        if self.pattern is not None:
            try:
                TypeAdapter(Annotated[str, Field(pattern=self.pattern)]).validate_python(value)
            except ValidationError:
                errors.append(f"must match pattern {self.pattern}")
        return tuple(errors)

    def to_python(self) -> str | None:
        return self.value


class IntNode(FormNode):
    """Holds an integer value, with optional comparison and multiple-of constraints."""

    kind: Literal["int"] = "int"
    value: int | None = None
    default: int | None = None

    ge: int | None = None
    le: int | None = None
    gt: int | None = None
    lt: int | None = None
    multiple_of: int | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Reject bool explicitly even though it is an int subclass.
        if isinstance(value, bool) or not isinstance(value, int):
            return (f"expected int, got {type(value).__name__}",)
        errors: list[str] = []
        if self.ge is not None and value < self.ge:
            errors.append(f"must be >= {self.ge}")
        if self.le is not None and value > self.le:
            errors.append(f"must be <= {self.le}")
        if self.gt is not None and value <= self.gt:
            errors.append(f"must be > {self.gt}")
        if self.lt is not None and value >= self.lt:
            errors.append(f"must be < {self.lt}")
        if self.multiple_of is not None and value % self.multiple_of != 0:
            errors.append(f"must be a multiple of {self.multiple_of}")
        return tuple(errors)

    def to_python(self) -> int | None:
        return self.value


class FloatNode(FormNode):
    """Holds a float value, with optional comparison and infinity/NaN constraints."""

    kind: Literal["float"] = "float"
    value: float | None = None
    default: float | None = None

    ge: float | None = None
    le: float | None = None
    gt: float | None = None
    lt: float | None = None
    multiple_of: float | None = None
    allow_inf_nan: bool = True

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Accept int (Pydantic coerces). Reject bool.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return (f"expected float, got {type(value).__name__}",)
        errors: list[str] = []
        value_is_nan = math.isnan(value)
        if self.ge is not None and (value_is_nan or value < self.ge):
            errors.append(f"must be >= {self.ge}")
        if self.le is not None and (value_is_nan or value > self.le):
            errors.append(f"must be <= {self.le}")
        if self.gt is not None and (value_is_nan or value <= self.gt):
            errors.append(f"must be > {self.gt}")
        if self.lt is not None and (value_is_nan or value >= self.lt):
            errors.append(f"must be < {self.lt}")
        if self.multiple_of is not None:
            try:
                TypeAdapter(Annotated[float, Field(multiple_of=self.multiple_of)]).validate_python(
                    value
                )
            except ValidationError:
                errors.append(f"must be a multiple of {self.multiple_of}")
        return tuple(errors)

    def to_python(self) -> float | None:
        return self.value


class BoolNode(FormNode):
    """Holds a boolean value."""

    kind: Literal["bool"] = "bool"
    value: bool | None = None
    default: bool | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, bool):
            return (f"expected bool, got {type(value).__name__}",)
        return ()

    def to_python(self) -> bool | None:
        return self.value


class DecimalNode(FormNode):
    """Holds a Decimal value, with optional digit and comparison constraints."""

    kind: Literal["decimal"] = "decimal"
    value: Decimal | None = None
    default: Decimal | None = None

    max_digits: int | None = None
    decimal_places: int | None = None
    ge: Decimal | None = None
    le: Decimal | None = None
    gt: Decimal | None = None
    lt: Decimal | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Reject bool first — Pydantic's Decimal validation rejects it.
        if isinstance(value, bool):
            return (f"expected Decimal, got {type(value).__name__}",)
        if isinstance(value, Decimal):
            decimal_value = value
        # Pydantic coerces int / float / str via Decimal(str(...)). Mirror
        # that behavior so validate_value does not flag values the schema
        # would happily accept.
        elif isinstance(value, (int, float, str)):
            try:
                decimal_value = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
            except (InvalidOperation, ValueError):
                return (f"cannot convert {value!r} to Decimal",)
        else:
            return (f"expected Decimal, got {type(value).__name__}",)
        errors: list[str] = []
        if self.ge is not None and decimal_value < self.ge:
            errors.append(f"must be >= {self.ge}")
        if self.le is not None and decimal_value > self.le:
            errors.append(f"must be <= {self.le}")
        if self.gt is not None and decimal_value <= self.gt:
            errors.append(f"must be > {self.gt}")
        if self.lt is not None and decimal_value >= self.lt:
            errors.append(f"must be < {self.lt}")
        if self.max_digits is not None:
            try:
                TypeAdapter(Annotated[Decimal, Field(max_digits=self.max_digits)]).validate_python(
                    decimal_value
                )
            except ValidationError:
                errors.append(f"must have no more than {self.max_digits} digits")
        if self.decimal_places is not None:
            try:
                TypeAdapter(
                    Annotated[Decimal, Field(decimal_places=self.decimal_places)]
                ).validate_python(decimal_value)
            except ValidationError:
                errors.append(f"must have no more than {self.decimal_places} decimal places")
        return tuple(errors)

    def to_python(self) -> Decimal | None:
        return self.value


class DatetimeNode(FormNode):
    """Holds a timezone-aware-or-naive ``datetime.datetime`` value.

    Pydantic emits ISO 8601 strings on ``model_dump_json`` and parses them
    back on ``model_validate_json``, so no custom serializer is needed.
    """

    kind: Literal["datetime"] = "datetime"
    value: datetime | None = None
    default: datetime | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Reject date/time subclasses explicitly — datetime IS-A date in Python,
        # but a date field cannot take a datetime and vice versa. We need an
        # exact-type check.
        if type(value) is not datetime:
            return (f"expected datetime, got {type(value).__name__}",)
        return ()

    def to_python(self) -> datetime | None:
        return self.value


class DateNode(FormNode):
    """Holds a ``datetime.date`` value (no time component)."""

    kind: Literal["date"] = "date"
    value: date | None = None
    default: date | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if type(value) is not date:  # exact-type: rejects datetime subclass
            return (f"expected date, got {type(value).__name__}",)
        return ()

    def to_python(self) -> date | None:
        return self.value


class TimeNode(FormNode):
    """Holds a ``datetime.time`` value (no date component)."""

    kind: Literal["time"] = "time"
    value: time | None = None
    default: time | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if type(value) is not time:
            return (f"expected time, got {type(value).__name__}",)
        return ()

    def to_python(self) -> time | None:
        return self.value


class TimedeltaNode(FormNode):
    """Holds a ``datetime.timedelta`` value (a duration).

    Pydantic emits ISO 8601 duration strings (``PT1H30M``) on JSON dump
    and parses them back on load — round-trip works without a custom
    serializer.
    """

    kind: Literal["timedelta"] = "timedelta"
    value: timedelta | None = None
    default: timedelta | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, timedelta):
            return (f"expected timedelta, got {type(value).__name__}",)
        return ()

    def to_python(self) -> timedelta | None:
        return self.value


class IpAddressNode(FormNode):
    """Holds an IPv4 or IPv6 address as a string.

    The ``version`` field discriminates 4 vs 6 — set by the builder from
    the field annotation (IPv4Address vs IPv6Address). Stored as a string
    rather than the ``IPv4Address``/``IPv6Address`` instance because:

    1. Pydantic's union handling for the two address classes is brittle.
    2. Strings are JSON-friendly without custom serializers.
    3. ``to_python`` coerces back via ``ipaddress.ip_address`` for the
       schema's validate step.
    """

    kind: Literal["ip_address"] = "ip_address"
    value: str | None = None
    default: str | None = None
    version: Literal[4, 6]

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from ipaddress import (
            AddressValueError,
            IPv4Address,
            IPv6Address,
        )

        if value is None:
            return () if not self.required else ("value is required",)
        # Accept already-parsed instances of the right version.
        if self.version == 4 and isinstance(value, IPv4Address):
            return ()
        if self.version == 6 and isinstance(value, IPv6Address):
            return ()
        if isinstance(value, str):
            cls = IPv4Address if self.version == 4 else IPv6Address
            other_cls = IPv6Address if self.version == 4 else IPv4Address
            other_version = 6 if self.version == 4 else 4
            try:
                cls(value)
            except (AddressValueError, ValueError):
                # Check if it parses as the other version — if so, give a
                # clearer "wrong version" message.
                try:
                    other_cls(value)
                    return (
                        f"expected IPv{self.version} address, "
                        f"got IPv{other_version}: {value!r}",
                    )
                except (AddressValueError, ValueError):
                    pass
                return (f"invalid IPv{self.version} address: {value!r}",)
            return ()
        return (f"expected IPv{self.version} address, got {type(value).__name__}",)

    def to_python(self) -> Any:
        from ipaddress import IPv4Address, IPv6Address

        if self.value is None:
            return None
        cls = IPv4Address if self.version == 4 else IPv6Address
        return cls(self.value)


class IpNetworkNode(FormNode):
    """Holds an IPv4 or IPv6 network in CIDR form, as a string."""

    kind: Literal["ip_network"] = "ip_network"
    value: str | None = None
    default: str | None = None
    version: Literal[4, 6]

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from ipaddress import IPv4Network, IPv6Network

        if value is None:
            return () if not self.required else ("value is required",)
        if self.version == 4 and isinstance(value, IPv4Network):
            return ()
        if self.version == 6 and isinstance(value, IPv6Network):
            return ()
        if isinstance(value, str):
            cls = IPv4Network if self.version == 4 else IPv6Network
            try:
                cls(value, strict=False)
            except ValueError:
                return (f"invalid IPv{self.version} network: {value!r}",)
            return ()
        return (f"expected IPv{self.version} network, got {type(value).__name__}",)

    def to_python(self) -> Any:
        from ipaddress import IPv4Network, IPv6Network

        if self.value is None:
            return None
        cls = IPv4Network if self.version == 4 else IPv6Network
        return cls(self.value, strict=False)


class UrlNode(FormNode):
    """Holds a URL as a string, with the original Pydantic URL type
    recorded in ``target_type_name`` for round-trip coercion.

    Covers ``AnyUrl``, ``AnyHttpUrl``, ``HttpUrl``, ``FileUrl``,
    ``WebsocketUrl``, and any other ``Annotated[Url, UrlConstraints(...)]``
    variant exposed by Pydantic. ``validate_value`` and ``to_python``
    delegate to a ``TypeAdapter`` built from ``target_type_name`` so
    each URL subtype's specific constraints (scheme set, default port,
    etc.) are enforced.
    """

    kind: Literal["url"] = "url"
    value: str | None = None
    default: str | None = None
    target_type_name: str  # e.g., "pydantic.HttpUrl"

    def _adapter(self) -> Any:
        """Build (and cache) a TypeAdapter for this URL's target type.

        Cached as an instance attribute via ``object.__setattr__`` to bypass
        Pydantic's own attribute machinery — TypeAdapters aren't Pydantic
        fields and shouldn't be model_dumped.
        """
        cached = getattr(self, "__url_adapter__", None)
        if cached is not None:
            return cached
        from pydantic import TypeAdapter

        target = _resolve_type_name(self.target_type_name)
        adapter = TypeAdapter(target)
        object.__setattr__(self, "__url_adapter__", adapter)
        return adapter

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from pydantic import ValidationError

        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, str):
            return (f"expected str URL, got {type(value).__name__}",)
        try:
            self._adapter().validate_python(value)
        except ValidationError as e:
            first = e.errors()[0]
            return (first.get("msg", "invalid URL"),)
        return ()

    def to_python(self) -> Any:
        if self.value is None:
            return None
        return self._adapter().validate_python(self.value)


class EmailNode(FormNode):
    """Holds an email address as a string, validated via Pydantic's
    ``EmailStr`` (which depends on ``email-validator``).
    """

    kind: Literal["email"] = "email"
    value: str | None = None
    default: str | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, str):
            return (f"expected str email, got {type(value).__name__}",)
        # Lazy import: email-validator is an optional dep; if missing, fall
        # back to a permissive '@'-presence check so EmailNode still works
        # in environments that haven't installed the extra.
        try:
            from email_validator import EmailNotValidError, validate_email
        except ImportError:
            if "@" not in value or value.startswith("@") or value.endswith("@"):
                return (f"invalid email: {value!r}",)
            return ()
        try:
            validate_email(value, check_deliverability=False)
        except EmailNotValidError as e:
            return (str(e),)
        return ()

    def to_python(self) -> str | None:
        return self.value


class PathNode(FormNode):
    """Holds a filesystem path as a string.

    Stored as a string (not a ``Path`` instance) so JSON round-trip is
    OS-portable — `Path("/etc/x")` becomes `WindowsPath` on Windows, which
    breaks equality on round-trip across platforms. ``set_value`` accepts
    either a string or a ``Path`` instance and normalizes to ``str``.
    """

    kind: Literal["path"] = "path"
    value: str | None = None
    default: str | None = None

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    @field_validator("value", "default", mode="before")
    @classmethod
    def _normalize_path(cls, v: Any) -> Any:
        from pathlib import PurePath

        if isinstance(v, PurePath):
            return str(v)
        return v

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from pathlib import PurePath

        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, (str, PurePath)):
            return (f"expected str or Path, got {type(value).__name__}",)
        return ()

    def to_python(self) -> Any:
        from pathlib import Path as _Path

        if self.value is None:
            return None
        return _Path(self.value)


class UuidNode(FormNode):
    """Holds a ``uuid.UUID`` value.

    Pydantic round-trips UUIDs as strings via JSON, so the proper field
    type works directly with no custom serializer.
    """

    kind: Literal["uuid"] = "uuid"
    value: UUID | None = None
    default: UUID | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, UUID):
            return (f"expected UUID, got {type(value).__name__}",)
        return ()

    def to_python(self) -> UUID | None:
        return self.value


class SecretNode(FormNode):
    """Holds the plaintext value of a ``pydantic.SecretStr`` or
    ``pydantic.SecretBytes`` field.

    The ``secret_kind`` field discriminates str vs bytes so renderers can
    pick the correct widget. ``to_python`` wraps the stored value in the
    appropriate Pydantic Secret type so model validation passes.

    Security caveat: secret values are stored in plaintext in snapshots
    (in-memory) and in ``draft_save`` JSON (on disk). Don't use drafts on
    shared storage for sensitive deployments. A future release may add
    encrypted drafts or a "skip secrets in drafts" mode.
    """

    kind: Literal["secret"] = "secret"
    value: str | bytes | None = None
    default: str | bytes | None = None
    secret_kind: Literal["str", "bytes"]

    @model_validator(mode="after")
    def _coerce_bytes_fields(self) -> SecretNode:
        """After JSON load, bytes values come back as ``str`` because Pydantic
        serializes ``bytes`` as a plain UTF-8 string in the ``str | bytes | None``
        union. Re-coerce them to ``bytes`` when ``secret_kind == "bytes"``."""
        if self.secret_kind == "bytes":
            if isinstance(self.value, str):
                self.value = self.value.encode()
            if isinstance(self.default, str):
                self.default = self.default.encode()
        return self

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if self.secret_kind == "str" and not isinstance(value, str):
            return (f"expected str (SecretStr value), got {type(value).__name__}",)
        if self.secret_kind == "bytes" and not isinstance(value, (bytes, bytearray)):
            return (f"expected bytes (SecretBytes value), got {type(value).__name__}",)
        return ()

    def to_python(self) -> Any:
        from pydantic import SecretBytes, SecretStr

        if self.value is None:
            return None
        if self.secret_kind == "str":
            assert isinstance(self.value, str), (
                f"SecretNode(secret_kind='str').value must be str, got {type(self.value).__name__}"
            )
            return SecretStr(self.value)
        assert isinstance(self.value, (bytes, bytearray)), (
            f"SecretNode(secret_kind='bytes').value must be bytes, got {type(self.value).__name__}"
        )
        return SecretBytes(self.value)


class PatternNode(FormNode):
    """Holds a regex pattern as its source string + flags.

    ``to_python`` recompiles via ``re.compile(value, flags)``.
    """

    kind: Literal["pattern"] = "pattern"
    value: str | None = None
    default: str | None = None
    flags: int = 0

    def validate_value(self, value: Any) -> tuple[str, ...]:
        import re as _re

        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, str):
            return (f"expected regex source string, got {type(value).__name__}",)
        try:
            _re.compile(value, self.flags)
        except _re.error as e:
            return (f"invalid regex: {e}",)
        return ()

    def to_python(self) -> Any:
        import re as _re

        if self.value is None:
            return None
        return _re.compile(self.value, self.flags)


class BytesNode(FormNode):
    """Holds a ``bytes`` value (JSON-serialized as hex to guarantee lossless
    round-trips — Pydantic's default JSON bytes handling is UTF-8 encoding,
    which is not safe for arbitrary binary data).

    The ``_value_hex`` / ``_default_hex`` *string* fields are the on-disk
    representation; the ``value`` / ``default`` *bytes* properties are the
    in-memory API.  External code should use ``value`` and ``default``; the
    hex fields are an implementation detail.
    """

    kind: Literal["bytes"] = "bytes"
    # Store as hex strings so JSON serialization is always lossless.
    _value_hex: str | None = None
    _default_hex: str | None = None

    # Public fields (bytes); private storage is the hex strings above.
    value: bytes | None = None
    default: bytes | None = None

    @field_serializer("value", when_used="json")
    def _serialize_value(self, v: bytes | None) -> str | None:
        if v is None:
            return None
        return v.hex()

    @field_serializer("default", when_used="json")
    def _serialize_default(self, v: bytes | None) -> str | None:
        if v is None:
            return None
        return v.hex()

    @model_validator(mode="before")
    @classmethod
    def _decode_hex_fields(cls, data: Any) -> Any:
        """On JSON load, ``value``/``default`` arrive as hex strings.
        Convert them back to ``bytes`` before field assignment so Pydantic
        receives the correct type.
        """
        if not isinstance(data, dict):
            return data
        for key in ("value", "default"):
            raw = data.get(key)
            if isinstance(raw, str):
                with contextlib.suppress(ValueError):
                    data = {**data, key: bytes.fromhex(raw)}
        return data

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, (bytes, bytearray)):
            return (f"expected bytes, got {type(value).__name__}",)
        return ()

    def to_python(self) -> bytes | None:
        if self.value is None:
            return None
        return bytes(self.value)


class EnumNode(FormNode):
    """Holds a single value drawn from a closed set of Enum members.

    Snapshot round-trip: ``value``, ``default``, and the member side of
    each ``choices`` tuple are serialized as the member's ``.name`` (a
    string) and rehydrated back into Enum members on validation, using
    ``enum_class_name`` for sys.modules lookup. This matches the pattern
    GroupNode uses for ``schema_class``.

    Invariant: ``choices[i][1]`` is always an Enum member when the node is
    in a fresh-from-builder OR fresh-from-snapshot-load state. After JSON
    serialization but before re-validation it is transiently a string.
    """

    kind: Literal["enum"] = "enum"
    value: Any = None
    default: Any = None
    enum_class_name: str
    choices: list[tuple[str, Any]] = []

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    @field_serializer("value", "default", when_used="json")
    def _serialize_member(self, value: Any) -> Any:
        from enum import Enum

        if isinstance(value, Enum):
            return value.name
        return value

    @field_serializer("choices", when_used="json")
    def _serialize_choices(
        self, choices: list[tuple[str, Any]]
    ) -> list[tuple[str, Any]]:
        from enum import Enum

        return [
            (name, member.name if isinstance(member, Enum) else member)
            for name, member in choices
        ]

    @model_validator(mode="after")
    def _rehydrate_members(self) -> EnumNode:
        """After JSON/YAML load, ``value`` / ``default`` / ``choices[i][1]`` may
        be raw strings or numbers. Look up the Enum class and convert back.

        This runs on every validation including initial construction, but
        Enum members short-circuit.
        """
        from enum import Enum

        enum_cls = self._lookup_enum_class()
        if enum_cls is None:
            # If the class can't be resolved (e.g., the module isn't
            # imported), skip rehydration and let downstream code see
            # raw strings. validate_value will catch this.
            return self

        def to_member(v: Any) -> Any:
            if isinstance(v, Enum):
                return v
            if isinstance(v, str):
                try:
                    return enum_cls[v]
                except KeyError:
                    pass
            try:
                return enum_cls(v)
            except (TypeError, ValueError):
                return v

        self.value = to_member(self.value)
        self.default = to_member(self.default)
        new_choices: list[tuple[str, Any]] = []
        for name, member in self.choices:
            new_choices.append((name, to_member(member)))
        self.choices = new_choices
        return self

    def _lookup_enum_class(self) -> Any:
        """Resolve ``enum_class_name`` (e.g. ``mymodule.Color``) via
        sys.modules. Returns the class, or None if not importable."""
        import sys
        from enum import Enum

        parts = self.enum_class_name.rsplit(".", 1)
        if len(parts) != 2:
            return None
        module_name, class_name = parts
        module = sys.modules.get(module_name)
        if module is None:
            return None
        cls = getattr(module, class_name, None)
        if cls is None or not (isinstance(cls, type) and issubclass(cls, Enum)):
            return None
        return cls

    def to_python(self) -> Any:
        return self.value

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from enum import Enum

        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, Enum):
            short_name = self.enum_class_name.rsplit(".", 1)[-1]
            return (f"{value!r} is not a {short_name} member",)
        # Compare by name to avoid identity drift across imports.
        if value.name not in [name for name, _ in self.choices]:
            short_name = self.enum_class_name.rsplit(".", 1)[-1]
            return (f"{value!r} is not a {short_name} member",)
        return ()


class LiteralNode(FormNode):
    """Holds a value drawn from a closed list defined by ``Literal[...]``.

    Literal values are always JSON-friendly primitives (str / int / bool /
    None / Enum members), so no special serializer is needed — Pydantic's
    default JSON encoding round-trips them correctly.
    """

    kind: Literal["literal"] = "literal"
    value: Any = None
    default: Any = None
    choices: list[Any] = []

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        return self.value

    def validate_value(self, value: Any) -> tuple[str, ...]:
        # If None is a declared choice, treat it like any other member.
        if value is None and None not in self.choices:
            return () if not self.required else ("value is required",)
        if value not in self.choices:
            return (f"{value!r} not in choices {self.choices!r}",)
        return ()


class SequenceNode(FormNode):
    """Container for list / set / tuple values.

    ``origin`` selects the Python container used by ``to_python``.
    ``item_type_name`` is the FQ name of the (homogeneous) item annotation,
    used by ``FormTree.add_item`` to build a fresh child via the registry.
    For fixed-length heterogeneous tuples (``origin="tuple_fixed"``),
    ``slot_type_names`` carries one FQ name per slot.
    """

    kind: Literal["sequence"] = "sequence"
    origin: Literal["list", "set", "tuple", "tuple_fixed"]
    items: "list[AnyNode]" = []
    item_type_name: str | None = None
    slot_type_names: list[str] | None = None
    min_length: int | None = None
    max_length: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        values = [it.to_python() for it in self.items]
        if self.origin == "list":
            return values
        if self.origin == "set":
            return set(values)
        # For fixed-length heterogeneous tuples: if every slot is None
        # (i.e. no existing data was provided), return None so GroupNode
        # can omit the key and let Pydantic apply the field's default.
        if self.origin == "tuple_fixed" and all(v is None for v in values):
            return None
        return tuple(values)  # both "tuple" and "tuple_fixed"

    def validate_value(self, value: Any) -> tuple[str, ...]:
        # Whole-sequence replacement isn't a typical mutation; renderers
        # use add_item / remove_item / move_item instead. Accept anything
        # iterable for now and let the schema do the work at submit time.
        return ()


class MappingNode(FormNode):
    """Container for ``dict[K, V]`` values.

    ``entries`` preserves insertion order; each entry is a (key_node,
    value_node) pair built from the corresponding annotations.
    """

    kind: Literal["mapping"] = "mapping"
    entries: "list[tuple[AnyNode, AnyNode]]" = []
    key_type_name: str
    value_type_name: str
    min_length: int | None = None
    max_length: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> dict[Any, Any]:
        return {k.to_python(): v.to_python() for k, v in self.entries}

    def validate_value(self, value: Any) -> tuple[str, ...]:
        return ()  # whole-mapping replacement deferred to v0.2


class UnionNode(FormNode):
    """Holds a value that could be one of several types.

    The user picks a variant; the node's ``selected`` carries the chosen
    variant's child node. ``variant_type_names`` records all candidate
    types for ``select_variant`` to rebuild on switch.
    """

    kind: Literal["union"] = "union"
    variant_type_names: list[str]
    selected_index: int | None = None
    selected: "AnyNode | None" = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        if self.selected is None:
            return None
        return self.selected.to_python()

    def validate_value(self, value: Any) -> tuple[str, ...]:
        # Per-leaf validation happens on the inner node; the union itself
        # accepts any value the user is staging.
        return ()


class GroupNode(FormNode):
    """Represents a nested Pydantic BaseModel with a list of child nodes."""

    kind: Literal["group"] = "group"
    schema_class: type[BaseModel]
    fields: "list[AnyNode]"  # forward ref; rebuilt at module bottom
    # An ``Optional[Model]`` field defaulting to None starts *omitted*:
    # children carry their schema defaults for display, but ``to_python``
    # resolves the whole group to None until the user activates it by
    # editing any descendant (``FormTree.set_value`` clears the flag on
    # every group it walks through). Without this, an untouched optional
    # nested model materializes as a fully-defaulted instance on submit
    # instead of round-tripping None.
    omitted: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    @field_serializer("schema_class", when_used="json")
    def serialize_schema_class(self, value: type[BaseModel]) -> str:
        """Serialize schema_class to a fully qualified name for JSON."""
        return f"{value.__module__}.{value.__name__}"

    @field_validator("schema_class", mode="before")
    @classmethod
    def _deserialize_schema_class(cls, v: Any) -> Any:
        """If ``v`` is a serialized string (`module.ClassName`), look up the
        class from ``sys.modules``. Raise ValueError with diagnostic info on
        failure so debugging draft-load problems is easier."""
        if not isinstance(v, str):
            return v  # already a class object — no change needed
        parts = v.rsplit(".", 1)
        if len(parts) != 2:
            msg = (
                f"Cannot deserialize schema_class from {v!r}: expected the "
                f"'module.ClassName' format produced by the field_serializer."
            )
            raise ValueError(msg)
        module_name, class_name = parts
        module = sys.modules.get(module_name)
        if module is None:
            msg = (
                f"Cannot deserialize schema_class {v!r}: module {module_name!r} "
                f"is not in sys.modules. Ensure the module is imported before "
                f"loading the snapshot/draft."
            )
            raise ValueError(msg)
        if not hasattr(module, class_name):
            msg = (
                f"Cannot deserialize schema_class {v!r}: module {module_name!r} "
                f"has no attribute {class_name!r}. The class may have been "
                f"renamed or moved since the snapshot/draft was created."
            )
            raise ValueError(msg)
        return getattr(module, class_name)

    def find(self, name: str) -> AnyNode | None:
        """Find a child node by name, or None if not found."""
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def to_python(self) -> dict[str, Any] | None:
        """Collect child values into a dict keyed by child names.

        Filters by *omitting the key from the returned dict* whenever a
        child's ``to_python()`` returns ``None`` — which causes Pydantic to
        apply the field's schema default.

        An all-None nested *required* ``GroupNode`` returns ``{}``: the
        empty dict stays in the parent so Pydantic reports the nested
        model's missing required leaves with precise dotted locations.
        An all-None *optional* group returns ``None`` instead — the
        parent omits the key and the field's default (``None``) applies.
        Keeping ``{}`` there used to manufacture validation errors for
        ``Optional[Model]`` fields the user never touched, making fresh
        trees of such schemas unsaveable.

        Known v0.1 limitation: users cannot save an Optional[T] field as
        explicit None once the subtree has values — that requires v0.2's
        explicit-null toggle.

        An *omitted* optional group short-circuits to ``None`` regardless
        of its children: their pre-filled schema defaults are presentation
        only until the user activates the group (see ``GroupNode.omitted``).
        """
        if self.omitted and not self.required:
            return None
        out: dict[str, Any] = {}
        for f in self.fields:
            v = f.to_python()
            if v is None:
                continue
            out[f.name] = v
        if not out and not self.required:
            return None
        return out


class AnyValueNode(FormNode):
    """Holds a value of unconstrained type (``typing.Any``).

    Pydantic accepts ``Any`` as an "anything goes" escape hatch — this
    node carries the value as-is plus a ``mode`` discriminator that
    indicates the value's runtime shape (``str`` / ``int`` / ``float`` /
    ``bool`` / ``list`` / ``dict`` / ``null``). Renderers use ``mode``
    to pick a widget; tree-side validation stays permissive so the
    underlying ``Any`` semantics are not narrowed by the form.

    Round-trip is direct: ``to_python`` returns ``value`` unchanged
    and ``model_validate`` accepts it back because ``Any`` does no
    validation. JSON snapshots round-trip primitives losslessly; non-
    JSON-native types (tuple, set, custom objects) collapse to their
    JSON form on reload, which matches what ``Any`` can guarantee.

    ``validate_assignment=True`` plus the ``_sync_mode`` model
    validator keeps ``mode`` consistent with ``value`` after every
    ``tree.set_value`` mutation — so renderers always pick the right
    widget without the caller having to set ``mode`` manually.
    """

    kind: Literal["any"] = "any"
    mode: AnyValueMode = "null"
    value: Any = None

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    @model_validator(mode="after")
    def _sync_mode(self) -> AnyValueNode:
        inferred = AnyValueNode.infer_mode(self.value)
        if self.mode != inferred:
            object.__setattr__(self, "mode", inferred)
        return self

    @field_serializer("value", when_used="json")
    def _serialize_json_value(self, value: Any) -> Any:
        return _json_safe_any_value(value)

    def validate_value(self, value: Any) -> tuple[str, ...]:
        # ``typing.Any`` accepts every value, including None — tree-level
        # validation imposes nothing. ``required`` carries through from
        # the field annotation but does not gate values here.
        return ()

    def to_python(self) -> Any:
        return self.value

    @staticmethod
    def infer_mode(value: Any) -> AnyValueMode:
        """Map ``value``'s runtime type to one of the seven modes.

        ``bool`` is checked before ``int`` because ``bool`` is an int
        subclass in Python and the order would otherwise mis-classify
        every boolean as int.
        """
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "str"
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "dict"
        # tuple / set / custom objects collapse to ``str`` mode so the
        # form has *some* representation — round-trip uses ``value``
        # directly so the original object survives in memory.
        return "str"


# Discriminated union — every concrete node type uses ``kind`` as discriminator.
AnyNode = Annotated[
    StringNode
    | IntNode
    | FloatNode
    | BoolNode
    | DecimalNode
    | DatetimeNode
    | DateNode
    | TimeNode
    | TimedeltaNode
    | IpAddressNode
    | IpNetworkNode
    | UrlNode
    | EmailNode
    | PathNode
    | UuidNode
    | SecretNode
    | PatternNode
    | BytesNode
    | EnumNode
    | LiteralNode
    | SequenceNode
    | MappingNode
    | UnionNode
    | GroupNode
    | AnyValueNode,
    Discriminator("kind"),
]


# Resolve the forward references inside GroupNode.fields, SequenceNode.items,
# MappingNode.entries, and UnionNode.selected.
GroupNode.model_rebuild()
SequenceNode.model_rebuild()
MappingNode.model_rebuild()
UnionNode.model_rebuild()


def _collect_missing_required(node: Any, base: str, out: list[str]) -> None:
    """Preorder walk collecting required-and-unset leaf paths."""

    def join(segment: Any) -> str:
        return f"{base}.{segment}" if base else str(segment)

    kind = getattr(node, "kind", None)
    if kind == "group":
        # An untouched optional group resolves to None (field default) —
        # its required children only become real validation gaps once
        # the subtree holds any value. Mirrors GroupNode.to_python.
        if not node.required and node.to_python() is None:
            return
        for child in node.fields:
            _collect_missing_required(child, join(child.name), out)
        return
    if kind == "sequence":
        for idx, item in enumerate(node.items):
            _collect_missing_required(item, join(idx), out)
        return
    if kind == "mapping":
        for idx, (_key, value) in enumerate(node.entries):
            _collect_missing_required(value, join(idx), out)
        return
    if kind == "union":
        if node.selected is not None:
            _collect_missing_required(node.selected, base, out)
        elif node.required:
            out.append(base)
        return
    if (
        getattr(node, "required", False)
        and hasattr(node, "value")
        and node.value is None
    ):
        out.append(base)


def _field_output_key(field_name: str, field_info: Any, *, by_alias: bool) -> str:
    if not by_alias:
        return field_name
    serialization_alias = getattr(field_info, "serialization_alias", None)
    if isinstance(serialization_alias, str) and serialization_alias:
        return serialization_alias
    alias = getattr(field_info, "alias", None)
    if isinstance(alias, str) and alias:
        return alias
    return field_name


def _key_present(data: dict[Any, Any], key: Any) -> Any:
    with contextlib.suppress(TypeError):
        if key in data:
            return key
    return _MISSING_KEY


def _reject_duplicate_mapping_json_keys(node: MappingNode) -> None:
    seen: set[str] = set()
    for key_node, _value_node in node.entries:
        json_key = _json_safe_any_key(key_node.to_python())
        if json_key in seen:
            msg = f"duplicate JSON key {json_key!r} after mapping key normalization"
            raise ValueError(msg)
        seen.add(json_key)


def _validation_error_messages(exc: Exception) -> list[str]:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        raw_errors = cast("list[dict[str, Any]]", errors())
        messages = [
            str(err.get("msg", err))
            for err in raw_errors
            if isinstance(err, dict)
        ]
        if messages:
            return messages
    return [str(exc)]


def _validate_seed_against_node(node: Any, seed: Any) -> list[str]:
    if seed is None:
        return []
    if isinstance(node, GroupNode):
        from pydantic_studio.types.aliases import input_value_for_field

        if isinstance(seed, BaseModel):
            data = seed.model_dump(mode="python")
        elif isinstance(seed, dict):
            data = seed
        else:
            return [
                "expected dict/BaseModel for group seed, got "
                f"{type(seed).__name__}"
            ]
        errors: list[str] = []
        for child in node.fields:
            field_info = node.schema_class.model_fields.get(child.name)
            if field_info is None:
                continue
            value = input_value_for_field(data, child.name, field_info)
            if value is None:
                continue
            for message in _validate_seed_against_node(child, value):
                errors.append(f"{child.name}: {message}")
        return errors
    if isinstance(node, SequenceNode):
        if not isinstance(seed, (list, tuple, set, frozenset)):
            return [
                "expected list/tuple/set for sequence value, got "
                f"{type(seed).__name__}"
            ]
        errors: list[str] = []
        length = len(seed)
        if node.min_length is not None and length < node.min_length:
            errors.append(f"length must be >= {node.min_length}")
        if node.max_length is not None and length > node.max_length:
            errors.append(f"length must be <= {node.max_length}")
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree.builder import default_registry

        values = list(seed)
        item_type_names = (
            node.slot_type_names
            if node.origin == "tuple_fixed"
            else [node.item_type_name] * len(values)
        )
        registry = default_registry()
        for index, value in enumerate(values):
            if item_type_names is None or index >= len(item_type_names):
                continue
            item_type_name = item_type_names[index]
            if item_type_name is None:
                continue
            item_type = _resolve_type_name(item_type_name)
            try:
                child = registry.find(item_type).build(
                    item_type,
                    FieldInfo(annotation=item_type),
                    value,
                )
            except ValidationError as exc:
                for message in _validation_error_messages(exc):
                    errors.append(f"[{index}]: {message}")
                continue
            for message in _validate_seed_against_node(child, value):
                errors.append(f"[{index}]: {message}")
        return errors
    if isinstance(node, MappingNode):
        if not isinstance(seed, dict):
            return [f"expected dict for mapping value, got {type(seed).__name__}"]
        errors: list[str] = []
        length = len(seed)
        if node.min_length is not None and length < node.min_length:
            errors.append(f"length must be >= {node.min_length}")
        if node.max_length is not None and length > node.max_length:
            errors.append(f"length must be <= {node.max_length}")
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree.builder import default_registry

        registry = default_registry()
        key_type = _resolve_type_name(node.key_type_name)
        value_type = _resolve_type_name(node.value_type_name)
        key_builder = registry.find(key_type)
        value_builder = registry.find(value_type)
        key_field = FieldInfo(annotation=key_type)
        value_field = FieldInfo(annotation=value_type)
        for raw_key, raw_value in seed.items():
            try:
                key_node = key_builder.build(key_type, key_field, raw_key)
            except ValidationError as exc:
                for message in _validation_error_messages(exc):
                    errors.append(f"key {raw_key!r}: {message}")
                continue
            for message in _validate_seed_against_node(key_node, raw_key):
                errors.append(f"key {raw_key!r}: {message}")
            try:
                value_node = value_builder.build(value_type, value_field, raw_value)
            except ValidationError as exc:
                for message in _validation_error_messages(exc):
                    errors.append(f"[{raw_key!r}]: {message}")
                continue
            for message in _validate_seed_against_node(value_node, raw_value):
                errors.append(f"[{raw_key!r}]: {message}")
        return errors
    if isinstance(node, UnionNode) and node.selected is not None:
        return _validate_seed_against_node(node.selected, seed)
    validate_value = getattr(node, "validate_value", None)
    if callable(validate_value):
        return list(cast("tuple[str, ...]", validate_value(seed)))
    return []


def _build_seeded_node(
    builder: Any,
    type_: Any,
    field_info: Any,
    seed: Any,
) -> tuple[Any | None, list[str]]:
    from pydantic import ValidationError

    try:
        node = builder.build(type_, field_info, None)
    except ValidationError as exc:
        return None, _validation_error_messages(exc)
    errors = _validate_seed_against_node(node, seed)
    if errors:
        return None, errors
    try:
        return builder.build(type_, field_info, seed), []
    except ValidationError as exc:
        return None, _validation_error_messages(exc)


def _overlay_any_output_values(data: Any, node: Any, *, by_alias: bool) -> Any:
    if isinstance(node, AnyValueNode):
        return _json_safe_any_value(node.value)
    if isinstance(node, GroupNode) and isinstance(data, dict):
        out = dict(data)
        for child in node.fields:
            field_info = node.schema_class.model_fields.get(child.name)
            if field_info is None:
                continue
            key = _field_output_key(child.name, field_info, by_alias=by_alias)
            if key in out:
                out[key] = _overlay_any_output_values(out[key], child, by_alias=by_alias)
        return out
    if isinstance(node, SequenceNode) and isinstance(data, list):
        return [
            _overlay_any_output_values(item_data, item_node, by_alias=by_alias)
            for item_data, item_node in zip(data, node.items, strict=False)
        ]
    if isinstance(node, MappingNode) and isinstance(data, dict):
        _reject_duplicate_mapping_json_keys(node)
        out = dict(data)
        for key_node, value_node in node.entries:
            raw_key = key_node.to_python()
            safe_key = _json_safe_any_value(raw_key)
            for output_key in (
                _key_present(out, raw_key),
                _key_present(out, safe_key),
                _key_present(out, str(safe_key)),
            ):
                if output_key is not _MISSING_KEY:
                    break
            if output_key is not _MISSING_KEY:
                out[output_key] = _overlay_any_output_values(
                    out[output_key], value_node, by_alias=by_alias
                )
        return out
    if isinstance(node, UnionNode) and node.selected is not None:
        return _overlay_any_output_values(data, node.selected, by_alias=by_alias)
    return data


class VariantOption(BaseModel):
    """Serializable metadata for one selectable root model variant."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    description: str | None = None
    model_type_name: str


class VariantState(BaseModel):
    """Root-level variant selector state for a FormTree."""

    model_config = ConfigDict(extra="forbid")

    options: list[VariantOption]
    selected_id: str
    discriminator: str | None = None
    persistence: Literal["metadata", "inline_discriminator"] = "metadata"


class FormTree(BaseModel):
    """Root container: schema reference, root group, and history (added later)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    schema_class: type[BaseModel] | None = None  # may be re-attached via context on load
    schema_name: str
    root: GroupNode
    created_at: datetime
    snapshots: list[bytes] = []
    cursor: int = 0
    snapshot_limit: int = 50
    draft_path: FsPath | None = None
    variant: VariantState | None = None

    # Stashed source CommentedMap for round-trip save (preserves comments).
    # Excluded from JSON snapshots — re-populated only via load_yaml.
    yaml_source: Any = Field(default=None, exclude=True, repr=False)

    def to_python(self) -> dict[str, Any]:
        # The root group is always required, so to_python never returns
        # None here; the `or {}` keeps the signature honest regardless.
        return self.root.to_python() or {}

    def to_instance(self) -> BaseModel:
        """Materialize the tree into the user's schema_class.

        Raises:
            ValidationFailedError: if the schema rejects the produced dict.
        """
        from pydantic import ValidationError

        from pydantic_studio.exceptions import ValidationFailedError

        if self.schema_class is None:
            msg = "FormTree.schema_class is not set"
            raise RuntimeError(msg)
        # GroupNode.to_python now filters None at every depth, so no
        # additional top-level filtering is needed here.
        data = self.to_python()
        try:
            return self.schema_class.model_validate(data, by_name=True)
        except ValidationError as e:
            errors = [
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                for err in e.errors()
            ]
            paths = [".".join(str(p) for p in err["loc"]) for err in e.errors()]
            raise ValidationFailedError(errors, paths=paths) from e

    def to_output_python(self, *, by_alias: bool = False) -> dict[str, Any]:
        """Materialize and dump tree values, including configured variant metadata."""
        instance = self.to_instance()
        data = instance.model_dump(
            mode="json",
            by_alias=by_alias,
            fallback=_json_safe_any_value,
        )
        data = _overlay_any_output_values(data, self.root, by_alias=by_alias)
        if (
            self.variant is not None
            and self.variant.persistence == "inline_discriminator"
            and self.variant.discriminator
        ):
            if self.variant.discriminator in data:
                msg = (
                    f"inline discriminator key {self.variant.discriminator!r} "
                    "conflicts with a model output field"
                )
                raise ValueError(msg)
            data = {self.variant.discriminator: self.variant.selected_id, **data}
        return data

    def missing_required_paths(self) -> list[str]:
        """Dotted paths of required leaves with no value, in field order.

        Drives the required-field guidance surface: the `n` jump key,
        the HelpBar counter, and the post-save-failure cursor jump.
        Containers are walked (sequence items, mapping values, selected
        union variants); an *unselected* union only counts when the
        field itself is required.
        """
        out: list[str] = []
        _collect_missing_required(self.root, "", out)
        return out

    @model_validator(mode="after")
    def _inject_schema_from_context(self, info: ValidationInfo) -> FormTree:
        """If schema_class is missing (e.g., loaded from JSON), pull it
        from the validation context (which ``draft_load`` supplies)."""
        if self.schema_class is None and info.context and "schema_class" in info.context:
            self.schema_class = info.context["schema_class"]
        return self

    def attach_variant_registry(
        self,
        variants: Any,
        *,
        selected_id: str,
        discriminator: str | None = None,
        persistence: Literal["metadata", "inline_discriminator"] = "metadata",
    ) -> None:
        """Attach caller-supplied root variant choices to this tree."""
        options = [
            VariantOption(
                id=spec.id,
                label=spec.display_label,
                description=spec.description,
                model_type_name=spec.model_type_name,
            )
            for spec in variants
        ]
        ids = {option.id for option in options}
        if selected_id not in ids:
            msg = f"selected variant {selected_id!r} is not in registry"
            raise ValueError(msg)
        self.variant = VariantState(
            options=options,
            selected_id=selected_id,
            discriminator=discriminator,
            persistence=persistence,
        )

    def select_root_variant(self, variant_id: str, seed: Any = None) -> ValidationResult:
        """Switch the root model to a caller-supplied variant."""
        if self.variant is None:
            return ValidationResult.fail(["tree does not have root variants"])
        option = next(
            (candidate for candidate in self.variant.options if candidate.id == variant_id),
            None,
        )
        if option is None:
            known = ", ".join(candidate.id for candidate in self.variant.options)
            return ValidationResult.fail(
                [f"unknown variant id {variant_id!r}; known variants: {known}"]
            )

        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        model = _resolve_type_name(option.model_type_name)
        builder = default_registry().find(model)
        root_seed = {} if seed is None else seed
        new_root, errors = _build_seeded_node(
            builder, model, FieldInfo(annotation=model), root_seed
        )
        if errors:
            return ValidationResult.fail(errors)
        if not isinstance(new_root, GroupNode):
            return ValidationResult.fail(
                [f"variant {variant_id!r} did not build a group root"]
            )

        self.schema_class = model
        self.schema_name = f"{model.__module__}:{model.__qualname__}"
        self.root = new_root
        self.variant.selected_id = variant_id
        # Root variant switches replace the schema as well as values. Existing
        # root-only snapshots belong to the old schema, so keeping them would
        # let undo restore an incompatible root.
        self.snapshots = []
        self.cursor = 0
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    # ----- mutations -----

    def set_value(self, path: str, value: Any) -> ValidationResult:
        """Set ``value`` at the given path; runs node-local validation.

        Path segments may be field names (str) — for navigating into
        GroupNode children — or integer indices — for SequenceNode items
        and MappingNode entries (where the index targets the *value* side
        of the (key, value) pair). The terminal segment identifies the
        node whose ``value`` field is mutated.

        On success: push a snapshot, write the value to the target node,
        clear ``target.error``, and return ``ValidationResult.ok()``.

        On failure: leave ``target.value`` untouched (so the FormTree's
        typed fields stay type-correct and snapshots remain serializable),
        record the first error message on ``target.error`` for renderer
        display, and return ``ValidationResult.fail(...)``. Note that
        ``target.error`` carries only the primary message; the full list
        of errors lives in the returned ``ValidationResult``.

        Cross-field validation runs at submit time (``to_instance``).
        """
        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.paths import Path as _Path

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            msg = "cannot set value on the root group itself"
            raise ValueError(msg)

        # Walk all but the last segment, pivoting on the current node's type.
        # Collect the GroupNodes on the way so a successful write can
        # activate any *omitted* optional group the edit passed through.
        node: Any = self.root
        walked_groups: list[GroupNode] = []
        for seg in path_obj.segments[:-1]:
            if isinstance(node, GroupNode):
                walked_groups.append(node)
            node = self._descend(node, seg)
        if isinstance(node, GroupNode):
            walked_groups.append(node)

        # Resolve the terminal segment to a target node.
        last = path_obj.segments[-1]
        target = self._descend(node, last)
        write_target = target
        if isinstance(target, UnionNode):
            if target.selected is None:
                return ValidationResult.fail(["union has no selected variant"])
            write_target = target.selected
            if not hasattr(write_target, "value"):
                return ValidationResult.fail(
                    ["selected union variant is not directly editable"]
                )

        errors = write_target.validate_value(value)
        if errors:
            write_target.error = errors[0]
            target.error = errors[0]
            return ValidationResult.fail(list(errors))

        # Validation passed: snapshot before mutating so undo can revert.
        self._push_snapshot(_snap.take(self.root))
        editable_target = cast("Any", write_target)
        editable_target.value = value
        editable_target.error = None
        # Editing any descendant activates omitted optional groups on the
        # path — from now on the group materializes instead of None.
        for group in walked_groups:
            if group.omitted:
                group.omitted = False
        if isinstance(target, UnionNode):
            target.error = None
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def _descend(self, node: Any, seg: Any) -> Any:
        """Navigate one path segment into ``node``.

        Pivots on ``node``'s type:
        - GroupNode + str → child by name
        - SequenceNode + int → items[seg]
        - MappingNode + int → entries[seg][1] (the value node)

        Raises KeyError on any mismatch (out-of-range index, unknown name,
        or type/segment mismatch).
        """
        if isinstance(node, GroupNode) and isinstance(seg, str):
            child = node.find(seg)
            if child is None:
                msg = f"no field named {seg!r} at this level"
                raise KeyError(msg)
            return child
        if isinstance(node, SequenceNode) and isinstance(seg, int):
            if not (0 <= seg < len(node.items)):
                msg = f"index {seg} out of range for sequence of length {len(node.items)}"
                raise KeyError(msg)
            return node.items[seg]
        if isinstance(node, MappingNode) and isinstance(seg, int):
            if not (0 <= seg < len(node.entries)):
                msg = f"index {seg} out of range for mapping of length {len(node.entries)}"
                raise KeyError(msg)
            # Index into mapping selects the value side of the pair —
            # rename_key handles the key side via its dedicated mutation.
            return node.entries[seg][1]
        if isinstance(node, UnionNode):
            if node.selected is None:
                msg = "cannot navigate into a union with no selected variant"
                raise KeyError(msg)
            return self._descend(node.selected, seg)
        msg = (
            f"cannot navigate segment {seg!r} into {type(node).__name__} "
            f"(no rule for ({type(node).__name__}, {type(seg).__name__}))"
        )
        raise KeyError(msg)

    def _resolve_path(self, path: str) -> Any:
        """Resolve ``path`` to a node using the same descent rules as set_value."""
        from pydantic_studio.tree.paths import Path as _Path

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            return self.root
        node: Any = self.root
        for seg in path_obj.segments:
            node = self._descend(node, seg)
        return node

    def _walk_to_sequence(self, path: str) -> SequenceNode:
        """Resolve ``path`` and return the SequenceNode at that location."""

        node = self._resolve_path(path)
        if not isinstance(node, SequenceNode):
            msg = f"{path!r} is not a SequenceNode"
            raise TypeError(msg)
        return node

    @staticmethod
    def _validate_sequence_length(seq: SequenceNode, new_length: int) -> ValidationResult:
        errors: list[str] = []
        if seq.min_length is not None and new_length < seq.min_length:
            errors.append(f"length must be >= {seq.min_length}")
        if seq.max_length is not None and new_length > seq.max_length:
            errors.append(f"length must be <= {seq.max_length}")
        if errors:
            return ValidationResult.fail(errors)
        return ValidationResult.ok()

    def add_item(self, path: str, value: Any = None) -> ValidationResult:
        """Append a default child to the SequenceNode at ``path``."""
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        seq = self._walk_to_sequence(path)
        if seq.origin == "tuple_fixed":
            return ValidationResult.fail(["cannot add to a fixed-length tuple"])
        if seq.item_type_name is None:
            return ValidationResult.fail(["sequence has no item_type_name"])
        length_result = self._validate_sequence_length(seq, len(seq.items) + 1)
        if not length_result.ok:
            return length_result
        # Resolve + build BEFORE snapshotting — failure here must not pollute
        # the undo history (mirrors the validate-first contract of set_value).
        item_type = _resolve_type_name(seq.item_type_name)
        builder = default_registry().find(item_type)
        item_field = FieldInfo(annotation=item_type)
        child = builder.build(item_type, item_field, None)
        if value is not None:
            errors = child.validate_value(value)
            if errors:
                return ValidationResult.fail(list(errors))
            child = builder.build(item_type, item_field, value)
        child.name = str(len(seq.items))
        self._push_snapshot(_snap.take(self.root))
        seq.items = [*seq.items, child]
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def remove_item(self, path: str, index: int) -> ValidationResult:
        """Remove the child at ``index`` from the SequenceNode at ``path``."""
        from pydantic_studio.tree import snapshots as _snap

        seq = self._walk_to_sequence(path)
        if not (0 <= index < len(seq.items)):
            return ValidationResult.fail([f"index {index} out of range"])
        length_result = self._validate_sequence_length(seq, len(seq.items) - 1)
        if not length_result.ok:
            return length_result
        self._push_snapshot(_snap.take(self.root))
        new_items = [it for i, it in enumerate(seq.items) if i != index]
        for i, it in enumerate(new_items):
            it.name = str(i)
        seq.items = new_items
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def insert_item(
        self, path: str, index: int, value: Any = None
    ) -> ValidationResult:
        """Insert a new child at ``index`` in the SequenceNode at ``path``."""
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        seq = self._walk_to_sequence(path)
        if seq.origin == "tuple_fixed":
            return ValidationResult.fail(
                ["cannot insert into a fixed-length tuple"]
            )
        if not (0 <= index <= len(seq.items)):
            return ValidationResult.fail([f"index {index} out of range"])
        if seq.item_type_name is None:
            return ValidationResult.fail(["sequence has no item_type_name"])
        length_result = self._validate_sequence_length(seq, len(seq.items) + 1)
        if not length_result.ok:
            return length_result
        item_type = _resolve_type_name(seq.item_type_name)
        builder = default_registry().find(item_type)
        item_field = FieldInfo(annotation=item_type)
        child = builder.build(item_type, item_field, None)
        if value is not None:
            errors = child.validate_value(value)
            if errors:
                return ValidationResult.fail(list(errors))
            child = builder.build(item_type, item_field, value)
        self._push_snapshot(_snap.take(self.root))
        new_items = [*seq.items[:index], child, *seq.items[index:]]
        for i, it in enumerate(new_items):
            it.name = str(i)
        seq.items = new_items
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def move_item(
        self, path: str, from_index: int, to_index: int
    ) -> ValidationResult:
        """Move the child at ``from_index`` to ``to_index`` in the SequenceNode at ``path``."""
        from pydantic_studio.tree import snapshots as _snap

        seq = self._walk_to_sequence(path)
        if not (0 <= from_index < len(seq.items)):
            return ValidationResult.fail(
                [f"from_index {from_index} out of range"]
            )
        if not (0 <= to_index < len(seq.items)):
            return ValidationResult.fail(
                [f"to_index {to_index} out of range"]
            )
        self._push_snapshot(_snap.take(self.root))
        items = list(seq.items)
        item = items.pop(from_index)
        items.insert(to_index, item)
        for i, it in enumerate(items):
            it.name = str(i)
        seq.items = items
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def _walk_to_mapping(self, path: str) -> MappingNode:
        """Resolve ``path`` and return the MappingNode at that location."""

        node = self._resolve_path(path)
        if not isinstance(node, MappingNode):
            msg = f"{path!r} is not a MappingNode"
            raise TypeError(msg)
        return node

    @staticmethod
    def _validate_mapping_length(mp: MappingNode, new_length: int) -> ValidationResult:
        errors: list[str] = []
        if mp.min_length is not None and new_length < mp.min_length:
            errors.append(f"length must be >= {mp.min_length}")
        if mp.max_length is not None and new_length > mp.max_length:
            errors.append(f"length must be <= {mp.max_length}")
        if errors:
            return ValidationResult.fail(errors)
        return ValidationResult.ok()

    @staticmethod
    def _validate_mapping_unique_key(
        mp: MappingNode, key: Any, exclude_index: int | None = None
    ) -> ValidationResult:
        for index, (key_node, _value_node) in enumerate(mp.entries):
            if exclude_index is not None and index == exclude_index:
                continue
            if key_node.to_python() == key:
                return ValidationResult.fail([f"duplicate key {key!r}"])
        return ValidationResult.ok()

    def add_entry(
        self, path: str, key: Any, value: Any = None
    ) -> ValidationResult:
        """Append a (key, value) entry to the MappingNode at ``path``."""
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        mp = self._walk_to_mapping(path)
        length_result = self._validate_mapping_length(mp, len(mp.entries) + 1)
        if not length_result.ok:
            return length_result
        key_type = _resolve_type_name(mp.key_type_name)
        value_type = _resolve_type_name(mp.value_type_name)
        reg = default_registry()
        k_builder = reg.find(key_type)
        v_builder = reg.find(value_type)
        key_field = FieldInfo(annotation=key_type)
        k_node = k_builder.build(key_type, key_field, None)
        key_errors = k_node.validate_value(key)
        if key_errors:
            return ValidationResult.fail(list(key_errors))
        k_node = k_builder.build(key_type, key_field, key)
        unique_result = self._validate_mapping_unique_key(mp, k_node.to_python())
        if not unique_result.ok:
            return unique_result
        value_field = FieldInfo(annotation=value_type)
        v_node = v_builder.build(value_type, value_field, None)
        if value is not None:
            value_errors = v_node.validate_value(value)
            if value_errors:
                return ValidationResult.fail(list(value_errors))
            v_node = v_builder.build(value_type, value_field, value)
        k_node.name = "key"
        v_node.name = "value"
        self._push_snapshot(_snap.take(self.root))
        mp.entries = [*mp.entries, (k_node, v_node)]
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def remove_entry(self, path: str, index: int) -> ValidationResult:
        """Remove the entry at ``index`` from the MappingNode at ``path``."""
        from pydantic_studio.tree import snapshots as _snap

        mp = self._walk_to_mapping(path)
        if not (0 <= index < len(mp.entries)):
            return ValidationResult.fail([f"index {index} out of range"])
        length_result = self._validate_mapping_length(mp, len(mp.entries) - 1)
        if not length_result.ok:
            return length_result
        self._push_snapshot(_snap.take(self.root))
        mp.entries = [e for i, e in enumerate(mp.entries) if i != index]
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def rename_key(
        self, path: str, index: int, new_key: Any
    ) -> ValidationResult:
        """Rename the key at ``index`` in the MappingNode at ``path``."""
        from pydantic_studio.tree import snapshots as _snap

        mp = self._walk_to_mapping(path)
        if not (0 <= index < len(mp.entries)):
            return ValidationResult.fail([f"index {index} out of range"])
        k_node, _v_node = mp.entries[index]
        errors = k_node.validate_value(new_key)
        if errors:
            return ValidationResult.fail(list(errors))
        unique_result = self._validate_mapping_unique_key(mp, new_key, exclude_index=index)
        if not unique_result.ok:
            return unique_result
        # Validation passed — push snapshot and mutate.
        self._push_snapshot(_snap.take(self.root))
        cast("Any", k_node).value = new_key
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    # ----- snapshot internals -----

    def _push_snapshot(self, snap: bytes) -> None:
        # If the cursor is not at the tail, drop the redo tail before pushing.
        if self.cursor < len(self.snapshots):
            self.snapshots = self.snapshots[: self.cursor]
        self.snapshots.append(snap)
        # Bound: drop oldest until under the limit.
        while len(self.snapshots) > self.snapshot_limit:
            self.snapshots.pop(0)
        self.cursor = len(self.snapshots)

    def undo(self) -> bool:
        """Restore the previous state. Returns True if anything was undone."""
        from pydantic_studio.tree import snapshots as _snap

        if self.cursor == 0:
            return False
        # The current state isn't yet on the stack; only prior states are.
        # Step back: cursor points to the snapshot that *was* the state before
        # the most recent mutation. To allow redo, capture the current state
        # first if cursor == len(snapshots).
        if self.cursor == len(self.snapshots):
            self.snapshots.append(_snap.take(self.root))
        self.cursor -= 1
        self.root = _snap.restore(self.snapshots[self.cursor])
        return True

    def redo(self) -> bool:
        """Re-apply a previously undone mutation."""
        from pydantic_studio.tree import snapshots as _snap

        if self.cursor + 1 >= len(self.snapshots):
            return False
        self.cursor += 1
        self.root = _snap.restore(self.snapshots[self.cursor])
        return True

    def _walk_to_union(self, path: str) -> UnionNode:
        node = self._resolve_path(path)
        if not isinstance(node, UnionNode):
            msg = f"{path!r} is not a UnionNode"
            raise TypeError(msg)
        return node

    def select_variant(
        self, path: str, variant_index: int, seed: Any = None
    ) -> ValidationResult:
        """Switch the UnionNode at ``path`` to its ``variant_index``-th variant.

        If ``seed`` is provided, the freshly-built variant is initialized
        with that value (otherwise its value is None / default).
        """
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        union = self._walk_to_union(path)
        if not (0 <= variant_index < len(union.variant_type_names)):
            return ValidationResult.fail(
                [
                    f"variant index {variant_index} out of range "
                    f"(0..{len(union.variant_type_names) - 1})"
                ]
            )
        v_type = _resolve_type_name(union.variant_type_names[variant_index])
        builder = default_registry().find(v_type)
        new_selected, errors = _build_seeded_node(
            builder, v_type, FieldInfo(annotation=v_type), seed
        )
        if errors:
            return ValidationResult.fail(errors)
        if new_selected is None:
            return ValidationResult.fail(
                [f"variant {variant_index!r} did not build a selected node"]
            )
        self._push_snapshot(_snap.take(self.root))
        union.selected_index = variant_index
        union.selected = new_selected
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()
