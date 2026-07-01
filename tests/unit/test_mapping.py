"""MappingNode + DictBuilder + entry mutations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pytest
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


class OptionalDictHost(BaseModel):
    labels: dict[str, int] | None = None
    seeded: dict[str, int] | None = Field(default_factory=lambda: {"default": 1})


class AnnotatedMappingHost(BaseModel):
    limits: dict[
        Annotated[str, Field(min_length=2)],
        Annotated[int, Field(gt=0)],
    ] = Field(default_factory=dict)


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


def test_optional_dict_default_none_stays_omitted_and_materializes_none() -> None:
    tree = build_form_tree(OptionalDictHost)

    assert "labels" not in tree.to_python()
    assert tree.to_instance().labels is None


def test_optional_dict_existing_null_overrides_seeded_default() -> None:
    tree = build_form_tree(OptionalDictHost, existing={"seeded": None})

    assert tree.to_python()["seeded"] is None
    assert tree.to_instance().seeded is None


def test_set_value_can_clear_optional_dict_to_null() -> None:
    tree = build_form_tree(OptionalDictHost, existing={"labels": {"a": 1}})

    result = tree.set_value("labels", None)

    assert result.ok is True
    assert tree.to_python()["labels"] is None
    assert tree.to_instance().labels is None


def test_add_entry_after_clearing_optional_dict_does_not_restore_old_entries() -> None:
    tree = build_form_tree(OptionalDictHost, existing={"labels": {"old": 1}})

    clear_result = tree.set_value("labels", None)
    add_result = tree.add_entry("labels", "new", 2)

    assert clear_result.ok is True
    assert add_result.ok is True
    assert tree.to_python()["labels"] == {"new": 2}
    assert tree.to_instance().labels == {"new": 2}


def test_add_entry_after_existing_null_does_not_restore_seeded_default() -> None:
    tree = build_form_tree(OptionalDictHost, existing={"seeded": None})

    result = tree.add_entry("seeded", "new", 2)

    assert result.ok is True
    assert tree.to_python()["seeded"] == {"new": 2}
    assert tree.to_instance().seeded == {"new": 2}


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


def test_add_entry_rejects_annotated_key_constraint_without_mutating() -> None:
    tree = build_form_tree(AnnotatedMappingHost)

    result = tree.add_entry("limits", "x", 1)

    assert result.ok is False
    assert result.errors == ("length must be >= 2",)
    limits = tree.root.find("limits")
    assert isinstance(limits, MappingNode)
    assert limits.entries == []
    assert tree.snapshots == []


def test_add_entry_rejects_annotated_value_constraint_without_mutating() -> None:
    tree = build_form_tree(AnnotatedMappingHost)

    result = tree.add_entry("limits", "ok", -1)

    assert result.ok is False
    assert result.errors == ("must be > 0",)
    limits = tree.root.find("limits")
    assert isinstance(limits, MappingNode)
    assert limits.entries == []
    assert tree.snapshots == []


def test_add_entry_rejects_explicit_none_value_without_mutating() -> None:
    tree = build_form_tree(WithDict)

    result = tree.add_entry("settings", "timeout", None)

    assert result.ok is False
    assert result.errors == ("value is required",)
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


def test_rename_key_same_normalized_key_is_noop_without_snapshot() -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"port": 80, "rps": 100}}
    )
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    entries_before = list(settings.entries)
    snapshots_before = list(tree.snapshots)
    cursor_before = tree.cursor

    result = tree.rename_key("settings", 0, "port")

    assert result.ok is True
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert settings.entries == entries_before
    assert settings.to_python() == {"port": 80, "rps": 100}
    assert tree.snapshots == snapshots_before
    assert tree.cursor == cursor_before


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


@pytest.mark.parametrize(
    ("operation", "expected_error"),
    [
        (lambda tree: tree.remove_entry("settings", True), "index must be an integer"),
        (lambda tree: tree.remove_entry("settings", 1.2), "index must be an integer"),
        (lambda tree: tree.rename_key("settings", True, "x"), "index must be an integer"),
        (lambda tree: tree.rename_key("settings", 1.2, "x"), "index must be an integer"),
    ],
)
def test_mapping_index_mutations_reject_non_integer_indexes_without_mutating(
    operation,
    expected_error: str,
) -> None:
    tree = build_form_tree(
        WithDict, existing={"settings": {"a": 1, "b": 2, "c": 3}}
    )
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    entries_before = list(settings.entries)
    snapshots_before = list(tree.snapshots)
    cursor_before = tree.cursor

    result = operation(tree)

    assert result.ok is False
    assert result.errors == (expected_error,)
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert settings.entries == entries_before
    assert settings.to_python() == {"a": 1, "b": 2, "c": 3}
    assert tree.snapshots == snapshots_before
    assert tree.cursor == cursor_before


def test_rename_key_rejects_duplicate_key_without_mutating() -> None:
    tree = build_form_tree(WithDict, existing={"settings": {"a": 1, "b": 2}})
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)

    result = tree.rename_key("settings", 1, "a")

    assert result.ok is False
    assert result.errors == ("duplicate key 'a'",)
    assert settings.to_python() == {"a": 1, "b": 2}
    assert tree.snapshots == []


def test_rename_key_rejects_annotated_key_constraint_without_mutating() -> None:
    tree = build_form_tree(AnnotatedMappingHost, existing={"limits": {"ok": 1}})
    limits = tree.root.find("limits")
    assert isinstance(limits, MappingNode)

    result = tree.rename_key("limits", 0, "x")

    assert result.ok is False
    assert result.errors == ("length must be >= 2",)
    assert limits.to_python() == {"ok": 1}
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


def test_set_value_replaces_mapping_entries_and_undoes() -> None:
    tree = build_form_tree(WithDict, existing={"settings": {"old": 1}})
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)

    result = tree.set_value("settings", {"timeout": 30, "retries": 3})

    assert result.ok is True
    assert settings.to_python() == {"timeout": 30, "retries": 3}
    assert tree.undo() is True
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)
    assert settings.to_python() == {"old": 1}


def test_set_value_rejects_invalid_mapping_value_without_mutating() -> None:
    tree = build_form_tree(WithDict, existing={"settings": {"old": 1}})
    settings = tree.root.find("settings")
    assert isinstance(settings, MappingNode)

    result = tree.set_value("settings", {"timeout": "not-an-int"})

    assert result.ok is False
    assert result.errors == ("['timeout']: expected int, got str",)
    assert settings.to_python() == {"old": 1}
    assert tree.snapshots == []


def test_set_value_rejects_annotated_mapping_key_without_mutating() -> None:
    tree = build_form_tree(AnnotatedMappingHost, existing={"limits": {"ok": 1}})
    limits = tree.root.find("limits")
    assert isinstance(limits, MappingNode)

    result = tree.set_value("limits", {"x": 1})

    assert result.ok is False
    assert result.errors == ("key 'x': length must be >= 2",)
    assert limits.to_python() == {"ok": 1}
    assert tree.snapshots == []


def test_set_value_rejects_annotated_mapping_value_without_mutating() -> None:
    tree = build_form_tree(AnnotatedMappingHost, existing={"limits": {"ok": 1}})
    limits = tree.root.find("limits")
    assert isinstance(limits, MappingNode)

    result = tree.set_value("limits", {"ok": -1})

    assert result.ok is False
    assert result.errors == ("['ok']: must be > 0",)
    assert limits.to_python() == {"ok": 1}
    assert tree.snapshots == []


def test_set_value_rejects_normalized_duplicate_mapping_keys_without_mutating() -> None:
    tree = build_form_tree(
        WithPathDict,
        existing={"paths": {Path("old.yaml"): 1}},
    )
    paths = tree.root.find("paths")
    assert isinstance(paths, MappingNode)

    result = tree.set_value(
        "paths",
        {
            Path("existing.yaml"): 1,
            "existing.yaml": 2,
        },
    )

    assert result.ok is False
    assert result.errors == ("duplicate key PosixPath('existing.yaml')",)
    assert paths.to_python() == {Path("old.yaml"): 1}
    assert tree.snapshots == []
