"""Builders for all temporal annotations: ``datetime``, ``date``, ``time``,
and ``timedelta``.

Pydantic round-trips these via ISO 8601 strings (durations use ISO 8601
duration format, e.g. ``PT1H30M``), so the builders only need to detect
the annotation and bind a default.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import DateNode, DatetimeNode, TimedeltaNode, TimeNode
from pydantic_studio.types.annotated import strip_annotated

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def _default(field_info: FieldInfo) -> Any:
    d = field_info.get_default(call_default_factory=True)
    return None if d is PydanticUndefined else d


class DatetimeBuilder:
    """Matches ``datetime.datetime`` annotations."""

    def matches(self, type_: type) -> bool:
        return strip_annotated(type_) is datetime

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> DatetimeNode:
        default = _default(field_info)
        return DatetimeNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )


class DateBuilder:
    """Matches ``datetime.date`` annotations.

    Note: this must come *after* DatetimeBuilder in the registry's match
    order if we ever check `issubclass(t, date)` — but ``strip_annotated(t)
    is date`` is identity-based, so order doesn't matter here.
    """

    def matches(self, type_: type) -> bool:
        return strip_annotated(type_) is date

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> DateNode:
        default = _default(field_info)
        return DateNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )


class TimeBuilder:
    """Matches ``datetime.time`` annotations."""

    def matches(self, type_: type) -> bool:
        return strip_annotated(type_) is time

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> TimeNode:
        default = _default(field_info)
        return TimeNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )


class TimedeltaBuilder:
    """Matches ``datetime.timedelta`` annotations."""

    def matches(self, type_: type) -> bool:
        return strip_annotated(type_) is timedelta

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> TimedeltaNode:
        default = _default(field_info)
        return TimedeltaNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )
