"""Unit tests for cells.parse.parse_for_kind — converts a raw string
from a text Input into the typed value the node expects.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

import pytest

from pydantic_studio.renderers.textual_.widgets.cells.parse import parse_for_kind


@pytest.mark.parametrize(
    ("kind", "raw", "expected"),
    [
        ("string", "alpha", "alpha"),
        ("int", "42", 42),
        ("float", "0.5", 0.5),
        ("decimal", "9.99", Decimal("9.99")),
        ("datetime", "2025-01-01T12:00:00", datetime(2025, 1, 1, 12, 0, 0)),
        ("date", "2025-01-01", date(2025, 1, 1)),
        ("time", "02:30:00", time(2, 30, 0)),
        ("ip_address", "10.0.0.1", "10.0.0.1"),  # stored as str; node validates
        ("ip_network", "10.0.0.0/24", "10.0.0.0/24"),
        ("url", "https://example.com", "https://example.com"),
        ("email", "ops@example.com", "ops@example.com"),
        ("path", "/etc/conf", "/etc/conf"),
        ("pattern", "^[a-z]+$", "^[a-z]+$"),
        ("secret", "hunter2", "hunter2"),
        ("uuid", "00000000-0000-0000-0000-000000000001", UUID(int=1)),
        ("bytes", "deadbeef", b"\xde\xad\xbe\xef"),
    ],
)
def test_parse_for_kind_happy_path(kind: str, raw: str, expected) -> None:
    ok, value = parse_for_kind(kind, raw)
    assert ok is True
    assert value == expected


def test_parse_for_kind_empty_returns_none() -> None:
    """Empty input passes (ok=True) with value=None so the node's
    validate_value gets to decide whether None is acceptable (e.g.,
    Optional[T] fields)."""
    ok, value = parse_for_kind("string", "")
    assert ok is True
    assert value is None


def test_parse_for_kind_int_bad_input_returns_failure() -> None:
    ok, value = parse_for_kind("int", "not-a-number")
    assert ok is False
    assert value is None


def test_parse_for_kind_float_bad_input_returns_failure() -> None:
    ok, value = parse_for_kind("float", "abc")
    assert ok is False
    assert value is None


def test_parse_for_kind_decimal_bad_input_returns_failure() -> None:
    ok, value = parse_for_kind("decimal", "not-numeric")
    assert ok is False
    assert value is None


def test_parse_for_kind_uuid_bad_input_returns_failure() -> None:
    ok, value = parse_for_kind("uuid", "not-a-uuid")
    assert ok is False
    assert value is None


def test_parse_for_kind_bytes_odd_hex_returns_failure() -> None:
    """bytes.fromhex rejects odd-length hex; the function surfaces this
    as ok=False instead of letting the ValueError escape."""
    ok, value = parse_for_kind("bytes", "abc")  # odd length
    assert ok is False
    assert value is None


def test_parse_for_kind_strips_whitespace() -> None:
    ok, value = parse_for_kind("int", "  42  ")
    assert ok is True
    assert value == 42


def test_parse_for_kind_unknown_kind_returns_failure() -> None:
    """A kind the helper doesn't know about returns ok=False, not a
    surprise raise. Defensive — the dispatcher in FieldRow ensures we
    never reach here in practice."""
    ok, value = parse_for_kind("not-a-kind", "anything")
    assert ok is False
    assert value is None
