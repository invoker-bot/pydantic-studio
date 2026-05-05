"""EnumNode + EnumBuilder coverage."""

from __future__ import annotations

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import EnumNode
from tests.fixtures.schemas import Color, WithColor


def test_enum_field_builds_into_enum_node() -> None:
    tree = build_form_tree(WithColor)
    fav = tree.root.find("favorite")
    assert isinstance(fav, EnumNode)
    assert fav.choices == [
        ("RED", Color.RED),
        ("GREEN", Color.GREEN),
        ("BLUE", Color.BLUE),
    ]
    assert fav.default == Color.BLUE


def test_enum_to_python_returns_member() -> None:
    tree = build_form_tree(WithColor, existing={"favorite": Color.RED})
    fav = tree.root.find("favorite")
    assert isinstance(fav, EnumNode)
    assert fav.value == Color.RED
    assert fav.to_python() == Color.RED


def test_enum_to_instance_round_trips() -> None:
    tree = build_form_tree(WithColor, existing={"favorite": Color.GREEN})
    instance = tree.to_instance()
    assert instance.favorite == Color.GREEN


def test_enum_validate_value_rejects_non_member() -> None:
    tree = build_form_tree(WithColor)
    result = tree.set_value("favorite", "not-a-color")
    assert result.ok is False
    assert any("not a Color member" in e for e in result.errors)


def test_enum_validate_value_accepts_member() -> None:
    tree = build_form_tree(WithColor)
    result = tree.set_value("favorite", Color.RED)
    assert result.ok is True
