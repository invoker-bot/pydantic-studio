"""Unit tests for the JSON API serializer."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html.serialize import (
    dispatch_mutation,
    tree_to_json,
    validation_envelope,
)


class _Primitive(BaseModel):
    name: str = Field(description="Service identifier")
    workers: int = 4


class _Inner(BaseModel):
    host: str
    port: int = 5432


class _Outer(BaseModel):
    primary: _Inner
    tags: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class _EmailVariant(BaseModel):
    kind: Literal["email"] = "email"
    address: str


class _SlackVariant(BaseModel):
    kind: Literal["slack"] = "slack"
    channel: str


_Notifier = Annotated[_EmailVariant | _SlackVariant, Field(discriminator="kind")]


class _WithUnion(BaseModel):
    notifier: _Notifier


def test_tree_to_json_returns_schema_name_and_root() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 8})
    data = tree_to_json(tree)
    assert data["schema_name"].endswith("_Primitive")
    assert data["root"]["kind"] == "group"
    field_kinds = {f["name"]: f["kind"] for f in data["root"]["fields"]}
    assert field_kinds == {"name": "string", "workers": "int"}


def test_tree_to_json_excludes_schema_class_and_snapshots() -> None:
    tree = build_form_tree(_Primitive)
    # Seed a snapshot so we can verify it's stripped.
    tree.set_value("name", "after")
    data = tree_to_json(tree)
    assert "schema_class" not in data
    assert "snapshots" not in data


def test_tree_to_json_nested_group_renders_as_group_node() -> None:
    tree = build_form_tree(
        _Outer,
        existing={"primary": {"host": "db.internal", "port": 5432}},
    )
    data = tree_to_json(tree)
    primary = next(f for f in data["root"]["fields"] if f["name"] == "primary")
    assert primary["kind"] == "group"
    host = next(f for f in primary["fields"] if f["name"] == "host")
    assert host["kind"] == "string"
    assert host["value"] == "db.internal"


def test_tree_to_json_sequence_renders_as_sequence_node_with_items() -> None:
    tree = build_form_tree(_Outer, existing={"primary": {"host": "x"}, "tags": ["a", "b"]})
    data = tree_to_json(tree)
    tags = next(f for f in data["root"]["fields"] if f["name"] == "tags")
    assert tags["kind"] == "sequence"
    assert [item["value"] for item in tags["items"]] == ["a", "b"]


def test_tree_to_json_mapping_renders_as_mapping_node_with_entries() -> None:
    tree = build_form_tree(
        _Outer,
        existing={"primary": {"host": "x"}, "env": {"TZ": "UTC", "LOG": "info"}},
    )
    data = tree_to_json(tree)
    env = next(f for f in data["root"]["fields"] if f["name"] == "env")
    assert env["kind"] == "mapping"
    pairs = [(k["value"], v["value"]) for k, v in env["entries"]]
    assert pairs == [("TZ", "UTC"), ("LOG", "info")]


def test_tree_to_json_union_renders_with_selected_variant() -> None:
    tree = build_form_tree(
        _WithUnion,
        existing={"notifier": {"kind": "email", "address": "a@x"}},
    )
    data = tree_to_json(tree)
    notifier = next(f for f in data["root"]["fields"] if f["name"] == "notifier")
    assert notifier["kind"] == "union"
    assert notifier["selected_index"] == 0
    assert notifier["selected"]["kind"] == "group"
    address = next(f for f in notifier["selected"]["fields"] if f["name"] == "address")
    assert address["value"] == "a@x"


def test_validation_envelope_ok_for_complete_tree() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 8})
    env = validation_envelope(tree)
    assert env == {"ok": True, "errors": []}


def test_validation_envelope_collects_per_field_errors() -> None:
    # Required field 'name' deliberately unset
    tree = build_form_tree(_Primitive)
    env = validation_envelope(tree)
    assert env["ok"] is False
    assert any("name" in e["path"] for e in env["errors"])
    for err in env["errors"]:
        assert set(err.keys()) >= {"path", "message"}


def test_dispatch_set_value_updates_tree_and_returns_ok() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "before", "workers": 4})
    result = dispatch_mutation(tree, {"op": "set_value", "path": "name", "value": "after"})
    assert result.ok is True
    assert tree.root.find("name").value == "after"


def test_dispatch_set_value_validation_failure_leaves_tree_untouched() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 4})
    # workers is int; setting a non-int should fail validation
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "workers", "value": "not-an-int"}
    )
    assert result.ok is False
    assert tree.root.find("workers").value == 4
