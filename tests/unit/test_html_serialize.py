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


class _WithList(BaseModel):
    tags: list[str] = Field(default_factory=list)


class _WithDict(BaseModel):
    env: dict[str, str] = Field(default_factory=dict)


class _UnionHolder(BaseModel):
    value: int | str


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


def test_dispatch_add_item_appends_to_sequence() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a"]})
    result = dispatch_mutation(tree, {"op": "add_item", "path": "tags"})
    assert result.ok is True
    assert len(tree.root.find("tags").items) == 2


def test_dispatch_remove_item_pops_indexed_entry() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a", "b", "c"]})
    result = dispatch_mutation(
        tree, {"op": "remove_item", "path": "tags", "index": 1}
    )
    assert result.ok is True
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["a", "c"]


def test_dispatch_move_item_reorders_sequence() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a", "b", "c"]})
    result = dispatch_mutation(
        tree, {"op": "move_item", "path": "tags", "from": 0, "to": 2}
    )
    assert result.ok is True
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["b", "c", "a"]


def test_dispatch_add_entry_appends_new_key() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC"}})
    result = dispatch_mutation(
        tree, {"op": "add_entry", "path": "env", "key": "LOG"}
    )
    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("TZ", "UTC"), ("LOG", None)]


def test_dispatch_remove_entry_drops_indexed_pair() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC", "LOG": "info"}})
    result = dispatch_mutation(
        tree, {"op": "remove_entry", "path": "env", "index": 0}
    )
    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("LOG", "info")]


def test_dispatch_rename_key_changes_key_at_index() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC"}})
    result = dispatch_mutation(
        tree,
        {"op": "rename_key", "path": "env", "index": 0, "new_key": "TIMEZONE"},
    )
    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("TIMEZONE", "UTC")]


def test_dispatch_select_variant_switches_to_indexed_branch() -> None:
    tree = build_form_tree(_UnionHolder, existing={"value": 42})
    # variant 0 is int; switch to str (variant 1)
    result = dispatch_mutation(
        tree, {"op": "select_variant", "path": "value", "variant_index": 1}
    )
    assert result.ok is True
    val = tree.root.find("value")
    assert val.selected_index == 1
    assert val.selected.kind == "string"


def test_dispatch_unknown_op_fails_without_mutating() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 4})
    result = dispatch_mutation(tree, {"op": "nuke", "path": "name"})
    assert result.ok is False
    assert any("nuke" in e for e in result.errors)
    assert tree.root.find("name").value == "alpha"


def test_dispatch_missing_op_fails_without_mutating() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha"})
    result = dispatch_mutation(tree, {"path": "name", "value": "x"})
    assert result.ok is False
    assert tree.root.find("name").value == "alpha"


def test_dispatch_bad_path_fails_without_mutating() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha"})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "nope.does.not.exist", "value": "x"}
    )
    assert result.ok is False


def test_dispatch_set_value_enum_coerces_name_string_to_member() -> None:
    """EnumField sends {op: 'set_value', value: <member_name>} since
    EnumNode._serialize_member emits the name. dispatch_mutation must
    coerce name -> member before validate_value sees it."""
    from enum import Enum

    from pydantic import BaseModel

    class Color(Enum):
        RED = "red"
        GREEN = "green"

    class M(BaseModel):
        color: Color = Color.RED

    tree = build_form_tree(M, existing={"color": Color.RED})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "color", "value": "GREEN"}
    )
    assert result.ok is True
    color_node = tree.root.find("color")
    assert color_node.value == Color.GREEN


def test_dispatch_set_value_literal_str() -> None:
    """LiteralField sends raw choice values; for str literals this is
    a plain string, which Literal[...] accepts directly."""
    from pydantic import BaseModel

    class M(BaseModel):
        choice: Literal["a", "b"] = "a"

    tree = build_form_tree(M, existing={"choice": "a"})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "choice", "value": "b"}
    )
    assert result.ok is True
    assert tree.root.find("choice").value == "b"


def test_dispatch_set_value_literal_int() -> None:
    """LiteralField preserves the choice type via matchedChoice
    lookup; for int literals the wire value is a number."""
    from pydantic import BaseModel

    class M(BaseModel):
        level: Literal[1, 2, 3] = 1

    tree = build_form_tree(M, existing={"level": 1})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "level", "value": 2}
    )
    assert result.ok is True
    assert tree.root.find("level").value == 2


def test_dispatch_set_value_bool() -> None:
    """BoolField sends raw true/false; trivial round-trip."""
    from pydantic import BaseModel

    class M(BaseModel):
        flag: bool = False

    tree = build_form_tree(M, existing={"flag": False})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "flag", "value": True}
    )
    assert result.ok is True
    assert tree.root.find("flag").value is True
