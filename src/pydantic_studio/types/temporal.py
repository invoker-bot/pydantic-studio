"""Builders for all temporal annotations: ``datetime``, ``date``, ``time``,
and ``timedelta``.

Pydantic round-trips these via ISO 8601 strings (durations use ISO 8601
duration format, e.g. ``PT1H30M``), so the builders only need to detect
the annotation and bind a default.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from pydantic_studio.tree.nodes import DateNode, DatetimeNode, TimedeltaNode, TimeNode
from pydantic_studio.types.annotated import strip_annotated
from pydantic_studio.types.utils import field_default

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def _is_subclass_of(type_: Any, target: type) -> bool:
    """``True`` when ``type_`` (after Annotated-stripping) is a class
    derived from ``target``. The ``isinstance(..., type)`` guard rejects
    typing special forms that would crash ``issubclass``.
    """
    unwrapped = strip_annotated(type_)
    return isinstance(unwrapped, type) and issubclass(unwrapped, target)


class DatetimeBuilder:
    """Matches ``datetime.datetime`` and subclasses."""

    def matches(self, type_: type) -> bool:
        return _is_subclass_of(type_, datetime)

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> DatetimeNode:
        default = field_default(field_info)
        return DatetimeNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )


class DateBuilder:
    """Matches ``datetime.date`` and subclasses, but *not* ``datetime``.

    ``datetime`` IS-A ``date`` in the stdlib, so the subclass-aware
    matcher would otherwise grab plain ``datetime`` fields away from
    DatetimeBuilder. Mirrors the ``bool ⊆ int`` exclusion in IntBuilder.
    """

    def matches(self, type_: type) -> bool:
        return _is_subclass_of(type_, date) and not _is_subclass_of(type_, datetime)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> DateNode:
        default = field_default(field_info)
        return DateNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )


class TimeBuilder:
    """Matches ``datetime.time`` and subclasses."""

    def matches(self, type_: type) -> bool:
        return _is_subclass_of(type_, time)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> TimeNode:
        default = field_default(field_info)
        return TimeNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )


class TimedeltaBuilder:
    """Matches ``datetime.timedelta`` and subclasses."""

    def matches(self, type_: type) -> bool:
        return _is_subclass_of(type_, timedelta)

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> TimedeltaNode:
        default = field_default(field_info)
        return TimedeltaNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            value=existing if existing is not None else default,
            default=default,
        )
