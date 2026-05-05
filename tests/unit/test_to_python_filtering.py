"""Recursive None filtering in GroupNode.to_python and FormTree.to_instance."""

from __future__ import annotations

from pydantic import BaseModel

from pydantic_studio import build_form_tree


class Inner(BaseModel):
    a: int = 7
    b: str = "default-b"


class Outer(BaseModel):
    name: str = "n"
    inner: Inner = Inner()


def test_nested_none_dropped_for_default_to_apply() -> None:
    tree = build_form_tree(Outer)
    # Nothing was filled in: every leaf is None.
    out = tree.root.to_python()
    # Top-level None dropped (was already true in Phase 1).
    assert "name" not in out
    # The nested group's all-None children produce an empty dict, which is
    # itself NOT None and therefore not filtered. Pydantic treats {} as
    # "use all of Inner's defaults", so this is the correct serialization.
    assert "inner" in out
    assert out["inner"] == {}


def test_nested_to_instance_applies_defaults() -> None:
    tree = build_form_tree(Outer)
    instance = tree.to_instance()
    assert instance.name == "n"
    assert instance.inner.a == 7
    assert instance.inner.b == "default-b"


def test_nested_partially_filled() -> None:
    tree = build_form_tree(Outer, existing={"inner": {"a": 99}})
    out = tree.root.to_python()
    assert out["inner"] == {"a": 99}  # b is None and is filtered
    instance = tree.to_instance()
    assert instance.inner.a == 99
    assert instance.inner.b == "default-b"  # default applied
