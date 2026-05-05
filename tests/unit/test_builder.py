from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic.fields import FieldInfo

from pydantic_studio.exceptions import NoBuilderError
from pydantic_studio.tree.builder import (
    BoolBuilder,
    DecimalBuilder,
    FloatBuilder,
    GroupBuilder,
    IntBuilder,
    NodeBuilder,
    Registry,
    StringBuilder,
    default_registry,
)
from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    FloatNode,
    GroupNode,
    IntNode,
    StringNode,
)
from tests.fixtures.schemas import Address, Person, Simple


def test_default_registry_is_non_empty():
    """The default registry should already have at least one builder
    (more added in subsequent tasks; for now we just check shape)."""
    assert isinstance(default_registry(), Registry)


def test_registry_no_match_raises_no_builder_error():
    """If no builder matches, the registry raises NoBuilderError(type)."""
    reg = Registry()  # empty
    with pytest.raises(NoBuilderError) as exc_info:
        reg.find(int)
    assert exc_info.value.type_ is int


def test_registry_register_prepends_builder():
    """Registering puts the new builder at the front (overrides earlier)."""

    class Always(NodeBuilder):
        def matches(self, type_: type) -> bool:
            return True

        def build(self, type_, field_info, existing):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    reg = Registry()
    a, b = Always(), Always()
    reg.register(a)
    reg.register(b)  # b prepended
    assert reg.find(int) is b


def _fi(default=None, **kw):
    """Helper: fabricate a FieldInfo with the given metadata."""
    return FieldInfo(default=default, **kw)


def test_string_builder_matches_str():
    b = StringBuilder()
    assert b.matches(str) is True
    assert b.matches(int) is False


def test_string_builder_builds_with_default():
    b = StringBuilder()
    fi = _fi(default="hi", description="a greeting")
    n = b.build(str, fi, existing=None)
    assert isinstance(n, StringNode)
    assert n.default == "hi"
    assert n.description == "a greeting"
    assert n.value is None  # nothing passed in `existing`


def test_string_builder_picks_existing_value_over_default():
    b = StringBuilder()
    fi = _fi(default="hi")
    n = b.build(str, fi, existing="bonjour")
    assert n.value == "bonjour"


def test_int_builder_matches_int_only():
    b = IntBuilder()
    assert b.matches(int) is True
    assert b.matches(bool) is False  # bool is a subclass of int but we don't want it


def test_int_builder_builds():
    b = IntBuilder()
    n = b.build(int, _fi(default=10), existing=None)
    assert isinstance(n, IntNode)
    assert n.default == 10


def test_float_builder_builds():
    b = FloatBuilder()
    assert b.matches(float)
    n = b.build(float, _fi(default=1.5), existing=None)
    assert isinstance(n, FloatNode)
    assert n.default == 1.5


def test_bool_builder_builds():
    b = BoolBuilder()
    assert b.matches(bool)
    n = b.build(bool, _fi(default=True), existing=None)
    assert isinstance(n, BoolNode)
    assert n.default is True


def test_decimal_builder_builds():
    b = DecimalBuilder()
    assert b.matches(Decimal)
    n = b.build(Decimal, _fi(default=Decimal("0.00")), existing=None)
    assert isinstance(n, DecimalNode)
    assert n.default == Decimal("0.00")


def test_string_builder_required_field_has_no_default():
    """A required field (no default) should produce a node with default=None,
    not PydanticUndefined sentinel leakage."""
    from pydantic_core import PydanticUndefined

    b = StringBuilder()
    fi = FieldInfo()  # no default → required
    n = b.build(str, fi, existing=None)
    assert n.default is None
    assert n.default is not PydanticUndefined  # ensure the sentinel was filtered
    assert n.required is True


def test_group_builder_matches_basemodel_subclasses():
    b = GroupBuilder(default_registry())
    assert b.matches(Address) is True
    assert b.matches(int) is False
    assert b.matches(str) is False


def test_group_builder_builds_simple_schema():
    b = GroupBuilder(default_registry())
    fi = FieldInfo(annotation=Simple)
    n = b.build(Simple, fi, existing=None)
    assert isinstance(n, GroupNode)
    assert n.schema_class is Simple
    field_names = [f.name for f in n.fields]
    assert field_names == ["name", "age", "height", "enabled", "balance"]


def test_group_builder_carries_field_info_into_children():
    b = GroupBuilder(default_registry())
    n = b.build(Simple, FieldInfo(annotation=Simple), existing=None)
    name_node = n.find("name")
    assert name_node is not None
    assert name_node.description == "The thing's name"


def test_group_builder_recursive_nested_model():
    b = GroupBuilder(default_registry())
    n = b.build(Person, FieldInfo(annotation=Person), existing=None)
    assert isinstance(n, GroupNode)
    addr_node = n.find("address")
    assert isinstance(addr_node, GroupNode)
    assert addr_node.schema_class is Address
    street = addr_node.find("street")
    assert street is not None
    assert street.kind == "string"


def test_group_builder_populates_existing_values():
    b = GroupBuilder(default_registry())
    existing = {"name": "alice", "age": 30}
    n = b.build(Simple, FieldInfo(annotation=Simple), existing=existing)
    assert n.find("name").value == "alice"
    assert n.find("age").value == 30
    # unspecified fields fall back to schema defaults
    assert n.find("enabled").value is None  # nothing passed
    assert n.find("enabled").default is True


def test_group_builder_recursive_existing_values():
    b = GroupBuilder(default_registry())
    existing = {"name": "alice", "address": {"street": "1 Main", "city": "Townsville"}}
    n = b.build(Person, FieldInfo(annotation=Person), existing=existing)
    addr = n.find("address")
    assert addr.find("street").value == "1 Main"
    assert addr.find("city").value == "Townsville"
