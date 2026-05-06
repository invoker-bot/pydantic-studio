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


class TestPhase3Sink:
    """End-to-end smoke for the 13 new Plan 3 type families."""

    def test_build_succeeds_for_all_phase3_types(self) -> None:
        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import Phase3Sink

        tree = build_form_tree(Phase3Sink)
        # Confirm all 14 fields rendered as nodes.
        assert len(tree.root.fields) == 14

    def test_to_instance_round_trip_with_defaults(self) -> None:
        from datetime import date, datetime, time, timedelta
        from ipaddress import IPv4Address, IPv6Network
        from pathlib import Path
        from uuid import UUID

        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import Phase3Sink

        tree = build_form_tree(Phase3Sink)
        instance = tree.to_instance()
        assert instance.when == datetime(2026, 5, 6, 12, 0)
        assert instance.on == date(2026, 5, 6)
        assert instance.at == time(9, 30)
        assert instance.interval == timedelta(seconds=30)
        assert instance.bind == IPv4Address("127.0.0.1")
        assert instance.allow == IPv6Network("fe80::/64")
        assert "api.example.com" in str(instance.api)
        assert instance.contact == "ops@example.com"
        assert instance.home == Path("/home/user")
        assert instance.request_id == UUID(int=0)
        assert instance.api_key.get_secret_value() == "default-key"
        assert instance.token.get_secret_value() == b"default-token"
        assert instance.name_re.pattern == r"^[a-z]+$"
        assert instance.blob == b"\x00\x01\x02"

    def test_set_value_each_field(self) -> None:
        """One set_value per node type — proves the validate-first contract
        works for every new node."""
        from datetime import date, datetime, time, timedelta
        from ipaddress import IPv4Address
        from uuid import uuid4

        from pydantic_studio import build_form_tree
        from tests.fixtures.schemas import Phase3Sink

        tree = build_form_tree(Phase3Sink)
        new_uuid = uuid4()
        mutations = [
            ("when", datetime(2027, 1, 1, 12, 0)),
            ("on", date(2027, 1, 1)),
            ("at", time(15, 45)),
            ("interval", timedelta(minutes=10)),
            ("bind", "192.168.1.1"),
            ("allow", "2001:db8::/32"),
            ("api", "https://newapi.example.com"),
            ("contact", "new@example.com"),
            ("home", "/srv/data"),
            ("request_id", new_uuid),
            ("api_key", "new-secret"),
            ("token", b"new-token"),
            ("name_re", r"^[A-Z]+$"),
            ("blob", b"\xff\xfe"),
        ]
        for path, value in mutations:
            result = tree.set_value(path, value)
            assert result.ok, f"set_value({path!r}, {value!r}) failed: {result.errors}"

        instance = tree.to_instance()
        assert instance.when == datetime(2027, 1, 1, 12, 0)
        assert instance.bind == IPv4Address("192.168.1.1")
        assert instance.contact == "new@example.com"
        assert instance.api_key.get_secret_value() == "new-secret"
        assert instance.token.get_secret_value() == b"new-token"

    def test_snapshot_round_trip(self) -> None:
        """Full FormTree.model_dump_json + model_validate_json round-trip
        must preserve every node type."""
        from pydantic_studio import build_form_tree
        from pydantic_studio.tree.nodes import FormTree
        from tests.fixtures.schemas import Phase3Sink

        tree = build_form_tree(Phase3Sink)
        raw = tree.model_dump_json(exclude={"schema_class"})
        restored = FormTree.model_validate_json(
            raw, context={"schema_class": Phase3Sink}
        )
        # The restored tree must be able to materialize the same instance.
        original_instance = tree.to_instance()
        restored_instance = restored.to_instance()
        assert original_instance == restored_instance
