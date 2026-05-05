"""SequenceNode shape and discriminator round-trip."""

from __future__ import annotations

from pydantic_studio.tree.nodes import GroupNode, SequenceNode, StringNode


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
