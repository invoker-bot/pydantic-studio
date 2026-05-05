"""LiteralNode + LiteralBuilder coverage."""

from __future__ import annotations

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import LiteralNode
from tests.fixtures.schemas import WithLogLevel


def test_literal_string_field_builds_into_literal_node() -> None:
    tree = build_form_tree(WithLogLevel)
    level = tree.root.find("level")
    assert isinstance(level, LiteralNode)
    assert level.choices == ["debug", "info", "warn", "error"]
    assert level.default == "info"


def test_literal_int_field() -> None:
    tree = build_form_tree(WithLogLevel)
    sev = tree.root.find("severity")
    assert isinstance(sev, LiteralNode)
    assert sev.choices == [1, 2, 3]
    assert sev.default == 2


def test_literal_to_instance_round_trip() -> None:
    tree = build_form_tree(WithLogLevel, existing={"level": "warn"})
    instance = tree.to_instance()
    assert instance.level == "warn"


def test_literal_validate_rejects_unlisted_value() -> None:
    tree = build_form_tree(WithLogLevel)
    result = tree.set_value("level", "trace")
    assert result.ok is False
    assert any("not in choices" in e for e in result.errors)


def test_literal_validate_accepts_listed_value() -> None:
    tree = build_form_tree(WithLogLevel)
    result = tree.set_value("level", "error")
    assert result.ok is True
