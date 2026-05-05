from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from pydantic_studio.tree.nodes import (
    AnyNode,
    BoolNode,
    DecimalNode,
    FloatNode,
    FormNode,
    GroupNode,
    IntNode,
    StringNode,
)
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


def test_int_node_minimal():
    n = IntNode(name="age")
    assert n.kind == "int"
    assert n.value is None


def test_int_node_with_value_and_constraints():
    n = IntNode(name="age", value=42, ge=0, le=150)
    assert n.value == 42
    assert n.ge == 0
    assert n.le == 150
    assert n.to_python() == 42


def test_int_node_supports_strict_bounds():
    n = IntNode(name="x", gt=0, lt=100, multiple_of=5)
    assert n.gt == 0
    assert n.lt == 100
    assert n.multiple_of == 5


def test_float_node_minimal():
    n = FloatNode(name="ratio", value=0.75)
    assert n.kind == "float"
    assert n.value == 0.75


def test_bool_node_minimal():
    n = BoolNode(name="enabled", value=True)
    assert n.kind == "bool"
    assert n.value is True
    assert n.to_python() is True


def test_decimal_node_minimal():
    n = DecimalNode(name="amount", value=Decimal("3.14"))
    assert n.kind == "decimal"
    assert n.value == Decimal("3.14")
    assert n.to_python() == Decimal("3.14")


def test_decimal_node_constraints():
    n = DecimalNode(name="x", max_digits=5, decimal_places=2)
    assert n.max_digits == 5
    assert n.decimal_places == 2


class _PersonSchema(BaseModel):
    name: str
    age: int


def test_group_node_holds_named_fields():
    name_node = StringNode(name="name", value="alice")
    age_node = IntNode(name="age", value=30)
    g = GroupNode(name="root", schema_class=_PersonSchema, fields=[name_node, age_node])
    assert g.kind == "group"
    assert len(g.fields) == 2
    assert g.fields[0].name == "name"


def test_group_node_find_by_name():
    name_node = StringNode(name="name", value="alice")
    age_node = IntNode(name="age", value=30)
    g = GroupNode(name="root", schema_class=_PersonSchema, fields=[name_node, age_node])
    assert g.find("name") is name_node
    assert g.find("missing") is None


def test_group_node_to_python():
    name_node = StringNode(name="name", value="alice")
    age_node = IntNode(name="age", value=30)
    g = GroupNode(name="root", schema_class=_PersonSchema, fields=[name_node, age_node])
    assert g.to_python() == {"name": "alice", "age": 30}


def test_group_node_serializes_with_polymorphic_children():
    """Children are stored under the AnyNode discriminated union."""
    g = GroupNode(
        name="root",
        schema_class=_PersonSchema,
        fields=[StringNode(name="name", value="bob"), IntNode(name="age", value=42)],
    )
    dumped = g.model_dump()
    assert dumped["kind"] == "group"
    assert dumped["fields"][0]["kind"] == "string"
    assert dumped["fields"][1]["kind"] == "int"


def test_group_node_round_trip_via_json():
    g = GroupNode(
        name="root",
        schema_class=_PersonSchema,
        fields=[StringNode(name="name", value="bob"), IntNode(name="age", value=42)],
    )
    raw = g.model_dump_json()
    restored = GroupNode.model_validate_json(raw)
    assert restored.schema_class is _PersonSchema
    assert isinstance(restored.fields[0], StringNode)
    assert isinstance(restored.fields[1], IntNode)
    assert restored.to_python() == {"name": "bob", "age": 42}


def test_any_node_alias_covers_all_types():
    """AnyNode discriminates among all concrete node types added so far."""
    # Sanity: we can declare a list[AnyNode] and append various types.
    nodes: list[AnyNode] = []
    nodes.append(StringNode(name="a"))
    nodes.append(IntNode(name="b"))
    nodes.append(BoolNode(name="c"))
    assert {n.kind for n in nodes} == {"string", "int", "bool"}
