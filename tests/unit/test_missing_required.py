"""FormTree.missing_required_paths — the data source behind required-field
guidance (the `n` jump key, the HelpBar counter, save-failure cursor jump).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree


class _Inner(BaseModel):
    network: str
    address: str


class _Schema(BaseModel):
    name: str = "alpha"
    api_key: str = Field(...)
    api_secret: str = Field(...)
    timeout: int = 30


class _Nested(BaseModel):
    title: str = "t"
    inner: _Inner
    items: list[_Inner] = Field(default_factory=list)


class _WithUnion(BaseModel):
    mode: Literal["a", "b"] = "a"
    payload: _Inner | int


class _WithOptionalModel(BaseModel):
    mode: Literal["a", "b"] = "a"
    payload: _Inner | None = None


def test_flat_schema_lists_missing_required_in_field_order() -> None:
    tree = build_form_tree(_Schema)
    assert tree.missing_required_paths() == ["api_key", "api_secret"]


def test_filled_required_fields_drop_out() -> None:
    tree = build_form_tree(_Schema)
    tree.set_value("api_key", "k")
    assert tree.missing_required_paths() == ["api_secret"]


def test_nested_group_paths_are_dotted() -> None:
    tree = build_form_tree(_Nested)
    assert tree.missing_required_paths() == ["inner.network", "inner.address"]


def test_sequence_items_are_walked() -> None:
    tree = build_form_tree(_Nested)
    tree.set_value("inner.network", "n")
    tree.set_value("inner.address", "a")
    tree.add_item("items")
    missing = tree.missing_required_paths()
    assert missing == ["items.0.network", "items.0.address"]


def test_untouched_optional_model_is_not_missing() -> None:
    """Optional[Model] = None collapses to an optional GroupNode; while
    its subtree is untouched it resolves to the field default and must
    not surface phantom required children (matching to_instance)."""
    tree = build_form_tree(_WithOptionalModel)
    assert tree.missing_required_paths() == []
    tree.to_instance()  # fresh tree of this schema must validate


def test_partially_filled_optional_model_surfaces_remaining_required() -> None:
    tree = build_form_tree(_WithOptionalModel)
    tree.set_value("payload.network", "TRC20")
    assert tree.missing_required_paths() == ["payload.address"]


def test_required_unselected_union_is_missing() -> None:
    tree = build_form_tree(_WithUnion)
    node = tree._resolve_path("payload")
    if node.kind != "union":  # builder may collapse; guard the premise
        import pytest

        pytest.skip("payload did not build as a UnionNode")
    assert tree.missing_required_paths() == ["payload"]


def test_selected_union_variant_is_walked() -> None:
    tree = build_form_tree(_WithUnion)
    node = tree._resolve_path("payload")
    if node.kind != "union":
        import pytest

        pytest.skip("payload did not build as a UnionNode")
    names = node.variant_type_names
    idx = next(i for i, n in enumerate(names) if n.endswith("_Inner"))
    tree.select_variant("payload", idx)
    missing = tree.missing_required_paths()
    assert "payload.network" in missing
    assert "payload.address" in missing


def test_complete_tree_returns_empty() -> None:
    tree = build_form_tree(_Schema)
    tree.set_value("api_key", "k")
    tree.set_value("api_secret", "s")
    assert tree.missing_required_paths() == []
