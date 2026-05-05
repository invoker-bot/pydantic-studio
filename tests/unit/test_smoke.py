"""Smoke test covering the full Phase 2 type matrix in one schema."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal, cast

from annotated_types import Ge
from pydantic import BaseModel, Field

from pydantic_studio import (
    EnumNode,
    GroupNode,
    IntNode,
    LiteralNode,
    MappingNode,
    SequenceNode,
    StringNode,
    UnionNode,
    build_form_tree,
)


class Tier(Enum):
    BASIC = "basic"
    PRO = "pro"


class Sub(BaseModel):
    label: str
    weight: Decimal = Decimal("1.00")


class Kitchen(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    age: Annotated[int, Ge(0)] = 0
    tier: Tier = Tier.BASIC
    log_level: Literal["debug", "info", "warn"] = "info"
    tags: list[str] = []
    flags: set[str] = set()
    coords: tuple[int, int] = (0, 0)
    settings: dict[str, int] = {}
    sub: Sub = Sub(label="default")
    primary: int | str = 0
    nickname: str | None = None


def test_kitchen_schema_builds_with_correct_node_types() -> None:
    tree = build_form_tree(Kitchen)
    assert isinstance(tree.root.find("name"), StringNode)
    assert isinstance(tree.root.find("age"), IntNode)
    assert isinstance(tree.root.find("tier"), EnumNode)
    assert isinstance(tree.root.find("log_level"), LiteralNode)
    assert isinstance(tree.root.find("tags"), SequenceNode)
    assert isinstance(tree.root.find("flags"), SequenceNode)
    assert isinstance(tree.root.find("coords"), SequenceNode)
    assert isinstance(tree.root.find("settings"), MappingNode)
    assert isinstance(tree.root.find("sub"), GroupNode)
    assert isinstance(tree.root.find("primary"), UnionNode)
    # Optional[str] demotes to StringNode with required=False.
    nick = tree.root.find("nickname")
    assert isinstance(nick, StringNode)
    assert nick.required is False


def test_kitchen_constraint_passes_through_to_nodes() -> None:
    tree = build_form_tree(Kitchen)
    name = cast("StringNode", tree.root.find("name"))
    assert name.min_length == 1
    assert name.max_length == 50
    age = cast("IntNode", tree.root.find("age"))
    assert age.ge == 0


def test_kitchen_round_trip_to_instance() -> None:
    tree = build_form_tree(
        Kitchen,
        existing={
            "name": "alice",
            "age": 30,
            "tier": Tier.PRO,
            "log_level": "warn",
            "tags": ["x", "y"],
            "flags": {"a"},
            "coords": (1, 2),
            "settings": {"k": 1},
            "sub": {"label": "L"},
            "primary": "hello",
            "nickname": "ali",
        },
    )
    instance = cast("Kitchen", tree.to_instance())
    assert instance.name == "alice"
    assert instance.age == 30
    assert instance.tier == Tier.PRO
    assert instance.log_level == "warn"
    assert instance.tags == ["x", "y"]
    assert instance.flags == {"a"}
    assert instance.coords == (1, 2)
    assert instance.settings == {"k": 1}
    assert instance.sub.label == "L"
    assert instance.primary == "hello"
    assert instance.nickname == "ali"


def test_kitchen_mutation_smoke() -> None:
    """Each major mutation runs and round-trips under undo/redo."""
    tree = build_form_tree(Kitchen)
    tree.set_value("name", "bob")
    tree.set_value("sub.label", "default")  # satisfy required nested field
    tree.add_item("tags", "first")
    tree.add_entry("settings", "k", 42)
    tree.select_variant("primary", 1, seed="from-union")
    instance = cast("Kitchen", tree.to_instance())
    assert instance.name == "bob"
    assert instance.tags == ["first"]
    assert instance.settings == {"k": 42}
    assert instance.primary == "from-union"
    # Walk all five mutations back.
    for _ in range(5):
        assert tree.undo() is True
