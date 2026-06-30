"""MappingNode + DictBuilder + entry mutations."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import IntNode, MappingNode, StringNode
from tests.fixtures.schemas import WithDict


class WithIntDict(BaseModel):
    ports: dict[int, str] = Field(default_factory=dict)


class WithPathDict(BaseModel):
    paths: dict[Path, int] = Field(default_factory=dict)


class ConstrainedDict(BaseModel):
    settings: dict[str, int] = Field(
        default_factory=lambda: {"a": 1}, min_length=1, max_length=2
    )


def test_dict_builder_constructs_mapping_node() -> None:
    tree = build_form_tree(WithDict)
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert settings.key_type_name == "builtins.str"
    assert settings.value_type_name == "builtins.int"
    assert settings.entries == []


def test_dict_pre_populates_from_existing() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"timeout": 30, "retries": 3}}
    )
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert len(settings.entries) == 2
    assert all(isinstance(k, StringNode) for k, _ in settings.entries)
    assert all(isinstance(v, IntNode) for _, v in settings.entries)
    assert {(k.value, v.value) for k, v in settings.entries} == {
        ("timeout", 30),
        ("retries", 3),
    }


def test_dict_to_python_returns_dict() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"timeout": 30}}
    )
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert settings.to_python() == {"timeout": 30}


def test_dict_to_instance_round_trip() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"a": 1, "b": 2}}
    )
    instance = tree.to_instance()
    assert instance.settings == {"a": 1, "b": 2}


def test_add_entry_appends() -> None:
    tree = build_form_tree(WithDict)
    result = tree.add_entry("settings", "timeout", 30)
    assert result.ok is True
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert len(settings.entries) == 1
    k, v = settings.entries[0]
    assert k.value == "timeout"
    assert v.value == 30


def test_add_entry_rejects_invalid_typed_key_without_mutating() -> None:
    tree = build_form_tree(WithIntDict)

    result = tree.add_entry("ports", "not-an-int", "http")

    assert result.ok is False
    assert any("expected int" in error for error in result.errors)
    ports = tree.root.find("ports")
    assert isinstance(ports, MappingNode)
    assert ports.entries == []
    assert tree.snapshots == []


def test_add_entry_rejects_invalid_typed_value_without_mutating() -> None:
    tree = build_form_tree(WithDict)

    result = tree.add_entry("settings", "timeout", "not-an-int")

    assert result.ok is False
    assert any("expected int" in error for error in result.errors)
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert settings.entries == []
    assert tree.snapshots == []


def test_remove_entry() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"a": 1, "b": 2, "c": 3}}
    )
    tree.remove_entry("settings", 1)
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert {(k.value, v.value) for k, v in settings.entries} == {
        ("a", 1),
        ("c", 3),
    }


def test_rename_key() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"old": 1}}
    )
    tree.rename_key("settings", 0, "new")
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    k, v = settings.entries[0]
    assert k.value == "new"
    assert v.value == 1


def test_add_entry_pushes_snapshot_for_undo() -> None:
    tree = build_form_tree(WithDict)
    tree.add_entry("settings", "k", 1)
    assert tree.undo() is True
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert settings.entries == []


def test_add_entry_rejects_mapping_max_length_without_mutating() -> None:
    tree = build_form_tree(ConstrainedDict, existing={"settings": {"a": 1, "b": 2}})
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)

    result = tree.add_entry("settings", "c", 3)

    assert result.ok is False
    assert result.errors == ("length must be <= 2",)
    assert settings.to_python() == {"a": 1, "b": 2}
    assert tree.snapshots == []


def test_add_entry_rejects_duplicate_key_without_mutating() -> None:
    tree = build_form_tree(WithDict, existing={"settings": {"a": 1}})
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)

    result = tree.add_entry("settings", "a", 2)

    assert result.ok is False
    assert result.errors == ("duplicate key 'a'",)
    assert settings.to_python() == {"a": 1}
    assert tree.snapshots == []


def test_remove_entry_rejects_mapping_min_length_without_mutating() -> None:
    tree = build_form_tree(ConstrainedDict, existing={"settings": {"a": 1}})
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)

    result = tree.remove_entry("settings", 0)

    assert result.ok is False
    assert result.errors == ("length must be >= 1",)
    assert settings.to_python() == {"a": 1}
    assert tree.snapshots == []


def test_rename_key_rejects_duplicate_key_without_mutating() -> None:
    tree = build_form_tree(WithDict, existing={"settings": {"a": 1, "b": 2}})
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)

    result = tree.rename_key("settings", 1, "a")

    assert result.ok is False
    assert result.errors == ("duplicate key 'a'",)
    assert settings.to_python() == {"a": 1, "b": 2}
    assert tree.snapshots == []


def test_rename_key_rejects_normalized_duplicate_key_without_mutating() -> None:
    tree = build_form_tree(
        WithPathDict,
        existing={"paths": {Path("existing.yaml"): 1, Path("other.yaml"): 2}},
    )
    paths = tree.root.find("paths")
    assert isinstance(paths, MappingNode)

    result = tree.rename_key("paths", 1, "existing.yaml")

    assert result.ok is False
    assert result.errors == ("duplicate key PosixPath('existing.yaml')",)
    assert paths.to_python() == {
        Path("existing.yaml"): 1,
        Path("other.yaml"): 2,
    }
    assert tree.snapshots == []
