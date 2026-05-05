"""set_value contract: returns ValidationResult after node-local validation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.tree.validation import ValidationResult


class Schema(BaseModel):
    name: str = Field(min_length=3)
    age: int = Field(ge=0)


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
