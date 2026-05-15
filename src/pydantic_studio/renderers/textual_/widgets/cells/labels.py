"""Shared label helpers for cell widgets.

These small public helpers live here so that both inline cells (e.g.
``ChoiceCell``) and drill-down screens (e.g. ``ChooserScreen``) can
produce the same user-facing label for the same node value -- avoiding
UX drift between, say, the inline display and a popup list.
"""

from __future__ import annotations

from typing import Any


def enum_label(value: Any) -> str:
    """Return a user-facing label for an Enum member (or any value).

    Prefer ``value.value`` (typical user-facing string, e.g. ``"info"``)
    over ``value.name`` (the Python identifier, e.g. ``"INFO"``) when the
    underlying value is a primitive (str / int / float / bool). Fall
    back to ``value.name`` if the value isn't primitive-friendly, and
    finally to ``str(value)`` if neither attribute is present.
    """
    inner = getattr(value, "value", None)
    if isinstance(inner, (str, int, float, bool)):
        return str(inner)
    if hasattr(value, "name"):
        return str(value.name)
    return str(value)
