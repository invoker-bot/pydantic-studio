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


class TestNoneTypeNameRoundTrip:
    """Containers whose item annotation is None should rebuild NoneBuilder
    children through the persisted item_type_name."""

    def test_add_item_to_list_of_none(self) -> None:
        from pydantic import BaseModel

        class HasNulls(BaseModel):
            nulls: list[None] = []

        tree = build_form_tree(HasNulls)

        result = tree.add_item("nulls")

        assert result.ok is True, result.errors
        nulls = tree.root.find("nulls")
        assert nulls is not None
        assert len(nulls.items) == 1
        assert nulls.items[0].kind == "any"
        assert nulls.items[0].mode == "null"
        assert nulls.items[0].to_python() is None


class TestNestedSeedValidation:
    """Seeded structural mutations should fail cleanly before mutating."""

    def test_add_item_rejects_invalid_nested_sequence_seed(self) -> None:
        from pydantic import BaseModel

        class HasNestedLists(BaseModel):
            rows: list[list[int]] = []

        tree = build_form_tree(HasNestedLists)
        snapshots_before = len(tree.snapshots)

        result = tree.add_item("rows", ["not-an-int"])

        assert result.ok is False
        assert result.errors
        rows = tree.root.find("rows")
        assert rows is not None
        assert rows.items == []
        assert len(tree.snapshots) == snapshots_before

    def test_insert_item_rejects_invalid_nested_sequence_seed(self) -> None:
        from pydantic import BaseModel

        class HasNestedLists(BaseModel):
            rows: list[list[int]] = []

        tree = build_form_tree(HasNestedLists)
        snapshots_before = len(tree.snapshots)

        result = tree.insert_item("rows", 0, ["not-an-int"])

        assert result.ok is False
        assert result.errors
        rows = tree.root.find("rows")
        assert rows is not None
        assert rows.items == []
        assert len(tree.snapshots) == snapshots_before

    def test_add_entry_rejects_invalid_nested_key_seed(self) -> None:
        from pydantic import BaseModel

        class HasNestedKeys(BaseModel):
            values: dict[tuple[int, int], str] = {}

        tree = build_form_tree(HasNestedKeys)
        snapshots_before = len(tree.snapshots)

        result = tree.add_entry("values", ("not-an-int", 1), "value")

        assert result.ok is False
        assert result.errors
        values = tree.root.find("values")
        assert values is not None
        assert values.entries == []
        assert len(tree.snapshots) == snapshots_before

    def test_rename_key_rejects_invalid_nested_key_seed(self) -> None:
        from pydantic import BaseModel

        class HasNestedKeys(BaseModel):
            values: dict[tuple[int, int], str] = {}

        tree = build_form_tree(HasNestedKeys, existing={"values": {(1, 2): "ok"}})
        snapshots_before = len(tree.snapshots)

        result = tree.rename_key("values", 0, ("not-an-int", 2))

        assert result.ok is False
        assert result.errors
        values = tree.root.find("values")
        assert values is not None
        assert values.to_python() == {(1, 2): "ok"}
        assert len(tree.snapshots) == snapshots_before

    def test_add_entry_rejects_invalid_nested_value_seed(self) -> None:
        from pydantic import BaseModel

        class HasNestedValues(BaseModel):
            values: dict[str, list[int]] = {}

        tree = build_form_tree(HasNestedValues)
        snapshots_before = len(tree.snapshots)

        result = tree.add_entry("values", "bad", ["not-an-int"])

        assert result.ok is False
        assert result.errors
        values = tree.root.find("values")
        assert values is not None
        assert values.entries == []
        assert len(tree.snapshots) == snapshots_before


class TestItemLevelSetValue:
    """set_value should accept paths into sequence items and mapping entries."""

    def test_set_list_item_by_index(self) -> None:
        tree = build_form_tree(WithList, existing={"tags": ["alpha", "beta"]})
        result = tree.set_value("tags[0]", "ALPHA")
        assert result.ok, f"expected ok, got errors {result.errors}"
        tags = tree.root.find("tags")
        assert tags is not None
        assert tags.items[0].value == "ALPHA"
        assert tags.items[1].value == "beta"

    def test_set_list_item_validation_failure_keeps_old_value(self) -> None:
        tree = build_form_tree(WithList, existing={"tags": ["alpha"]})
        result = tree.set_value("tags[0]", 123)  # int into string slot
        assert not result.ok
        tags = tree.root.find("tags")
        assert tags is not None
        assert tags.items[0].value == "alpha", "old value must survive failed set"

    def test_set_list_item_out_of_range(self) -> None:
        tree = build_form_tree(WithList, existing={"tags": ["x"]})
        with pytest.raises(KeyError, match="index 5"):
            tree.set_value("tags[5]", "y")

    def test_set_nested_list_item(self) -> None:
        from pydantic import BaseModel

        class Server(BaseModel):
            host: str = "localhost"
            port: int = 8080

        class Cluster(BaseModel):
            replicas: list[Server] = []

        tree = build_form_tree(
            Cluster, existing={"replicas": [{"host": "h1"}, {"host": "h2"}]}
        )
        result = tree.set_value("replicas[1].host", "newhost")
        assert result.ok
        replicas = tree.root.find("replicas")
        assert replicas is not None
        # replicas[1] is a GroupNode; navigate to find its host child.
        server_1 = replicas.items[1]
        from pydantic_studio import GroupNode
        assert isinstance(server_1, GroupNode)
        host = server_1.find("host")
        assert host is not None
        assert host.value == "newhost"

    def test_set_mapping_value_by_key_index(self) -> None:
        tree = build_form_tree(WithDict, existing={"settings": {"port": 80, "rps": 100}})
        # MappingNode entries use integer indices — entry [0] is ("port", 80),
        # [1] is ("rps", 100). set_value targets the value side.
        result = tree.set_value("settings[1]", 200)
        assert result.ok
        settings = tree.root.find("settings")
        assert settings is not None
        _k, v_node = settings.entries[1]
        assert v_node.value == 200

    def test_set_value_pushes_snapshot_for_undo(self) -> None:
        tree = build_form_tree(WithList, existing={"tags": ["a"]})
        snapshots_before = len(tree.snapshots)
        tree.set_value("tags[0]", "A")
        assert len(tree.snapshots) == snapshots_before + 1
        # Undo restores previous value.
        assert tree.undo()
        tags_after_undo = tree.root.find("tags")
        assert tags_after_undo is not None
        assert tags_after_undo.items[0].value == "a"
