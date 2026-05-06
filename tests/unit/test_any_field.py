"""Tests for ``typing.Any`` support — issue #2.

``Any`` and containers parameterised over it (``dict[str, Any]``,
``list[Any]``) build an ``AnyValueNode`` that holds the value as-is
and exposes a runtime ``mode`` discriminator so renderers can pick a
widget. Round-trip is direct because Pydantic's ``Any`` does no
validation on the return path.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import AnyValueNode, MappingNode, SequenceNode


def test_bare_any_field_with_no_value_builds_null_mode_node():
    class M(BaseModel):
        payload: Any = None

    tree = build_form_tree(M)
    payload_node = next(c for c in tree.root.fields if c.name == "payload")
    assert isinstance(payload_node, AnyValueNode)
    assert payload_node.mode == "null"
    assert payload_node.value is None


def test_any_field_infers_str_mode_from_default():
    class M(BaseModel):
        payload: Any = "hello"

    tree = build_form_tree(M)
    payload_node = next(c for c in tree.root.fields if c.name == "payload")
    assert payload_node.mode == "str"
    assert payload_node.value == "hello"


def test_any_field_infers_int_mode_from_existing():
    class M(BaseModel):
        payload: Any

    tree = build_form_tree(M, existing={"payload": 42})
    payload_node = next(c for c in tree.root.fields if c.name == "payload")
    assert payload_node.mode == "int"
    assert payload_node.value == 42


def test_any_field_distinguishes_bool_from_int():
    """Order matters: ``bool`` is an ``int`` subclass in Python, so the
    inference must check ``bool`` first."""

    class M(BaseModel):
        payload: Any

    tree = build_form_tree(M, existing={"payload": True})
    payload_node = next(c for c in tree.root.fields if c.name == "payload")
    assert payload_node.mode == "bool"
    assert payload_node.value is True


def test_any_field_infers_list_mode_holding_value_opaquely():
    class M(BaseModel):
        payload: Any

    tree = build_form_tree(M, existing={"payload": [1, "two", 3.0]})
    payload_node = next(c for c in tree.root.fields if c.name == "payload")
    assert payload_node.mode == "list"
    assert payload_node.value == [1, "two", 3.0]


def test_any_field_round_trips_nested_dict_through_to_instance():
    class M(BaseModel):
        payload: Any

    tree = build_form_tree(M, existing={"payload": {"a": 1, "b": [True, False]}})
    inst = tree.to_instance()
    assert inst.payload == {"a": 1, "b": [True, False]}


def test_dict_str_any_builds_mapping_with_per_entry_modes():
    class M(BaseModel):
        params: dict[str, Any] = {}

    tree = build_form_tree(
        M,
        existing={"params": {"k1": "s", "k2": 7, "k3": [1, 2]}},
    )
    params_node = next(c for c in tree.root.fields if c.name == "params")
    assert isinstance(params_node, MappingNode)
    assert len(params_node.entries) == 3
    modes = sorted(v.mode for _, v in params_node.entries)
    assert modes == ["int", "list", "str"]


def test_dict_str_any_round_trips_heterogeneous_values():
    class M(BaseModel):
        params: dict[str, Any] = {}

    payload = {"k1": "s", "k2": 7, "k3": [1, 2]}
    tree = build_form_tree(M, existing={"params": payload})
    inst = tree.to_instance()
    assert inst.params == payload


def test_list_any_builds_sequence_with_per_item_modes():
    class M(BaseModel):
        items: list[Any] = []

    tree = build_form_tree(
        M, existing={"items": ["x", 42, [1, 2], {"k": "v"}]}
    )
    items_node = next(c for c in tree.root.fields if c.name == "items")
    assert isinstance(items_node, SequenceNode)
    modes = [item.mode for item in items_node.items]
    assert modes == ["str", "int", "list", "dict"]


def test_list_any_round_trips_heterogeneous_items():
    class M(BaseModel):
        items: list[Any] = []

    payload = ["x", 42, [1, 2], {"k": "v"}]
    tree = build_form_tree(M, existing={"items": payload})
    inst = tree.to_instance()
    assert inst.items == payload


def test_any_value_node_set_value_accepts_any_type_and_resyncs_mode():
    """``tree.set_value`` on an AnyValueNode replaces the value and the
    node's mode auto-syncs via ``validate_assignment``-driven model
    validator — so the renderer always sees a mode that matches what
    the field actually holds."""

    class M(BaseModel):
        payload: Any

    tree = build_form_tree(M, existing={"payload": "initial"})
    result = tree.set_value("payload", 42)
    assert result.ok
    payload_node = next(c for c in tree.root.fields if c.name == "payload")
    assert payload_node.value == 42
    assert payload_node.mode == "int"


class _SnapshotModel(BaseModel):
    """Module-level model for the JSON round-trip test — GroupNode's
    schema_class deserializer looks classes up from ``sys.modules``,
    so the model has to live at module scope, not inside a test fn."""

    params: dict[str, Any] = {}


def test_any_field_round_trip_through_json_snapshot():
    """Snapshots persist AnyValueNode through JSON. Primitives survive
    losslessly; the discriminated union picks the right node back via
    ``kind`` on reload. Mirrors the dump+context pattern used by
    ``tree.draft.save_draft`` / ``load_draft``."""
    from pydantic_studio.tree.nodes import FormTree

    payload = {"k1": "abc", "k2": 99, "k3": True, "k4": [1, 2, 3]}
    tree = build_form_tree(_SnapshotModel, existing={"params": payload})
    raw = tree.model_dump_json(exclude={"schema_class"})
    restored = FormTree.model_validate_json(
        raw, context={"schema_class": _SnapshotModel}
    )
    inst = restored.to_instance()
    assert inst.params == payload
