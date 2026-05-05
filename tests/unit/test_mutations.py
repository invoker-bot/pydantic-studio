from __future__ import annotations

import pytest

from pydantic_studio.tree.builder import build_form_tree
from tests.fixtures.schemas import Person, Simple


def test_set_value_sets_a_top_level_field():
    tree = build_form_tree(Simple)
    tree.set_value("name", "dave")
    assert tree.root.find("name").value == "dave"


def test_set_value_sets_a_nested_field():
    tree = build_form_tree(Person)
    tree.set_value("address.city", "Springfield")
    addr = tree.root.find("address")
    assert addr.find("city").value == "Springfield"


def test_set_value_pushes_a_snapshot():
    tree = build_form_tree(Simple)
    assert len(tree.snapshots) == 0
    tree.set_value("name", "x")
    assert len(tree.snapshots) == 1
    tree.set_value("name", "y")
    assert len(tree.snapshots) == 2


def test_set_value_unknown_path_raises():
    tree = build_form_tree(Simple)
    with pytest.raises(KeyError, match="no_such_field"):
        tree.set_value("no_such_field", "x")


def test_set_value_through_nonexistent_parent_raises():
    tree = build_form_tree(Person)
    with pytest.raises(KeyError, match="ghost"):
        tree.set_value("ghost.city", "x")


def test_undo_restores_previous_value():
    tree = build_form_tree(Simple)
    tree.set_value("name", "first")
    tree.set_value("name", "second")
    assert tree.root.find("name").value == "second"
    assert tree.undo() is True
    assert tree.root.find("name").value == "first"


def test_undo_to_initial_state():
    tree = build_form_tree(Simple)
    tree.set_value("name", "x")
    assert tree.undo() is True
    # Initial state had value=None for name.
    assert tree.root.find("name").value is None


def test_undo_returns_false_when_nothing_to_undo():
    tree = build_form_tree(Simple)
    assert tree.undo() is False


def test_redo_returns_false_when_nothing_to_redo():
    tree = build_form_tree(Simple)
    assert tree.redo() is False


def test_redo_after_undo_restores():
    tree = build_form_tree(Simple)
    tree.set_value("name", "alpha")
    tree.set_value("name", "beta")
    tree.undo()
    tree.undo()
    tree.redo()
    assert tree.root.find("name").value == "alpha"
    tree.redo()
    assert tree.root.find("name").value == "beta"


def test_set_after_undo_drops_redo_tail():
    tree = build_form_tree(Simple)
    tree.set_value("name", "a")
    tree.set_value("name", "b")
    tree.undo()  # back to "a"
    tree.set_value("name", "c")  # should drop the "b" snapshot from redo tail
    assert tree.redo() is False  # no redo available
    assert tree.root.find("name").value == "c"


def test_snapshot_buffer_evicts_oldest():
    tree = build_form_tree(Simple)
    tree.snapshot_limit = 3
    for i in range(5):
        tree.set_value("name", f"v{i}")
    # 5 mutations but limit=3 → only 3 most recent snapshots kept.
    assert len(tree.snapshots) == 3
    # The earliest accessible state should be the one captured before "v2".
    while tree.undo():
        pass
    # We've undone everything we can. The earliest reachable name is "v1"
    # (the value before "v2" was assigned), since the snapshot taken before
    # "v0" was evicted.
    assert tree.root.find("name").value == "v1"


def test_snapshot_limit_default_is_50():
    tree = build_form_tree(Simple)
    assert tree.snapshot_limit == 50
