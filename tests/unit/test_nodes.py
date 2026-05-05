from __future__ import annotations

from pydantic_studio.tree.nodes import FormNode, StringNode
from pydantic_studio.tree.validation import ValidationResult


def test_validation_result_ok_factory():
    res = ValidationResult.ok()
    assert res.ok is True
    assert res.errors == ()


def test_validation_result_failure_factory():
    res = ValidationResult.fail(["name: required"])
    assert res.ok is False
    assert res.errors == ("name: required",)


def test_validation_result_is_truthy_when_ok():
    """Convenient: `if result: ...` works."""
    assert bool(ValidationResult.ok()) is True
    assert bool(ValidationResult.fail(["x"])) is False


def test_validation_result_success_alias_matches_ok():
    """``ok()`` is an alias for ``success()``."""
    assert ValidationResult.success() == ValidationResult.ok()


def test_form_node_to_python_raises_not_implemented():
    """Subclasses must override ``to_python``; the base raises NotImplementedError."""
    import pytest

    class _Bare(FormNode):
        kind: str = "_bare"

    with pytest.raises(NotImplementedError, match=r"_Bare\.to_python is not implemented"):
        _Bare(name="x").to_python()


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


def test_string_node_minimal():
    n = StringNode(name="title")
    assert n.kind == "string"
    assert n.value is None
    assert n.default is None
    assert n.error is None
    assert n.multiline is False
    assert n.secret is False


def test_string_node_set_value():
    n = StringNode(name="title", value="hello")
    assert n.value == "hello"
    assert n.to_python() == "hello"


def test_string_node_with_constraints():
    n = StringNode(name="code", min_length=3, max_length=8, pattern=r"^[A-Z]+$")
    assert n.min_length == 3
    assert n.max_length == 8
    assert n.pattern == "^[A-Z]+$"


def test_string_node_default_falls_back_to_value():
    n = StringNode(name="title", default="untitled")
    assert n.default == "untitled"
    assert n.value is None  # default is separate from current value


def test_string_node_secret_flag():
    n = StringNode(name="password", secret=True)
    assert n.secret is True


def test_string_node_serializes_with_kind_discriminator():
    n = StringNode(name="x", value="y")
    dumped = n.model_dump()
    assert dumped["kind"] == "string"
    restored = StringNode.model_validate(dumped)
    assert restored.value == "y"
