"""Unit tests for render.py — YAML preview + the _coerce_to_yaml_safe shim.

The preview path has two sources: ``model_dump(mode="json")`` on success,
``tree.to_python()`` on validation/serialization failure. The latter can
return Enum/Decimal/UUID/time/timedelta/HttpUrl objects that ruamel.yaml
refuses to represent. ``_coerce_to_yaml_safe`` flattens these before the
dump so the preview never crashes.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import IntEnum, StrEnum
from pathlib import PurePosixPath
from uuid import UUID

from pydantic import BaseModel, SecretBytes, SecretStr

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html.render import (
    _coerce_to_yaml_safe,
    render_yaml_preview,
)


class _Level(StrEnum):
    INFO = "info"


class _Tier(IntEnum):
    GOLD = 1


def test_coerce_passes_through_yaml_native_scalars() -> None:
    for v in ("x", 1, 1.5, True, False, None):
        assert _coerce_to_yaml_safe(v) == v


def test_coerce_passes_through_yaml_native_temporals() -> None:
    d = date(2025, 1, 1)
    dt = datetime(2025, 1, 1, 12, 0, 0)
    assert _coerce_to_yaml_safe(d) is d
    assert _coerce_to_yaml_safe(dt) is dt


def test_coerce_passes_through_bytes() -> None:
    b = b"\xde\xad\xbe\xef"
    assert _coerce_to_yaml_safe(b) is b


def test_coerce_str_enum_unwraps_to_str() -> None:
    out = _coerce_to_yaml_safe(_Level.INFO)
    assert out == "info"
    assert type(out) is str


def test_coerce_int_enum_unwraps_to_int() -> None:
    out = _coerce_to_yaml_safe(_Tier.GOLD)
    assert out == 1
    assert type(out) is int


def test_coerce_decimal_to_str() -> None:
    assert _coerce_to_yaml_safe(Decimal("0.00")) == "0.00"


def test_coerce_uuid_to_str() -> None:
    u = UUID("00000000-0000-0000-0000-000000000000")
    assert _coerce_to_yaml_safe(u) == "00000000-0000-0000-0000-000000000000"


def test_coerce_time_and_timedelta_to_str() -> None:
    assert _coerce_to_yaml_safe(time(2, 30, 0)) == "02:30:00"
    assert _coerce_to_yaml_safe(timedelta(hours=1)) == "1:00:00"


def test_coerce_path_to_str() -> None:
    assert _coerce_to_yaml_safe(PurePosixPath("/etc/conf")) == "/etc/conf"


def test_coerce_secrets_are_masked() -> None:
    assert _coerce_to_yaml_safe(SecretStr("hunter2")) == "**********"
    assert _coerce_to_yaml_safe(SecretBytes(b"hunter2")) == "**********"


def test_coerce_walks_nested_dicts_and_lists() -> None:
    payload = {
        "level": _Level.INFO,
        "amounts": [Decimal("1.0"), Decimal("2.5")],
        "ids": {"primary": UUID(int=1)},
    }
    out = _coerce_to_yaml_safe(payload)
    assert out == {
        "level": "info",
        "amounts": ["1.0", "2.5"],
        "ids": {"primary": "00000000-0000-0000-0000-000000000001"},
    }


def test_coerce_unknown_object_falls_back_to_str() -> None:
    class _Custom:
        def __str__(self) -> str:
            return "custom-stringified"

    assert _coerce_to_yaml_safe(_Custom()) == "custom-stringified"


def test_render_yaml_preview_survives_non_utf8_bytes_field() -> None:
    """Regression: pydantic v2's model_dump(mode='json') raises
    UnicodeDecodeError on non-UTF8 bytes. The preview must fall back to
    tree.to_python() and coerce, not 500 the /api/tree response.
    """

    class M(BaseModel):
        name: str = ""
        salt: bytes = b""

    tree = build_form_tree(M)
    tree.set_value("name", "demo")
    tree.set_value("salt", b"\xde\xad\xbe\xef")
    out = render_yaml_preview(tree)
    assert "name: demo" in out
    assert not out.startswith("<preview error")


def test_render_yaml_preview_inlines_enum_value() -> None:
    class M(BaseModel):
        level: _Level = _Level.INFO

    tree = build_form_tree(M)
    tree.set_value("level", _Level.INFO)
    out = render_yaml_preview(tree)
    assert "level: info" in out
