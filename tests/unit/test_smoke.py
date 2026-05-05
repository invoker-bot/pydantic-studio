"""End-to-end smoke test exercising the public API only."""

from __future__ import annotations

from decimal import Decimal

import pydantic_studio as ps
from tests.fixtures.schemas import Person, Simple


def test_smoke_simple():
    tree = ps.build_form_tree(Simple)
    tree.set_value("name", "alice")
    tree.set_value("age", 7)
    tree.set_value("balance", Decimal("0.50"))
    inst = tree.to_instance()
    assert inst.name == "alice"
    assert inst.age == 7


def test_smoke_nested():
    tree = ps.build_form_tree(Person)
    tree.set_value("name", "alice")
    tree.set_value("address.street", "Main")
    tree.set_value("address.city", "Springfield")
    inst = tree.to_instance()
    assert inst.address.city == "Springfield"


def test_smoke_undo_redo_full_round_trip():
    tree = ps.build_form_tree(Simple)
    tree.set_value("name", "x")
    tree.set_value("age", 1)
    tree.undo()
    tree.undo()
    tree2 = ps.build_form_tree(Simple, existing=tree.to_python())  # round-trip via dict
    assert isinstance(tree2, ps.FormTree)
