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
    assert len(result.errors) >= 1


def test_set_value_still_pushes_snapshot_on_invalid() -> None:
    """Even when validation fails, the mutation is applied and a snapshot
    is pushed — undo() should be able to revert the bad value."""
    tree = build_form_tree(Schema)
    tree.set_value("name", "Alice")  # valid baseline
    tree.set_value("age", "not-a-number")  # invalid
    assert tree.undo() is True
    age_node = tree.root.find("age")
    assert age_node is not None
    assert age_node.value != "not-a-number"
