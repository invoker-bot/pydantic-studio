"""Extract numeric / string / decimal constraints from a Pydantic FieldInfo.

Pydantic v2 stores constraints in ``field_info.metadata`` as objects from
``annotated_types`` (``Ge``, ``Le``, ``Gt``, ``Lt``, ``MultipleOf``,
``MinLen``, ``MaxLen``, ``Interval``, ``Len``) plus Pydantic's own
``StringConstraints`` and ``Decimal`` helpers. ``Field(min_length=...)``
calls also normalize into the same shape.

This module flattens those into a plain dict so each builder picks the
keys it understands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def extract_constraints(field_info: FieldInfo) -> dict[str, Any]:
    """Flatten ``field_info.metadata`` into a constraint dict.

    Recognized keys:
        ge, le, gt, lt, multiple_of   — numeric (annotated_types.Interval/Ge/Le/Gt/Lt/MultipleOf)
        min_length, max_length        — sequence/string
                                      (annotated_types.MinLen/MaxLen, StringConstraints)
        pattern                       — string (StringConstraints.pattern, only ``str`` instances —
                                        compiled ``re.Pattern`` objects are skipped)
        max_digits, decimal_places    — Decimal (pydantic Decimal helper)

    If multiple metadata items set the same key the last item wins
    (dict assignment). In practice Pydantic rejects most double-constraint
    annotations at schema build time, so this rarely matters.

    Unknown metadata items are silently ignored.
    """
    out: dict[str, Any] = {}
    for item in getattr(field_info, "metadata", []) or []:
        for attr, key in (
            ("ge", "ge"),
            ("le", "le"),
            ("gt", "gt"),
            ("lt", "lt"),
            ("multiple_of", "multiple_of"),
            ("min_length", "min_length"),
            ("max_length", "max_length"),
            ("max_digits", "max_digits"),
            ("decimal_places", "decimal_places"),
        ):
            v = getattr(item, attr, None)
            if v is not None:
                out[key] = v
        # StringConstraints.pattern is a string or None.
        pat = getattr(item, "pattern", None)
        if pat is not None and isinstance(pat, str):
            out["pattern"] = pat
    return out
