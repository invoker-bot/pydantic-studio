"""Tests for the temporal type family — datetime/date/time."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from pydantic import BaseModel

from pydantic_studio import (
    DateNode,
    DatetimeNode,
    TimeNode,
    build_form_tree,
)


class WithTemporal(BaseModel):
    when: datetime = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    on: date = date(2026, 1, 1)
    at: time = time(9, 30)


class TestDatetimeNode:
    def test_build_uses_datetime_node(self) -> None:
        tree = build_form_tree(WithTemporal)
        when = tree.root.find("when")
        assert isinstance(when, DatetimeNode)
        assert when.value == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def test_validate_accepts_datetime(self) -> None:
        node = DatetimeNode(name="x", value=None)
        assert node.validate_value(datetime(2026, 5, 6)) == ()

    def test_validate_rejects_str(self) -> None:
        """The renderer is responsible for parsing user input strings into
        datetime instances before calling set_value. Validation expects the
        already-parsed type."""
        node = DatetimeNode(name="x", value=None)
        errors = node.validate_value("2026-05-06T12:00:00")
        assert errors  # non-empty
        assert "expected datetime" in errors[0]

    def test_validate_rejects_date_and_time_subtypes(self) -> None:
        """date is not a datetime even though datetime IS a date subclass."""
        node = DatetimeNode(name="x", value=None)
        # date is the parent — pass a pure date and we should reject.
        errors = node.validate_value(date(2026, 5, 6))
        assert errors
        assert "expected datetime" in errors[0]

    def test_required_none_fails(self) -> None:
        node = DatetimeNode(name="x", required=True, value=None)
        errors = node.validate_value(None)
        assert errors == ("value is required",)

    def test_optional_none_ok(self) -> None:
        node = DatetimeNode(name="x", required=False, value=None)
        assert node.validate_value(None) == ()

    def test_to_python_returns_value(self) -> None:
        d = datetime(2026, 5, 6, 12, 0)
        node = DatetimeNode(name="x", value=d)
        assert node.to_python() == d

    def test_snapshot_round_trip(self) -> None:
        """Pydantic emits ISO strings + parses them back on validate."""
        node = DatetimeNode(name="x", value=datetime(2026, 5, 6, 12, 0, tzinfo=UTC))
        raw = node.model_dump_json()
        restored = DatetimeNode.model_validate_json(raw)
        assert restored.value == node.value


class TestDateNode:
    def test_build_uses_date_node(self) -> None:
        tree = build_form_tree(WithTemporal)
        on = tree.root.find("on")
        assert isinstance(on, DateNode)
        assert on.value == date(2026, 1, 1)

    def test_validate_accepts_date(self) -> None:
        node = DateNode(name="x", value=None)
        assert node.validate_value(date(2026, 5, 6)) == ()

    def test_validate_rejects_datetime(self) -> None:
        """A datetime is technically a date subclass in Python, but a date
        field cannot accept a datetime — the time component would be lost.
        Reject explicitly."""
        node = DateNode(name="x", value=None)
        errors = node.validate_value(datetime(2026, 5, 6))
        assert errors
        assert "expected date" in errors[0]

    def test_validate_rejects_str(self) -> None:
        node = DateNode(name="x", value=None)
        errors = node.validate_value("2026-05-06")
        assert errors

    def test_snapshot_round_trip(self) -> None:
        node = DateNode(name="x", value=date(2026, 5, 6))
        raw = node.model_dump_json()
        restored = DateNode.model_validate_json(raw)
        assert restored.value == node.value


class TestTimeNode:
    def test_build_uses_time_node(self) -> None:
        tree = build_form_tree(WithTemporal)
        at = tree.root.find("at")
        assert isinstance(at, TimeNode)
        assert at.value == time(9, 30)

    def test_validate_accepts_time(self) -> None:
        node = TimeNode(name="x", value=None)
        assert node.validate_value(time(12, 0)) == ()

    def test_validate_rejects_str(self) -> None:
        node = TimeNode(name="x", value=None)
        errors = node.validate_value("12:00:00")
        assert errors

    def test_snapshot_round_trip(self) -> None:
        node = TimeNode(name="x", value=time(12, 0, 30))
        raw = node.model_dump_json()
        restored = TimeNode.model_validate_json(raw)
        assert restored.value == node.value


class TestEndToEnd:
    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithTemporal)
        instance = tree.to_instance()
        assert isinstance(instance, WithTemporal)
        assert instance.when == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        assert instance.on == date(2026, 1, 1)
        assert instance.at == time(9, 30)

    def test_set_value_then_submit(self) -> None:
        tree = build_form_tree(WithTemporal)
        new_when = datetime(2027, 6, 15, 8, 0, tzinfo=UTC)
        result = tree.set_value("when", new_when)
        assert result.ok
        instance = tree.to_instance()
        assert instance.when == new_when
