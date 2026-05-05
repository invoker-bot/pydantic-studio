"""UnionNode + UnionBuilder coverage. select_variant lives in T15."""

from __future__ import annotations

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import IntNode, StringNode, UnionNode
from tests.fixtures.schemas import WithOptional, WithUnion


def test_optional_demotes_to_inner_type_node() -> None:
    """``str | None`` becomes a StringNode with required=False, NOT a UnionNode."""
    tree = build_form_tree(WithOptional)
    nick = tree.root.find("nickname")
    assert isinstance(nick, StringNode)
    assert nick.required is False
    age = tree.root.find("age")
    assert isinstance(age, IntNode)
    assert age.required is False


def test_true_union_becomes_union_node() -> None:
    tree = build_form_tree(WithUnion)
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.variant_type_names == ["builtins.int", "builtins.str"]


def test_union_pre_populated_from_existing_int() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 42})
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 0
    assert isinstance(val.selected, IntNode)
    assert val.selected.value == 42


def test_union_pre_populated_from_existing_str() -> None:
    tree = build_form_tree(WithUnion, existing={"value": "hi"})
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 1
    assert isinstance(val.selected, StringNode)
    assert val.selected.value == "hi"


def test_union_to_python_returns_inner_value() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 7})
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.to_python() == 7


def test_union_to_instance_round_trip() -> None:
    tree = build_form_tree(WithUnion, existing={"value": "hello"})
    instance = tree.to_instance()
    assert instance.value == "hello"


def test_select_variant_switches_to_str() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 42})
    result = tree.select_variant("value", 1)  # switch to str
    assert result.ok is True
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 1
    assert isinstance(val.selected, StringNode)
    assert val.selected.value is None  # fresh; previous int 42 is discarded


def test_select_variant_undo_restores() -> None:
    tree = build_form_tree(WithUnion, existing={"value": 42})
    tree.select_variant("value", 1)
    assert tree.undo() is True
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected_index == 0
    assert isinstance(val.selected, IntNode)
    assert val.selected.value == 42


def test_select_variant_out_of_range_returns_error() -> None:
    tree = build_form_tree(WithUnion)
    result = tree.select_variant("value", 99)
    assert result.ok is False
    assert any("out of range" in e for e in result.errors)


def test_select_variant_with_seed_value() -> None:
    """Optional second arg lets caller seed the new variant's value."""
    tree = build_form_tree(WithUnion)
    result = tree.select_variant("value", 1, seed="seeded")
    assert result.ok is True
    val = tree.root.find("value")
    assert isinstance(val, UnionNode)
    assert val.selected.value == "seeded"
