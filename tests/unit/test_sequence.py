"""SequenceNode shape and discriminator round-trip."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import GroupNode, IntNode, SequenceNode, StringNode
from tests.fixtures.schemas import WithFixedTuple, WithList, WithSet, WithTuple


class ConstrainedList(BaseModel):
    tags: list[str] = Field(default_factory=lambda: ["a"], min_length=1, max_length=2)


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


def test_fixed_tuple_to_python_returns_none_when_all_slots_none() -> None:
    """All-None tuple_fixed must return None so the parent group filters
    the key — letting Pydantic apply the schema default for the field."""
    seq = SequenceNode(
        name="rgb",
        origin="tuple_fixed",
        items=[
            IntNode(name="0", value=None),
            IntNode(name="1", value=None),
            IntNode(name="2", value=None),
        ],
        slot_type_names=["builtins.int", "builtins.int", "builtins.int"],
    )
    assert seq.to_python() is None


def test_fixed_tuple_no_existing_uses_schema_default() -> None:
    """When existing data is omitted, the default tuple from the schema
    flows through to the materialized instance."""
    tree = build_form_tree(WithFixedTuple)
    instance = tree.to_instance()
    assert instance.rgb == (0, 0, 0)
    assert instance.pair == ("k", 0)


def test_add_item_appends_default_child() -> None:
    tree = build_form_tree(WithList)
    result = tree.add_item("tags")
    assert result.ok is True
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert len(tags.items) == 1
    assert isinstance(tags.items[0], StringNode)
    assert tags.items[0].name == "0"


def test_add_item_with_explicit_value() -> None:
    tree = build_form_tree(WithList)
    tree.add_item("tags", "hello")
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert cast("StringNode", tags.items[0]).value == "hello"


def test_add_item_rejects_invalid_typed_value_without_mutating() -> None:
    tree = build_form_tree(WithList)

    result = tree.add_item("counts", "not-an-int")

    assert result.ok is False
    assert any("expected int" in error for error in result.errors)
    counts = tree.root.find("counts")
    assert isinstance(counts, SequenceNode)
    assert counts.items == []
    assert tree.snapshots == []


def test_add_item_rejects_explicit_none_without_mutating() -> None:
    tree = build_form_tree(WithList)

    result = tree.add_item("counts", None)

    assert result.ok is False
    assert result.errors == ("value is required",)
    counts = tree.root.find("counts")
    assert isinstance(counts, SequenceNode)
    assert counts.items == []
    assert tree.snapshots == []


def test_remove_item_renumbers() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["a", "b", "c"]})
    tree.remove_item("tags", 1)
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    str_items = [cast("StringNode", it) for it in tags.items]
    assert [it.value for it in str_items] == ["a", "c"]
    assert [it.name for it in tags.items] == ["0", "1"]


def test_insert_item_at_index() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["a", "c"]})
    tree.insert_item("tags", 1, "b")
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    str_items = [cast("StringNode", it) for it in tags.items]
    assert [it.value for it in str_items] == ["a", "b", "c"]


def test_insert_item_rejects_invalid_typed_value_without_mutating() -> None:
    tree = build_form_tree(WithList, existing={"counts": [1, 3]})

    result = tree.insert_item("counts", 1, "not-an-int")

    assert result.ok is False
    assert any("expected int" in error for error in result.errors)
    counts = tree.root.find("counts")
    assert isinstance(counts, SequenceNode)
    int_items = [cast("IntNode", item) for item in counts.items]
    assert [item.value for item in int_items] == [1, 3]
    assert [item.name for item in counts.items] == ["0", "1"]
    assert tree.snapshots == []


def test_insert_item_rejects_explicit_none_without_mutating() -> None:
    tree = build_form_tree(WithList, existing={"counts": [1, 3]})

    result = tree.insert_item("counts", 1, None)

    assert result.ok is False
    assert result.errors == ("value is required",)
    counts = tree.root.find("counts")
    assert isinstance(counts, SequenceNode)
    int_items = [cast("IntNode", item) for item in counts.items]
    assert [item.value for item in int_items] == [1, 3]
    assert [item.name for item in counts.items] == ["0", "1"]
    assert tree.snapshots == []


def test_move_item_reorders() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["a", "b", "c"]})
    tree.move_item("tags", 0, 2)
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    str_items = [cast("StringNode", it) for it in tags.items]
    assert [it.value for it in str_items] == ["b", "c", "a"]


def test_add_item_pushes_snapshot_so_undo_works() -> None:
    tree = build_form_tree(WithList)
    tree.add_item("tags", "x")
    assert tree.undo() is True
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert tags.items == []


def test_add_item_fails_on_fixed_tuple() -> None:
    tree = build_form_tree(WithFixedTuple)
    result = tree.add_item("rgb")
    assert result.ok is False
    assert any("fixed-length" in e for e in result.errors)


def test_add_item_rejects_sequence_max_length_without_mutating() -> None:
    tree = build_form_tree(ConstrainedList, existing={"tags": ["a", "b"]})
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)

    result = tree.add_item("tags", "c")

    assert result.ok is False
    assert result.errors == ("length must be <= 2",)
    assert [cast("StringNode", item).value for item in tags.items] == ["a", "b"]
    assert tree.snapshots == []


def test_insert_item_rejects_sequence_max_length_without_mutating() -> None:
    tree = build_form_tree(ConstrainedList, existing={"tags": ["a", "b"]})
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)

    result = tree.insert_item("tags", 1, "c")

    assert result.ok is False
    assert result.errors == ("length must be <= 2",)
    assert [cast("StringNode", item).value for item in tags.items] == ["a", "b"]
    assert [item.name for item in tags.items] == ["0", "1"]
    assert tree.snapshots == []


def test_remove_item_rejects_sequence_min_length_without_mutating() -> None:
    tree = build_form_tree(ConstrainedList, existing={"tags": ["a"]})
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)

    result = tree.remove_item("tags", 0)

    assert result.ok is False
    assert result.errors == ("length must be >= 1",)
    assert [cast("StringNode", item).value for item in tags.items] == ["a"]
    assert tree.snapshots == []


def test_set_value_replaces_sequence_items_and_undoes() -> None:
    tree = build_form_tree(WithList, existing={"tags": ["old"]})
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)

    result = tree.set_value("tags", ["red", "blue"])

    assert result.ok is True
    assert [cast("StringNode", item).value for item in tags.items] == ["red", "blue"]
    assert [item.name for item in tags.items] == ["0", "1"]
    assert tree.undo() is True
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)
    assert [cast("StringNode", item).value for item in tags.items] == ["old"]


def test_set_value_rejects_invalid_sequence_item_without_mutating() -> None:
    tree = build_form_tree(WithList, existing={"counts": [1, 2]})
    counts = tree.root.find("counts")
    assert isinstance(counts, SequenceNode)

    result = tree.set_value("counts", ["not-an-int"])

    assert result.ok is False
    assert result.errors == ("[0]: expected int, got str",)
    assert [cast("IntNode", item).value for item in counts.items] == [1, 2]
    assert [item.name for item in counts.items] == ["0", "1"]
    assert tree.snapshots == []


def test_set_value_rejects_sequence_length_without_mutating() -> None:
    tree = build_form_tree(ConstrainedList, existing={"tags": ["a"]})
    tags = tree.root.find("tags")
    assert isinstance(tags, SequenceNode)

    result = tree.set_value("tags", [])

    assert result.ok is False
    assert result.errors == ("length must be >= 1",)
    assert [cast("StringNode", item).value for item in tags.items] == ["a"]
    assert tree.snapshots == []


def test_set_value_replaces_fixed_tuple_items() -> None:
    tree = build_form_tree(WithFixedTuple)
    rgb = tree.root.find("rgb")
    assert isinstance(rgb, SequenceNode)

    result = tree.set_value("rgb", (10, 20, 30))

    assert result.ok is True
    assert [cast("IntNode", item).value for item in rgb.items] == [10, 20, 30]
    assert [item.name for item in rgb.items] == ["0", "1", "2"]
    assert tree.to_instance().rgb == (10, 20, 30)
