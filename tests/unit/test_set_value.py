"""set_value contract: returns ValidationResult after node-local validation."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Annotated, Any

import pytest
from pydantic import BaseModel, Field, PlainValidator

from pydantic_studio import build_form_tree
from pydantic_studio.tree.validation import ValidationResult


class Schema(BaseModel):
    name: str = Field(min_length=3)
    age: int = Field(ge=0)


class ConstrainedIntSchema(BaseModel):
    at_least: int = Field(default=2, ge=1)
    at_most: int = Field(default=2, le=8)
    above: int = Field(default=2, gt=0)
    below: int = Field(default=2, lt=10)
    even: int = Field(default=2, multiple_of=2)


class ConstrainedFloatSchema(BaseModel):
    at_least: float = Field(default=0.5, ge=0.5)
    at_most: float = Field(default=0.5, le=1.0)
    above: float = Field(default=0.5, gt=0.0)
    below: float = Field(default=0.5, lt=1.0)
    quarter_step: float = Field(default=0.5, multiple_of=0.25)


class FiniteFloatSchema(BaseModel):
    ratio: float = Field(default=0.5, allow_inf_nan=False)


class ConstrainedDecimalSchema(BaseModel):
    at_least: Decimal = Field(default=Decimal("1.00"), ge=Decimal("1.00"))
    at_most: Decimal = Field(default=Decimal("1.00"), le=Decimal("2.00"))
    above: Decimal = Field(default=Decimal("1.00"), gt=Decimal("0.00"))
    below: Decimal = Field(default=Decimal("1.00"), lt=Decimal("2.00"))
    digit_limit: Decimal = Field(default=Decimal("1.00"), max_digits=4)
    cents: Decimal = Field(default=Decimal("1.00"), decimal_places=2)


class PlainDecimalSchema(BaseModel):
    price: Decimal = Decimal("1.00")


class FiniteDecimalSchema(BaseModel):
    price: Decimal = Field(default=Decimal("1.00"), allow_inf_nan=False)


class ConstrainedStringSchema(BaseModel):
    at_least: str = Field(default="good", min_length=3)
    at_most: str = Field(default="good", max_length=5)
    contains_marker: str = Field(default="abc", pattern="abc")
    unicode_letters: str = Field(default="abc", pattern=r"\p{L}+")


def _reject_bad_string(value: Any) -> str:
    if value == "bad":
        raise ValueError("bad blocked")
    return str(value)


class PlainValidatorStringSchema(BaseModel):
    token: Annotated[str, PlainValidator(_reject_bad_string)] = "ok"


class NestedProfile(BaseModel):
    host: str = "localhost"
    port: int = Field(default=5432, ge=1)


class NestedProfileSchema(BaseModel):
    profile: NestedProfile = Field(default_factory=NestedProfile)


def test_set_valid_value_returns_ok() -> None:
    tree = build_form_tree(Schema)
    result = tree.set_value("name", "Alice")
    assert isinstance(result, ValidationResult)
    assert result.ok is True
    assert result.errors == ()


def test_set_invalid_value_returns_errors() -> None:
    tree = build_form_tree(Schema)
    result = tree.set_value("age", "not-a-number")
    assert result.ok is False
    assert result.errors == ("expected int, got str",)


def test_set_value_does_not_mutate_on_invalid() -> None:
    """Validation failure must not corrupt the typed value field, so the
    tree stays serializable and undo cannot crash."""
    tree = build_form_tree(Schema)
    tree.set_value("name", "Alice")
    age_node = tree.root.find("age")
    assert age_node is not None
    initial_value = age_node.value
    result = tree.set_value("age", "not-a-number")
    assert result.ok is False
    # value untouched
    assert age_node.value == initial_value
    # error message recorded for renderer display
    assert age_node.error == "expected int, got str"


def test_undo_after_invalid_then_valid_does_not_crash() -> None:
    """Sequence: valid → invalid (no-op) → valid → undo. Must not raise."""
    tree = build_form_tree(Schema)
    tree.set_value("name", "Alice")          # snapshot pushed
    tree.set_value("age", "not-a-number")    # invalid → no snapshot
    tree.set_value("name", "Bob")            # snapshot pushed
    # Undo back to "Alice" — must not raise on snapshot replay.
    assert tree.undo() is True
    name_node = tree.root.find("name")
    assert name_node is not None
    assert name_node.value == "Alice"


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("at_least", 0, "must be >= 1"),
        ("at_most", 9, "must be <= 8"),
        ("above", 0, "must be > 0"),
        ("below", 10, "must be < 10"),
        ("even", 1, "must be a multiple of 2"),
    ],
)
def test_set_int_value_rejects_constraint_violations_without_mutating(
    path: str, value: int, message: str
) -> None:
    tree = build_form_tree(ConstrainedIntSchema)
    node = tree.root.find(path)
    assert node is not None
    assert node.value == 2

    result = tree.set_value(path, value)

    assert result.ok is False
    assert result.errors == (message,)
    assert node.value == 2
    assert node.error == message


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("at_least", 0.25, "must be >= 0.5"),
        ("at_most", 1.5, "must be <= 1.0"),
        ("above", 0.0, "must be > 0.0"),
        ("below", 1.0, "must be < 1.0"),
        ("quarter_step", 0.3, "must be a multiple of 0.25"),
    ],
)
def test_set_float_value_rejects_constraint_violations_without_mutating(
    path: str, value: float, message: str
) -> None:
    tree = build_form_tree(ConstrainedFloatSchema)
    node = tree.root.find(path)
    assert node is not None
    assert node.value == 0.5

    result = tree.set_value(path, value)

    assert result.ok is False
    assert result.errors == (message,)
    assert node.value == 0.5
    assert node.error == message


def test_set_float_value_rejects_nan_against_bounds_without_mutating() -> None:
    tree = build_form_tree(ConstrainedFloatSchema)
    node = tree.root.find("at_least")
    assert node is not None
    assert node.value == 0.5

    result = tree.set_value("at_least", math.nan)

    assert result.ok is False
    assert result.errors == ("must be >= 0.5",)
    assert node.value == 0.5
    assert node.error == "must be >= 0.5"


def test_float_field_propagates_allow_inf_nan_constraint() -> None:
    tree = build_form_tree(FiniteFloatSchema)
    node = tree.root.find("ratio")

    assert node is not None
    assert node.allow_inf_nan is False


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_set_float_value_rejects_non_finite_when_disallowed_without_mutating(
    value: float,
) -> None:
    tree = build_form_tree(FiniteFloatSchema)
    node = tree.root.find("ratio")
    assert node is not None
    assert node.value == 0.5

    result = tree.set_value("ratio", value)

    assert result.ok is False
    assert result.errors == ("must be finite",)
    assert node.value == 0.5
    assert node.error == "must be finite"


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("at_least", Decimal("0.99"), "must be >= 1.00"),
        ("at_most", Decimal("2.01"), "must be <= 2.00"),
        ("above", Decimal("0.00"), "must be > 0.00"),
        ("below", Decimal("2.00"), "must be < 2.00"),
        ("digit_limit", Decimal("123.45"), "must have no more than 4 digits"),
        ("cents", Decimal("1.001"), "must have no more than 2 decimal places"),
    ],
)
def test_set_decimal_value_rejects_constraint_violations_without_mutating(
    path: str, value: Decimal, message: str
) -> None:
    tree = build_form_tree(ConstrainedDecimalSchema)
    node = tree.root.find(path)
    assert node is not None
    assert node.value == Decimal("1.00")

    result = tree.set_value(path, value)

    assert result.ok is False
    assert result.errors == (message,)
    assert node.value == Decimal("1.00")
    assert node.error == message


def test_decimal_field_propagates_allow_inf_nan_constraint() -> None:
    tree = build_form_tree(FiniteDecimalSchema)
    node = tree.root.find("price")

    assert node is not None
    assert node.allow_inf_nan is False


def test_decimal_field_defaults_to_rejecting_non_finite_values() -> None:
    tree = build_form_tree(PlainDecimalSchema)
    node = tree.root.find("price")

    assert node is not None
    assert node.allow_inf_nan is False


@pytest.mark.parametrize(
    "value",
    [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")],
)
def test_set_decimal_value_rejects_non_finite_when_disallowed_without_mutating(
    value: Decimal,
) -> None:
    tree = build_form_tree(FiniteDecimalSchema)
    node = tree.root.find("price")
    assert node is not None
    assert node.value == Decimal("1.00")

    result = tree.set_value("price", value)

    assert result.ok is False
    assert result.errors == ("must be finite",)
    assert node.value == Decimal("1.00")
    assert node.error == "must be finite"


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ("at_least", "xy", "length must be >= 3"),
        ("at_most", "toolong", "length must be <= 5"),
        ("contains_marker", "ab", "must match pattern abc"),
    ],
)
def test_set_string_value_rejects_constraint_violations_without_mutating(
    path: str, value: str, message: str
) -> None:
    tree = build_form_tree(ConstrainedStringSchema)
    node = tree.root.find(path)
    assert node is not None
    expected_default = "abc" if path == "contains_marker" else "good"
    assert node.value == expected_default
    assert node.default == expected_default

    result = tree.set_value(path, value)

    assert result.ok is False
    assert result.errors == (message,)
    assert node.value == node.default
    assert node.error == message


def test_set_string_value_uses_pydantic_regex_engine_for_patterns() -> None:
    tree = build_form_tree(ConstrainedStringSchema)
    node = tree.root.find("unicode_letters")
    assert node is not None
    assert node.value == "abc"

    result = tree.set_value("unicode_letters", "123")

    assert result.ok is False
    assert result.errors == (r"must match pattern \p{L}+",)
    assert node.value == "abc"
    assert node.error == r"must match pattern \p{L}+"


def test_set_value_rejects_plain_validator_errors_without_mutating() -> None:
    tree = build_form_tree(PlainValidatorStringSchema)
    node = tree.root.find("token")
    assert node is not None
    assert node.value == "ok"

    result = tree.set_value("token", "bad")

    assert result.ok is False
    assert result.errors == ("Value error, bad blocked",)
    assert node.value == "ok"
    assert node.error == "Value error, bad blocked"
    assert tree.snapshots == []


def test_set_value_replaces_nested_group_fields_and_undoes() -> None:
    tree = build_form_tree(
        NestedProfileSchema,
        existing={"profile": {"host": "old.local", "port": 5432}},
    )

    result = tree.set_value("profile", {"host": "db.local", "port": 15432})

    assert result.ok is True
    assert tree.to_instance().profile == NestedProfile(host="db.local", port=15432)
    assert tree.undo() is True
    assert tree.to_instance().profile == NestedProfile(host="old.local", port=5432)


def test_set_value_rejects_invalid_nested_group_field_without_mutating() -> None:
    tree = build_form_tree(
        NestedProfileSchema,
        existing={"profile": {"host": "old.local", "port": 5432}},
    )

    result = tree.set_value("profile", {"host": "db.local", "port": 0})

    assert result.ok is False
    assert result.errors == ("port: must be >= 1",)
    assert tree.to_instance().profile == NestedProfile(host="old.local", port=5432)
    assert tree.snapshots == []
