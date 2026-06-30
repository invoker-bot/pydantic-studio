"""set_value contract: returns ValidationResult after node-local validation."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

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


class ConstrainedStringSchema(BaseModel):
    at_least: str = Field(default="good", min_length=3)
    at_most: str = Field(default="good", max_length=5)
    contains_marker: str = Field(default="abc", pattern="abc")
    unicode_letters: str = Field(default="abc", pattern=r"\p{L}+")


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
