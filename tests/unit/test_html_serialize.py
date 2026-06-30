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


class _AnyHolder(BaseModel):
    payload: Any = None


class _VariantEmail(BaseModel):
    address: str = "ops@example.com"


class _VariantSlack(BaseModel):
    channel: str = "#ops"


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


def test_dispatch_add_entry_rejects_null_key_without_mutating() -> None:
    tree = build_form_tree(_WithDict, existing={"env": {"TZ": "UTC"}})
    result = dispatch_mutation(tree, {"op": "add_entry", "path": "env", "key": None})

    assert result.ok is False
    assert any("key must be a string" in err for err in result.errors)
    pairs = [(k.value, v.value) for k, v in tree.root.find("env").entries]
    assert pairs == [("TZ", "UTC")]


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
