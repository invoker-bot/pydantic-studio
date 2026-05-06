"""Regression tests for the four Phase-2 follow-up fixes shipped in Plan 3."""

from __future__ import annotations

import pytest

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import WithDict, WithList, WithSet


class TestSnapshotOrderingHoist:
    """When resolve fails, no spurious snapshot should be pushed."""

    def test_add_item_with_unresolvable_item_type(self) -> None:
        tree = build_form_tree(WithList)
        # Corrupt the SequenceNode's stored item-type name so resolve raises.
        tags = tree.root.find("tags")
        assert tags is not None
        tags.item_type_name = "nosuch.module.Type"

        snapshots_before = len(tree.snapshots)
        with pytest.raises(ValueError, match=r"not in sys\.modules"):
            tree.add_item("tags", "x")
        assert len(tree.snapshots) == snapshots_before, (
            "snapshot pushed even though resolve raised — undo state is now polluted"
        )

    def test_insert_item_with_unresolvable_item_type(self) -> None:
        tree = build_form_tree(WithList)
        tags = tree.root.find("tags")
        assert tags is not None
        tags.item_type_name = "nosuch.module.Type"
        snapshots_before = len(tree.snapshots)
        with pytest.raises(ValueError, match=r"not in sys\.modules"):
            tree.insert_item("tags", 0, "x")
        assert len(tree.snapshots) == snapshots_before

    def test_add_entry_with_unresolvable_key_type(self) -> None:
        tree = build_form_tree(WithDict)
        settings = tree.root.find("settings")
        assert settings is not None
        settings.key_type_name = "nosuch.module.Type"
        snapshots_before = len(tree.snapshots)
        with pytest.raises(ValueError, match=r"not in sys\.modules"):
            tree.add_entry("settings", "k", 1)
        assert len(tree.snapshots) == snapshots_before

    def test_select_variant_with_unresolvable_variant(self) -> None:
        # WithUnion is `int | str`, which is demoted to int via UnionBuilder
        # because Pydantic's smart-union narrows it. We need an actual
        # multi-variant union for this test — build one inline.
        from pydantic import BaseModel

        from tests.fixtures.schemas import Address

        class TwoVariants(BaseModel):
            v: Address | int = 0

        t2 = build_form_tree(TwoVariants)
        union = t2.root.find("v")
        assert union is not None
        # Corrupt the second variant so resolve raises.
        union.variant_type_names = [union.variant_type_names[0], "nosuch.module.Type"]
        snapshots_before = len(t2.snapshots)
        with pytest.raises(ValueError, match=r"not in sys\.modules"):
            t2.select_variant("v", 1)
        assert len(t2.snapshots) == snapshots_before


class TestUnionPreSelectViaModelValidate:
    """When a union has a BaseModel variant and existing is a dict that
    matches its schema, the variant should be pre-selected — not left blank."""

    def test_dict_matches_basemodel_variant(self) -> None:
        from pydantic import BaseModel

        from tests.fixtures.schemas import Address

        class HasUnion(BaseModel):
            target: Address | int = 0

        # Pass a dict that validly populates Address; UnionBuilder should
        # detect this via model_validate and pre-select the Address variant.
        tree = build_form_tree(HasUnion, existing={"target": {"street": "X", "city": "Y"}})
        union = tree.root.find("target")
        assert union is not None
        assert union.selected_index == 0, (
            f"expected Address variant (index 0) pre-selected, got {union.selected_index}"
        )
        assert union.selected is not None
        assert union.selected.kind == "group"

    def test_int_still_picks_int_variant(self) -> None:
        from pydantic import BaseModel

        from tests.fixtures.schemas import Address

        class HasUnion(BaseModel):
            target: Address | int = 0

        tree = build_form_tree(HasUnion, existing={"target": 42})
        union = tree.root.find("target")
        assert union is not None
        assert union.selected_index == 1, "expected int variant (index 1)"
        assert union.selected is not None
        assert union.selected.kind == "int"
        assert union.selected.value == 42


class TestBuildItemsIsinstanceGuard:
    """`_build_items` should reject non-sequence existing values cleanly."""

    def test_string_existing_is_rejected(self) -> None:
        """A bare string is iterable but iterating yields chars — almost
        always a user mistake. Reject loudly."""
        with pytest.raises(TypeError, match="expected list/tuple/set"):
            build_form_tree(WithList, existing={"tags": "abc"})

    def test_int_existing_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="expected list/tuple/set"):
            build_form_tree(WithList, existing={"tags": 42})

    def test_dict_existing_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="expected list/tuple/set"):
            build_form_tree(WithList, existing={"tags": {"a": 1}})

    def test_list_existing_accepted(self) -> None:
        """Regression: valid input must still work after the guard lands."""
        tree = build_form_tree(WithList, existing={"tags": ["a", "b"]})
        tags = tree.root.find("tags")
        assert tags is not None
        assert len(tags.items) == 2

    def test_set_existing_accepted(self) -> None:
        tree = build_form_tree(WithSet, existing={"flags": {"a", "b"}})
        flags = tree.root.find("flags")
        assert flags is not None
        assert len(flags.items) == 2
