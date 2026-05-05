from __future__ import annotations

from pydantic_studio.tree.nodes import FormNode
from pydantic_studio.tree.validation import ValidationResult


def test_validation_result_ok_factory():
    res = ValidationResult.ok()
    assert res.ok is True
    assert res.errors == []


def test_validation_result_failure_factory():
    res = ValidationResult.fail(["name: required"])
    assert res.ok is False
    assert res.errors == ["name: required"]


def test_validation_result_is_truthy_when_ok():
    """Convenient: `if result: ...` works."""
    assert bool(ValidationResult.ok()) is True
    assert bool(ValidationResult.fail(["x"])) is False


def test_form_node_has_required_attrs():
    """FormNode is the abstract base; concrete subclasses come later."""
    # Constructing FormNode directly via subclass-without-extras for the test:
    class _Bare(FormNode):
        kind: str = "_bare"

    n = _Bare(name="x")
    assert n.name == "x"
    assert n.description is None
    assert n.required is True
    assert n.error is None


def test_form_node_with_description():
    class _Bare(FormNode):
        kind: str = "_bare"

    n = _Bare(name="x", description="**hello**", required=False)
    assert n.description == "**hello**"
    assert n.required is False
