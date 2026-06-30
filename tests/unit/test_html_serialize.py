"""Unit tests for the JSON API serializer."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree, load_yaml
from pydantic_studio.renderers.html.serialize import (
    dispatch_mutation,
    tree_to_json,
    validation_envelope,
)
from pydantic_studio.variants import VariantRegistry, VariantSpec, build_variant_form_tree
from tests.fixtures.schemas import WithColor


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


class _OptionalOuter(BaseModel):
    primary: _Inner | None = None


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


class _WithIntList(BaseModel):
    counts: list[int] = Field(default_factory=list)


class _WithIntMatrix(BaseModel):
    matrix: list[list[int]] = Field(default_factory=list)


class _WithDict(BaseModel):
    env: dict[str, str] = Field(default_factory=dict)


class _WithIntDict(BaseModel):
    ports: dict[int, str] = Field(default_factory=dict)


class _WithIntValueDict(BaseModel):
    weights: dict[str, int] = Field(default_factory=dict)


class _WithTupleKeyDict(BaseModel):
    routes: dict[tuple[int, int], str] = Field(default_factory=dict)


class _WithIntListValueDict(BaseModel):
    buckets: dict[str, list[int]] = Field(default_factory=dict)


class _UnionHolder(BaseModel):
    value: int | str


class _StructuredSeed(BaseModel):
    count: int
    counts: list[int] = Field(default_factory=list)
    ports: dict[int, int] = Field(default_factory=dict)


class _StructuredUnionHolder(BaseModel):
    value: str | _StructuredSeed


class _WithStructuredSeedList(BaseModel):
    items: list[_StructuredSeed] = Field(default_factory=list)


class _WithStructuredSeedMap(BaseModel):
    items: dict[str, _StructuredSeed] = Field(default_factory=dict)


class _WithStructuredUnionList(BaseModel):
    items: list[str | _StructuredSeed] = Field(default_factory=list)


class _WithStructuredUnionMap(BaseModel):
    items: dict[str, str | _StructuredSeed] = Field(default_factory=dict)


class _AnyHolder(BaseModel):
    payload: Any = None


class _VariantEmail(BaseModel):
    address: str = "ops@example.com"


class _VariantSlack(BaseModel):
    channel: str = "#ops"


class _VariantPort(BaseModel):
    port: int = 443
    replicas: list[int] = Field(default_factory=list)


def test_tree_to_json_returns_schema_name_and_root() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 8})
    data = tree_to_json(tree)
    assert data["schema_name"].endswith("_Primitive")
    assert data["root"]["kind"] == "group"
    field_kinds = {f["name"]: f["kind"] for f in data["root"]["fields"]}
    assert field_kinds == {"name": "string", "workers": "int"}


def test_tree_to_json_excludes_internal_formtree_fields_and_keeps_group_state() -> None:
    tree = build_form_tree(_Outer)
    # Seed a snapshot so we can verify it's stripped.
    tree.set_value("primary.host", "after")
    data = tree_to_json(tree)
    assert "schema_class" not in data
    assert "snapshots" not in data
    assert "created_at" not in data
    assert "cursor" not in data
    assert "snapshot_limit" not in data
    assert "draft_path" not in data
    assert "omitted" in data["root"]
    assert "omitted" in data["root"]["fields"][0]


def test_tree_to_json_marks_omitted_optional_group() -> None:
    tree = build_form_tree(_OptionalOuter)

    data = tree_to_json(tree)

    primary = next(f for f in data["root"]["fields"] if f["name"] == "primary")
    assert primary["omitted"] is True


def test_tree_to_json_includes_clean_history_state() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 8})

    data = tree_to_json(tree)

    assert data["history"] == {"can_undo": False, "can_redo": False}


def test_tree_to_json_history_tracks_undo_redo_cursor() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 8})

    tree.set_value("name", "beta")
    after_edit = tree_to_json(tree)

    tree.undo()
    after_undo = tree_to_json(tree)

    tree.redo()
    after_redo = tree_to_json(tree)

    assert after_edit["history"] == {"can_undo": True, "can_redo": False}
    assert after_undo["history"] == {"can_undo": False, "can_redo": True}
    assert after_redo["history"] == {"can_undo": True, "can_redo": False}


def test_tree_to_json_includes_yaml_preview_of_values() -> None:
    """The envelope must carry a `preview` field that renders the
    *effective config values* as YAML, so the SPA can show users what
    will actually be saved instead of the raw FormTree structure.
    """
    tree = build_form_tree(
        _Primitive, existing={"name": "demo-service", "workers": 8}
    )
    data = tree_to_json(tree)
    assert "preview" in data
    preview = data["preview"]
    assert isinstance(preview, str)
    # Real values, YAML-formatted (key: value)
    assert "name: demo-service" in preview
    assert "workers: 8" in preview
    # Metadata MUST NOT leak in
    assert '"kind"' not in preview
    assert '"required"' not in preview
    assert "fields:" not in preview


def test_tree_to_json_preview_reflects_post_mutation_state() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "before", "workers": 1})
    tree.set_value("name", "after")
    data = tree_to_json(tree)
    assert "name: after" in data["preview"]
    assert "name: before" not in data["preview"]


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


def test_tree_to_json_load_yaml_enum_value_matches_choice_name(tmp_path) -> None:
    src = tmp_path / "config.yaml"
    src.write_text("favorite: red\n", encoding="utf-8")

    tree = load_yaml(src, WithColor)
    data = tree_to_json(tree)

    favorite = next(f for f in data["root"]["fields"] if f["name"] == "favorite")
    assert favorite["value"] == "RED"
    assert favorite["choices"] == [
        ["RED", "RED"],
        ["GREEN", "GREEN"],
        ["BLUE", "BLUE"],
    ]


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


def test_tree_to_json_includes_root_variant_metadata() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_VariantEmail, label="Email"),
                VariantSpec(id="slack", model=_VariantSlack, label="Slack"),
            ]
        ),
        selected_id="email",
        discriminator="class_name",
        persistence="inline_discriminator",
    )

    data = tree_to_json(tree)

    assert data["variant"]["selected_id"] == "email"
    assert data["variant"]["options"][0]["label"] == "Email"
    assert "class_name: email" in data["preview"]


def test_tree_to_json_serializes_non_json_native_any_value() -> None:
    class OpaqueValue:
        def __str__(self) -> str:
            return "opaque-value"

    tree = build_form_tree(_AnyHolder, existing={"payload": OpaqueValue()})

    data = tree_to_json(tree)

    payload = next(f for f in data["root"]["fields"] if f["name"] == "payload")
    assert payload["value"] == "opaque-value"
    json.dumps(data, allow_nan=False)


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


def test_dispatch_set_value_requires_value_key_without_mutating() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 4})
    result = dispatch_mutation(tree, {"op": "set_value", "path": "name"})

    assert result.ok is False
    assert any("value is required" in err for err in result.errors)
    assert tree.root.find("name").value == "alpha"


def test_dispatch_rejects_null_path_without_mutating() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 4})
    result = dispatch_mutation(tree, {"op": "set_value", "path": None, "value": "beta"})

    assert result.ok is False
    assert any("path must be a string" in err for err in result.errors)
    assert tree.root.find("name").value == "alpha"


def test_dispatch_set_value_requires_path_without_mutating() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 4})
    result = dispatch_mutation(tree, {"op": "set_value", "value": "beta"})

    assert result.ok is False
    assert any("path is required" in err for err in result.errors)
    assert tree.root.find("name").value == "alpha"


def test_dispatch_set_value_coerces_nested_container_scalar_values() -> None:
    list_tree = build_form_tree(_WithIntList, existing={"counts": [1]})
    list_result = dispatch_mutation(
        list_tree, {"op": "set_value", "path": "counts.0", "value": "2"}
    )

    assert list_result.ok is True
    assert list_tree.root.find("counts").items[0].value == 2

    mapping_tree = build_form_tree(_WithIntValueDict, existing={"weights": {"base": 1}})
    mapping_result = dispatch_mutation(
        mapping_tree, {"op": "set_value", "path": "weights.0", "value": "2"}
    )

    assert mapping_result.ok is True
    assert mapping_tree.root.find("weights").entries[0][1].value == 2


def test_dispatch_set_value_coerces_group_replacement_fields() -> None:
    tree = build_form_tree(_Outer, existing={"primary": {"host": "old.local"}})

    result = dispatch_mutation(
        tree,
        {
            "op": "set_value",
            "path": "primary",
            "value": {"host": "db.local", "port": "15432"},
        },
    )

    assert result.ok is True
    primary = tree.root.find("primary")
    assert primary.find("host").value == "db.local"
    assert primary.find("port").value == 15432


def test_dispatch_set_value_coerces_sequence_replacement_items() -> None:
    tree = build_form_tree(_WithIntList, existing={"counts": [1]})

    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "counts", "value": ["3", "4"]}
    )

    assert result.ok is True
    counts = tree.root.find("counts")
    assert [item.value for item in counts.items] == [3, 4]


def test_dispatch_set_value_coerces_nested_sequence_replacement_items() -> None:
    tree = build_form_tree(_WithIntMatrix, existing={"matrix": [[1]]})

    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "matrix", "value": [["2", "3"]]}
    )

    assert result.ok is True
    matrix = tree.root.find("matrix")
    assert [[cell.value for cell in row.items] for row in matrix.items] == [[2, 3]]


def test_dispatch_set_value_coerces_mapping_replacement_values() -> None:
    tree = build_form_tree(_WithIntValueDict, existing={"weights": {"base": 1}})

    result = dispatch_mutation(
        tree,
        {
            "op": "set_value",
            "path": "weights",
            "value": {"base": "2", "extra": "3"},
        },
    )

    assert result.ok is True
    weights = tree.root.find("weights")
    assert [(key.value, value.value) for key, value in weights.entries] == [
        ("base", 2),
        ("extra", 3),
    ]


def test_dispatch_set_value_coerces_structured_union_replacement() -> None:
    tree = build_form_tree(_StructuredUnionHolder, existing={"value": "seeded"})

    result = dispatch_mutation(
        tree,
        {
            "op": "set_value",
            "path": "value",
            "value": {
                "count": "2",
                "counts": ["3", "4"],
                "ports": {"80": "8080"},
            },
        },
    )

    assert result.ok is True
    val = tree.root.find("value")
    assert val.selected_index == 1
    assert val.selected.kind == "group"
    assert val.selected.find("count").value == 2
    assert [item.value for item in val.selected.find("counts").items] == [3, 4]
    assert [
        (key.value, value.value)
        for key, value in val.selected.find("ports").entries
    ] == [(80, 8080)]


def test_dispatch_set_value_coerces_selected_union_scalar_value() -> None:
    tree = build_form_tree(_UnionHolder, existing={"value": 1})

    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "value", "value": "2"}
    )

    assert result.ok is True
    union = tree.root.find("value")
    assert union.selected.value == 2


def test_dispatch_set_value_null_clears_optional_group() -> None:
    tree = build_form_tree(
        _OptionalOuter,
        existing={"primary": {"host": "db.internal", "port": 15432}},
    )

    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "primary", "value": None}
    )

    assert result.ok is True
    assert tree.to_instance().primary is None
    primary = tree.root.find("primary")
    assert primary.omitted is True
    assert primary.find("host").value is None
    assert primary.find("port").value == 5432


def test_dispatch_undo_restores_previous_state() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 4})
    dispatch_mutation(tree, {"op": "set_value", "path": "name", "value": "beta"})

    result = dispatch_mutation(tree, {"op": "undo"})

    assert result.ok is True
    assert tree.root.find("name").value == "alpha"


def test_dispatch_redo_restores_undone_state() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha", "workers": 4})
    dispatch_mutation(tree, {"op": "set_value", "path": "name", "value": "beta"})
    dispatch_mutation(tree, {"op": "undo"})

    result = dispatch_mutation(tree, {"op": "redo"})

    assert result.ok is True
    assert tree.root.find("name").value == "beta"


def test_dispatch_add_item_appends_to_sequence() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a"]})
    result = dispatch_mutation(tree, {"op": "add_item", "path": "tags"})
    assert result.ok is True
    assert len(tree.root.find("tags").items) == 2


def test_dispatch_add_item_passes_value_to_tree() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a"]})

    result = dispatch_mutation(
        tree, {"op": "add_item", "path": "tags", "value": "seeded"}
    )

    assert result.ok is True
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["a", "seeded"]


def test_dispatch_add_item_coerces_typed_value() -> None:
    tree = build_form_tree(_WithIntList, existing={"counts": [1]})

    result = dispatch_mutation(
        tree, {"op": "add_item", "path": "counts", "value": "2"}
    )

    assert result.ok is True
    values = [it.value for it in tree.root.find("counts").items]
    assert values == [1, 2]


def test_dispatch_add_item_coerces_nested_sequence_seed_values() -> None:
    tree = build_form_tree(_WithIntMatrix)

    result = dispatch_mutation(
        tree, {"op": "add_item", "path": "matrix", "value": ["2", "3"]}
    )

    assert result.ok is True
    row = tree.root.find("matrix").items[0]
    assert [cell.value for cell in row.items] == [2, 3]


def test_dispatch_add_item_coerces_structured_seed_value() -> None:
    tree = build_form_tree(_WithStructuredSeedList)

    result = dispatch_mutation(
        tree,
        {
            "op": "add_item",
            "path": "items",
            "value": {
                "count": "2",
                "counts": ["3", "4"],
                "ports": {"80": "8080"},
            },
        },
    )

    assert result.ok is True
    item = tree.root.find("items").items[0]
    assert item.find("count").value == 2
    assert [nested.value for nested in item.find("counts").items] == [3, 4]
    assert [(key.value, value.value) for key, value in item.find("ports").entries] == [
        (80, 8080)
    ]


def test_dispatch_add_item_coerces_structured_union_seed_value() -> None:
    tree = build_form_tree(_WithStructuredUnionList)

    result = dispatch_mutation(
        tree,
        {
            "op": "add_item",
            "path": "items",
            "value": {
                "count": "2",
                "counts": ["3", "4"],
                "ports": {"80": "8080"},
            },
        },
    )

    assert result.ok is True
    union = tree.root.find("items").items[0]
    assert union.selected_index == 1
    assert union.selected.kind == "group"
    assert union.selected.find("count").value == 2
    assert [nested.value for nested in union.selected.find("counts").items] == [3, 4]
    assert [
        (key.value, value.value)
        for key, value in union.selected.find("ports").entries
    ] == [(80, 8080)]


def test_dispatch_insert_item_inserts_at_index() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a", "c"]})

    result = dispatch_mutation(
        tree, {"op": "insert_item", "path": "tags", "index": 1, "value": "b"}
    )

    assert result.ok is True
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["a", "b", "c"]


def test_dispatch_insert_item_coerces_typed_value() -> None:
    tree = build_form_tree(_WithIntList, existing={"counts": [1, 3]})

    result = dispatch_mutation(
        tree, {"op": "insert_item", "path": "counts", "index": 1, "value": "2"}
    )

    assert result.ok is True
    values = [it.value for it in tree.root.find("counts").items]
    assert values == [1, 2, 3]


def test_dispatch_insert_item_coerces_nested_sequence_seed_values() -> None:
    tree = build_form_tree(_WithIntMatrix, existing={"matrix": [[1]]})

    result = dispatch_mutation(
        tree,
        {"op": "insert_item", "path": "matrix", "index": 0, "value": ["2", "3"]},
    )

    assert result.ok is True
    rows = tree.root.find("matrix").items
    assert [[cell.value for cell in row.items] for row in rows] == [[2, 3], [1]]


def test_dispatch_insert_item_coerces_structured_seed_value() -> None:
    tree = build_form_tree(
        _WithStructuredSeedList,
        existing={"items": [{"count": 1, "counts": [], "ports": {}}]},
    )

    result = dispatch_mutation(
        tree,
        {
            "op": "insert_item",
            "path": "items",
            "index": 0,
            "value": {
                "count": "2",
                "counts": ["3", "4"],
                "ports": {"80": "8080"},
            },
        },
    )

    assert result.ok is True
    items = tree.root.find("items").items
    assert [item.find("count").value for item in items] == [2, 1]
    assert [nested.value for nested in items[0].find("counts").items] == [3, 4]
    assert [
        (key.value, value.value)
        for key, value in items[0].find("ports").entries
    ] == [(80, 8080)]


def test_dispatch_insert_item_coerces_structured_union_seed_value() -> None:
    tree = build_form_tree(_WithStructuredUnionList, existing={"items": ["seeded"]})

    result = dispatch_mutation(
        tree,
        {
            "op": "insert_item",
            "path": "items",
            "index": 0,
            "value": {
                "count": "2",
                "counts": ["3", "4"],
                "ports": {"80": "8080"},
            },
        },
    )

    assert result.ok is True
    items = tree.root.find("items").items
    assert items[0].selected_index == 1
    assert items[0].selected.kind == "group"
    assert items[0].selected.find("count").value == 2
    assert [nested.value for nested in items[0].selected.find("counts").items] == [
        3,
        4,
    ]
    assert [
        (key.value, value.value)
        for key, value in items[0].selected.find("ports").entries
    ] == [(80, 8080)]
    assert items[1].selected.value == "seeded"


def test_dispatch_remove_item_pops_indexed_entry() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a", "b", "c"]})
    result = dispatch_mutation(
        tree, {"op": "remove_item", "path": "tags", "index": 1}
    )
    assert result.ok is True
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["a", "c"]


def test_dispatch_remove_item_rejects_bool_index_without_mutating() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a", "b", "c"]})
    result = dispatch_mutation(
        tree, {"op": "remove_item", "path": "tags", "index": True}
    )

    assert result.ok is False
    assert any("index must be an integer" in err for err in result.errors)
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["a", "b", "c"]


def test_dispatch_move_item_reorders_sequence() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a", "b", "c"]})
    result = dispatch_mutation(
        tree, {"op": "move_item", "path": "tags", "from": 0, "to": 2}
    )
    assert result.ok is True
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["b", "c", "a"]


def test_dispatch_move_item_rejects_float_target_without_mutating() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a", "b", "c"]})
    result = dispatch_mutation(
        tree, {"op": "move_item", "path": "tags", "from": 0, "to": 1.9}
    )

    assert result.ok is False
    assert any("to must be an integer" in err for err in result.errors)
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["a", "b", "c"]


def test_dispatch_move_item_requires_to_argument_without_mutating() -> None:
    tree = build_form_tree(_WithList, existing={"tags": ["a", "b", "c"]})
    result = dispatch_mutation(tree, {"op": "move_item", "path": "tags", "from": 0})

    assert result.ok is False
    assert any("to is required" in err for err in result.errors)
    values = [it.value for it in tree.root.find("tags").items]
    assert values == ["a", "b", "c"]


def test_dispatch_add_entry_appends_new_key() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC"}})
    result = dispatch_mutation(
        tree, {"op": "add_entry", "path": "env", "key": "LOG"}
    )
    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("TZ", "UTC"), ("LOG", None)]


def test_dispatch_add_entry_passes_value_to_tree() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC"}})

    result = dispatch_mutation(
        tree,
        {"op": "add_entry", "path": "env", "key": "LOG", "value": "debug"},
    )

    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("TZ", "UTC"), ("LOG", "debug")]


def test_dispatch_add_entry_coerces_typed_value() -> None:
    tree = build_form_tree(_WithIntValueDict, existing={"weights": {"base": 1}})

    result = dispatch_mutation(
        tree,
        {"op": "add_entry", "path": "weights", "key": "extra", "value": "2"},
    )

    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("weights").entries]
    assert pairs == [("base", 1), ("extra", 2)]


def test_dispatch_add_entry_coerces_nested_sequence_seed_value() -> None:
    tree = build_form_tree(_WithIntListValueDict)

    result = dispatch_mutation(
        tree,
        {"op": "add_entry", "path": "buckets", "key": "first", "value": ["2", "3"]},
    )

    assert result.ok is True
    key, value = tree.root.find("buckets").entries[0]
    assert key.value == "first"
    assert [cell.value for cell in value.items] == [2, 3]


def test_dispatch_add_entry_coerces_structured_seed_value() -> None:
    tree = build_form_tree(_WithStructuredSeedMap)

    result = dispatch_mutation(
        tree,
        {
            "op": "add_entry",
            "path": "items",
            "key": "first",
            "value": {
                "count": "2",
                "counts": ["3", "4"],
                "ports": {"80": "8080"},
            },
        },
    )

    assert result.ok is True
    key, value = tree.root.find("items").entries[0]
    assert key.value == "first"
    assert value.find("count").value == 2
    assert [nested.value for nested in value.find("counts").items] == [3, 4]
    assert [
        (port.value, target.value) for port, target in value.find("ports").entries
    ] == [(80, 8080)]


def test_dispatch_add_entry_coerces_structured_union_seed_value() -> None:
    tree = build_form_tree(_WithStructuredUnionMap)

    result = dispatch_mutation(
        tree,
        {
            "op": "add_entry",
            "path": "items",
            "key": "first",
            "value": {
                "count": "2",
                "counts": ["3", "4"],
                "ports": {"80": "8080"},
            },
        },
    )

    assert result.ok is True
    key, union = tree.root.find("items").entries[0]
    assert key.value == "first"
    assert union.selected_index == 1
    assert union.selected.kind == "group"
    assert union.selected.find("count").value == 2
    assert [nested.value for nested in union.selected.find("counts").items] == [3, 4]
    assert [
        (port.value, target.value)
        for port, target in union.selected.find("ports").entries
    ] == [(80, 8080)]


def test_dispatch_add_entry_rejects_null_key_without_mutating() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC"}})
    result = dispatch_mutation(tree, {"op": "add_entry", "path": "env", "key": None})

    assert result.ok is False
    assert any("key must be a string" in err for err in result.errors)
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("TZ", "UTC")]


def test_dispatch_add_entry_coerces_typed_mapping_key() -> None:
    tree = build_form_tree(_WithIntDict)

    result = dispatch_mutation(tree, {"op": "add_entry", "path": "ports", "key": "8080"})

    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("ports").entries]
    assert pairs == [(8080, None)]


def test_dispatch_add_entry_coerces_structured_mapping_key() -> None:
    tree = build_form_tree(_WithTupleKeyDict)

    result = dispatch_mutation(
        tree,
        {"op": "add_entry", "path": "routes", "key": ["1", "2"], "value": "edge"},
    )

    assert result.ok is True
    key, value = tree.root.find("routes").entries[0]
    assert key.to_python() == (1, 2)
    assert [item.value for item in key.items] == [1, 2]
    assert value.value == "edge"


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


def test_dispatch_rename_key_coerces_typed_mapping_key() -> None:
    tree = build_form_tree(_WithIntDict, existing={"ports": {80: "http"}})

    result = dispatch_mutation(
        tree,
        {"op": "rename_key", "path": "ports", "index": 0, "new_key": "443"},
    )

    assert result.ok is True
    pairs = [(k.value, v.value) for k, v in tree.root.find("ports").entries]
    assert pairs == [(443, "http")]


def test_dispatch_rename_key_coerces_structured_mapping_key() -> None:
    tree = build_form_tree(_WithTupleKeyDict, existing={"routes": {(1, 2): "edge"}})

    result = dispatch_mutation(
        tree,
        {"op": "rename_key", "path": "routes", "index": 0, "new_key": ["3", "4"]},
    )

    assert result.ok is True
    key, value = tree.root.find("routes").entries[0]
    assert key.to_python() == (3, 4)
    assert [item.value for item in key.items] == [3, 4]
    assert value.value == "edge"


def test_dispatch_rename_key_rejects_null_key_without_mutating() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC"}})
    result = dispatch_mutation(
        tree,
        {"op": "rename_key", "path": "env", "index": 0, "new_key": None},
    )

    assert result.ok is False
    assert any("new_key must be a string" in err for err in result.errors)
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("TZ", "UTC")]


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


def test_dispatch_select_variant_current_index_is_noop_without_seed() -> None:
    tree = build_form_tree(_UnionHolder, existing={"value": "initial"})
    assert tree.set_value("value", "edited").ok is True
    val = tree.root.find("value")
    assert val.selected_index == 1
    selected_before = val.selected
    snapshots_before = list(tree.snapshots)
    cursor_before = tree.cursor

    result = dispatch_mutation(
        tree, {"op": "select_variant", "path": "value", "variant_index": 1}
    )

    assert result.ok is True
    val = tree.root.find("value")
    assert val.selected_index == 1
    assert val.selected is selected_before
    assert val.selected.value == "edited"
    assert tree.snapshots == snapshots_before
    assert tree.cursor == cursor_before


def test_dispatch_select_variant_passes_seed_to_tree() -> None:
    tree = build_form_tree(_UnionHolder, existing={"value": 42})

    result = dispatch_mutation(
        tree,
        {"op": "select_variant", "path": "value", "variant_index": 1, "seed": "seeded"},
    )

    assert result.ok is True
    val = tree.root.find("value")
    assert val.selected_index == 1
    assert val.selected.kind == "string"
    assert val.selected.value == "seeded"


def test_dispatch_select_variant_coerces_seed_for_target_variant() -> None:
    tree = build_form_tree(_UnionHolder, existing={"value": "seeded"})

    result = dispatch_mutation(
        tree,
        {"op": "select_variant", "path": "value", "variant_index": 0, "seed": "2"},
    )

    assert result.ok is True
    val = tree.root.find("value")
    assert val.selected_index == 0
    assert val.selected.kind == "int"
    assert val.selected.value == 2


def test_dispatch_select_variant_coerces_structured_seed_values() -> None:
    tree = build_form_tree(_StructuredUnionHolder, existing={"value": "seeded"})

    result = dispatch_mutation(
        tree,
        {
            "op": "select_variant",
            "path": "value",
            "variant_index": 1,
            "seed": {
                "count": "2",
                "counts": ["3", "4"],
                "ports": {"80": "8080"},
            },
        },
    )

    assert result.ok is True
    val = tree.root.find("value")
    assert val.selected_index == 1
    assert val.selected.kind == "group"
    assert val.selected.find("count").value == 2
    assert [item.value for item in val.selected.find("counts").items] == [3, 4]
    assert [
        (key.value, value.value)
        for key, value in val.selected.find("ports").entries
    ] == [(80, 8080)]


def test_dispatch_select_variant_rejects_duplicate_coerced_seed_mapping_keys() -> None:
    tree = build_form_tree(_StructuredUnionHolder, existing={"value": "seeded"})

    result = dispatch_mutation(
        tree,
        {
            "op": "select_variant",
            "path": "value",
            "variant_index": 1,
            "seed": {
                "count": "2",
                "counts": [],
                "ports": {"80": "8080", "080": "9090"},
            },
        },
    )

    assert result.ok is False
    assert any("duplicate key 80" in error for error in result.errors)
    val = tree.root.find("value")
    assert val.selected_index == 0
    assert val.selected.kind == "string"
    assert val.selected.value == "seeded"


def test_dispatch_select_variant_rejects_string_index_without_mutating() -> None:
    tree = build_form_tree(_UnionHolder, existing={"value": 42})
    result = dispatch_mutation(
        tree, {"op": "select_variant", "path": "value", "variant_index": "1"}
    )

    assert result.ok is False
    assert any("variant_index must be an integer" in err for err in result.errors)
    val = tree.root.find("value")
    assert val.selected_index == 0
    assert val.selected.kind == "int"


def test_dispatch_select_root_variant_switches_root_model() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_VariantEmail),
                VariantSpec(id="slack", model=_VariantSlack),
            ]
        ),
        selected_id="email",
    )

    result = dispatch_mutation(tree, {"op": "select_root_variant", "variant_id": "slack"})

    assert result.ok is True
    assert tree.schema_class is _VariantSlack
    assert tree.root.find("channel") is not None


def test_dispatch_select_root_variant_current_id_is_noop_without_seed() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_VariantEmail),
                VariantSpec(id="slack", model=_VariantSlack),
            ]
        ),
        selected_id="email",
    )
    assert tree.set_value("address", "edited@example.com").ok is True
    root_before = tree.root
    snapshots_before = list(tree.snapshots)
    cursor_before = tree.cursor

    result = dispatch_mutation(
        tree, {"op": "select_root_variant", "variant_id": "email"}
    )

    assert result.ok is True
    assert tree.schema_class is _VariantEmail
    assert tree.root is root_before
    assert tree.root.find("address").value == "edited@example.com"
    assert tree.snapshots == snapshots_before
    assert tree.cursor == cursor_before


def test_dispatch_select_root_variant_passes_seed_to_tree() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_VariantEmail),
                VariantSpec(id="slack", model=_VariantSlack),
            ]
        ),
        selected_id="email",
    )

    result = dispatch_mutation(
        tree,
        {
            "op": "select_root_variant",
            "variant_id": "slack",
            "seed": {"channel": "#alerts"},
        },
    )

    assert result.ok is True
    assert tree.schema_class is _VariantSlack
    assert tree.root.find("channel").value == "#alerts"


def test_dispatch_select_root_variant_coerces_structured_seed_values() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_VariantEmail),
                VariantSpec(id="port", model=_VariantPort),
            ]
        ),
        selected_id="email",
    )

    result = dispatch_mutation(
        tree,
        {
            "op": "select_root_variant",
            "variant_id": "port",
            "seed": {"port": "8443", "replicas": ["1", "2"]},
        },
    )

    assert result.ok is True
    assert tree.schema_class is _VariantPort
    assert tree.root.find("port").value == 8443
    assert [item.value for item in tree.root.find("replicas").items] == [1, 2]


def test_dispatch_select_root_variant_does_not_require_path() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_VariantEmail),
                VariantSpec(id="slack", model=_VariantSlack),
            ]
        ),
        selected_id="email",
    )

    result = dispatch_mutation(
        tree, {"op": "select_root_variant", "variant_id": "slack", "path": None}
    )

    assert result.ok is True
    assert tree.schema_class is _VariantSlack
    assert tree.root.find("channel") is not None


def test_dispatch_select_root_variant_rejects_null_id_without_mutating() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_VariantEmail),
                VariantSpec(id="slack", model=_VariantSlack),
            ]
        ),
        selected_id="email",
    )

    result = dispatch_mutation(tree, {"op": "select_root_variant", "variant_id": None})

    assert result.ok is False
    assert any("variant_id must be a string" in err for err in result.errors)
    assert tree.schema_class is _VariantEmail
    assert tree.root.find("address") is not None


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
    assert any("op is required" in e for e in result.errors)
    assert tree.root.find("name").value == "alpha"


def test_dispatch_non_string_op_fails_without_mutating() -> None:
    tree = build_form_tree(_Primitive, existing={"name": "alpha"})
    result = dispatch_mutation(tree, {"op": 123, "path": "name", "value": "x"})
    assert result.ok is False
    assert any("op must be a string" in e for e in result.errors)
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


def test_dispatch_set_value_datetime_coerces_iso_string() -> None:
    """DatetimeField sends an ISO 8601 string; dispatch must coerce
    to a datetime instance before DatetimeNode.validate_value runs."""
    from datetime import datetime

    from pydantic import BaseModel

    class M(BaseModel):
        when: datetime = datetime(2020, 1, 1)

    tree = build_form_tree(M, existing={"when": datetime(2020, 1, 1)})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "when", "value": "2025-01-15T10:30:00"}
    )
    assert result.ok is True
    assert tree.root.find("when").value == datetime(2025, 1, 15, 10, 30, 0)


def test_dispatch_set_value_date_coerces_iso_string() -> None:
    from datetime import date

    from pydantic import BaseModel

    class M(BaseModel):
        d: date = date(2020, 1, 1)

    tree = build_form_tree(M, existing={"d": date(2020, 1, 1)})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "d", "value": "2025-06-09"}
    )
    assert result.ok is True
    assert tree.root.find("d").value == date(2025, 6, 9)


def test_dispatch_set_value_time_coerces_iso_string() -> None:
    from datetime import time

    from pydantic import BaseModel

    class M(BaseModel):
        t: time = time(0, 0)

    tree = build_form_tree(M, existing={"t": time(0, 0)})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "t", "value": "14:30:00"}
    )
    assert result.ok is True
    assert tree.root.find("t").value == time(14, 30, 0)


def test_dispatch_set_value_timedelta_coerces_iso_duration() -> None:
    from datetime import timedelta

    from pydantic import BaseModel

    class M(BaseModel):
        ttl: timedelta = timedelta(seconds=0)

    tree = build_form_tree(M, existing={"ttl": timedelta(seconds=0)})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "ttl", "value": "PT1H30M"}
    )
    assert result.ok is True
    assert tree.root.find("ttl").value == timedelta(hours=1, minutes=30)


def test_dispatch_set_value_decimal_coerces_string() -> None:
    from decimal import Decimal

    from pydantic import BaseModel

    class M(BaseModel):
        amount: Decimal = Decimal("0.00")

    tree = build_form_tree(M, existing={"amount": Decimal("0.00")})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "amount", "value": "19.99"}
    )
    assert result.ok is True
    assert tree.root.find("amount").value == Decimal("19.99")


def test_dispatch_set_value_uuid_coerces_string() -> None:
    from uuid import UUID

    from pydantic import BaseModel

    class M(BaseModel):
        id: UUID = UUID("11111111-1111-1111-1111-111111111111")

    tree = build_form_tree(
        M, existing={"id": UUID("11111111-1111-1111-1111-111111111111")}
    )
    new_value = "22222222-2222-2222-2222-222222222222"
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "id", "value": new_value}
    )
    assert result.ok is True
    assert tree.root.find("id").value == UUID(new_value)


def test_dispatch_set_value_bytes_coerces_hex_string() -> None:
    from pydantic import BaseModel

    class M(BaseModel):
        blob: bytes = b""

    tree = build_form_tree(M, existing={"blob": b""})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "blob", "value": "deadbeef"}
    )
    assert result.ok is True
    assert tree.root.find("blob").value == b"\xde\xad\xbe\xef"


def test_dispatch_set_value_secret_bytes_coerces_utf8_string() -> None:
    from pydantic import BaseModel, SecretBytes

    class M(BaseModel):
        key: SecretBytes = SecretBytes(b"")

    tree = build_form_tree(M, existing={"key": SecretBytes(b"")})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "key", "value": "p4ssw0rd"}
    )
    assert result.ok is True
    assert tree.root.find("key").value == b"p4ssw0rd"


def test_dispatch_set_value_secret_str_passes_through_unchanged() -> None:
    """SecretStr nodes accept str on the wire (secret_kind == 'str');
    coercion must NOT encode to bytes."""
    from pydantic import BaseModel, SecretStr

    class M(BaseModel):
        password: SecretStr = SecretStr("")

    tree = build_form_tree(M, existing={"password": SecretStr("")})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "password", "value": "letmein"}
    )
    assert result.ok is True
    assert tree.root.find("password").value == "letmein"


def test_dispatch_set_value_malformed_iso_returns_validation_failure() -> None:
    """If the wire string is unparseable, coercion swallows the error
    and validate_value rejects via the canonical 'expected X' message —
    not via a raised exception leaking out of dispatch_mutation."""
    from datetime import date

    from pydantic import BaseModel

    class M(BaseModel):
        d: date = date(2020, 1, 1)

    tree = build_form_tree(M, existing={"d": date(2020, 1, 1)})
    result = dispatch_mutation(
        tree, {"op": "set_value", "path": "d", "value": "not-a-date"}
    )
    assert result.ok is False
    assert tree.root.find("d").value == date(2020, 1, 1)   # unchanged
