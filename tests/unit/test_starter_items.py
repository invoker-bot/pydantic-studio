"""Regression tests for the four Phase-2 follow-up fixes shipped in Plan 3."""

from __future__ import annotations

import pytest

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import WithDict, WithList, WithUnion


class TestSnapshotOrderingHoist:
    """When resolve fails, no spurious snapshot should be pushed."""

    def test_add_item_with_unresolvable_item_type(self, monkeypatch) -> None:
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
        tree = build_form_tree(WithUnion)
        value_node = tree.root.find("value")
        assert value_node is not None
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
