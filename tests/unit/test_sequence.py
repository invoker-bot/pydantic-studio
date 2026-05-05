"""SequenceNode shape and discriminator round-trip."""

from __future__ import annotations

from typing import cast

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import GroupNode, IntNode, SequenceNode, StringNode
from tests.fixtures.schemas import WithFixedTuple, WithList, WithSet, WithTuple


def test_sequence_node_construct() -> None:
    node = SequenceNode(
        name="tags",
        origin="list",
        items=[StringNode(name="0", value="a"), StringNode(name="1", value="b")],
        item_type_name="builtins.str",
    )
    assert node.kind == "sequence"
    assert node.origin == "list"
    assert len(node.items) == 2


def test_sequence_node_round_trips_through_group() -> None:
    """A SequenceNode embedded in a GroupNode must serialize and rehydrate
    without losing its kind discriminator."""
    seq = SequenceNode(
        name="tags",
        origin="list",
        items=[StringNode(name="0", value="a")],
        item_type_name="builtins.str",
    )
    group = GroupNode.model_construct(
        name="root",
        kind="group",
        schema_class=__import__("pydantic").BaseModel,
        fields=[seq],
    )
    raw = group.model_dump_json()
    rehydrated = GroupNode.model_validate_json(raw)
    inner = rehydrated.fields[0]
    assert isinstance(inner, SequenceNode)
    assert inner.origin == "list"
    assert inner.items[0].value == "a"


def test_sequence_to_python_returns_list_of_item_values() -> None:
    seq = SequenceNode(
        name="tags",
        origin="list",
        items=[StringNode(name="0", value="a"), StringNode(name="1", value="b")],
        item_type_name="builtins.str",
    )
    assert seq.to_python() == ["a", "b"]


def test_sequence_to_python_for_set_origin_returns_set() -> None:
    seq = SequenceNode(
        name="tags",
        origin="set",
        items=[StringNode(name="0", value="a"), StringNode(name="1", value="b")],
        item_type_name="builtins.str",
    )
    assert seq.to_python() == {"a", "b"}


def test_sequence_to_python_for_tuple_origin_returns_tuple() -> None:
    seq = SequenceNode(
        name="tags",
        origin="tuple",
        items=[StringNode(name="0", value="a")],
        item_type_name="builtins.str",
    )
    assert seq.to_python() == ("a",)


def test_list_builder_constructs_sequence_node() -> None:
    tree = build_form_tree(WithList)
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert tags.origin == "list"
    assert tags.item_type_name == "builtins.str"
    assert tags.items == []


def test_list_builder_pre_populates_from_existing() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["a", "b", "c"]})
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert len(tags.items) == 3
    assert all(isinstance(it, StringNode) for it in tags.items)
    str_items = [cast("StringNode", it) for it in tags.items]
    assert [it.value for it in str_items] == ["a", "b", "c"]


def test_list_of_int_dispatches_through_int_builder() -> None:
    tree = build_form_tree(WithList, existing={"counts": [1, 2, 3]})
    counts = tree.root.find("counts")
    assert isinstance(counts, SequenceNode)
    assert all(isinstance(it, IntNode) for it in counts.items)
    int_items = [cast("IntNode", it) for it in counts.items]
    assert [it.value for it in int_items] == [1, 2, 3]


def test_set_builder_constructs_sequence_node_origin_set() -> None:
    tree = build_form_tree(WithSet, existing={"flags": {"a", "b"}})
    flags = tree.root.find("flags")
    assert isinstance(flags, SequenceNode)
    assert flags.origin == "set"
    str_items = [cast("StringNode", it) for it in flags.items]
    assert {it.value for it in str_items} == {"a", "b"}


def test_list_to_instance_round_trip() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["x", "y"]})
    instance = tree.to_instance()
    assert instance.tags == ["x", "y"]


def test_set_to_instance_round_trip() -> None:
    tree = build_form_tree(WithSet, existing={"flags": {"x", "y"}})
    instance = tree.to_instance()
    assert instance.flags == {"x", "y"}


def test_variadic_tuple_uses_origin_tuple() -> None:
    tree = build_form_tree(WithTuple, existing={"coords": (1, 2, 3)})
    coords = tree.root.find("coords")
    assert isinstance(coords, SequenceNode)
    assert coords.origin == "tuple"
    assert [cast("IntNode", it).value for it in coords.items] == [1, 2, 3]


def test_fixed_tuple_uses_origin_tuple_fixed() -> None:
    tree = build_form_tree(WithFixedTuple, existing={"rgb": (10, 20, 30)})
    rgb = tree.root.find("rgb")
    assert isinstance(rgb, SequenceNode)
    assert rgb.origin == "tuple_fixed"
    assert rgb.slot_type_names == ["builtins.int", "builtins.int", "builtins.int"]
    assert [cast("IntNode", it).value for it in rgb.items] == [10, 20, 30]


def test_fixed_tuple_heterogeneous_slot_types() -> None:
    tree = build_form_tree(WithFixedTuple, existing={"pair": ("hello", 7)})
    pair = tree.root.find("pair")
    assert isinstance(pair, SequenceNode)
    assert pair.origin == "tuple_fixed"
    assert pair.slot_type_names == ["builtins.str", "builtins.int"]
    assert cast("StringNode", pair.items[0]).value == "hello"
    assert cast("IntNode", pair.items[1]).value == 7


def test_fixed_tuple_to_instance_round_trip() -> None:
    tree = build_form_tree(WithFixedTuple, existing={"rgb": (1, 2, 3)})
    instance = tree.to_instance()
    assert instance.rgb == (1, 2, 3)
