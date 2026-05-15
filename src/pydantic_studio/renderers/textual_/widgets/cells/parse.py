"""Parse raw text input into the typed value a node expects.

Resurrects the helper that lived in the cutover-deleted ``scalars.py``.
Same surface, different name (no leading underscore — this is the
cells package's public parser).

For 16 leaf kinds the function returns ``(True, value)`` on success
and ``(False, None)`` on any parse failure. Empty input is treated as
None with ``ok=True`` so the calling cell can defer to the node's
own ``validate_value`` for Optional[T] handling.
"""

from __future__ import annotations

from typing import Any


def parse_for_kind(kind: str, raw: str) -> tuple[bool, Any]:
    """Convert ``raw`` to the type ``kind`` expects.

    Returns ``(ok, value)``. ``ok=False`` means the raw string could not
    be parsed (e.g., "abc" for kind="int"); the caller should display a
    parse error and leave the node's value unchanged. ``ok=True`` with
    ``value=None`` means the user entered empty text — let the node's
    validate_value decide.
    """
    raw = raw.strip()
    if raw == "":
        return True, None

    try:
        if kind == "string":
            return True, raw
        if kind == "int":
            return True, int(raw)
        if kind == "float":
            return True, float(raw)
        if kind == "decimal":
            from decimal import Decimal

            return True, Decimal(raw)
        if kind == "datetime":
            from datetime import datetime

            return True, datetime.fromisoformat(raw)
        if kind == "date":
            from datetime import date

            return True, date.fromisoformat(raw)
        if kind == "time":
            from datetime import time

            return True, time.fromisoformat(raw)
        if kind == "timedelta":
            from datetime import timedelta

            from pydantic import TypeAdapter

            return True, TypeAdapter(timedelta).validate_python(raw)
        if kind in ("ip_address", "ip_network", "url", "email", "path", "pattern"):
            # Node stores these as strings; the node's validate_value parses.
            return True, raw
        if kind == "secret":
            return True, raw
        if kind == "uuid":
            from uuid import UUID

            return True, UUID(raw)
        if kind == "bytes":
            # Hex by default — matches BytesNode.field_serializer convention.
            return True, bytes.fromhex(raw)
    except (ValueError, TypeError, ArithmeticError):
        # ArithmeticError covers decimal.InvalidOperation for bad Decimal inputs.
        return False, None
    return False, None
