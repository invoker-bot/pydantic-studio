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
