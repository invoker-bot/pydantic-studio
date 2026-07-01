"""Recursive defaults and None filtering in GroupNode/FormTree materialization."""

from __future__ import annotations

from pydantic import BaseModel

from pydantic_studio import build_form_tree


class Inner(BaseModel):
    a: int = 7
    b: str = "default-b"


class Outer(BaseModel):
    name: str = "n"
    inner: Inner = Inner()


class NullableDefaults(BaseModel):
    nickname: str | None = "guest"


def test_nested_defaults_are_materialized() -> None:
    tree = build_form_tree(Outer)
    out = tree.root.to_python()
    assert out == {"name": "n", "inner": {"a": 7, "b": "default-b"}}


def test_nested_to_instance_applies_defaults() -> None:
    tree = build_form_tree(Outer)
    instance = tree.to_instance()
    assert instance.name == "n"
    assert instance.inner.a == 7
    assert instance.inner.b == "default-b"


def test_nested_partially_filled() -> None:
    tree = build_form_tree(Outer, existing={"inner": {"a": 99}})
    out = tree.root.to_python()
    assert out["inner"] == {"a": 99, "b": "default-b"}
    instance = tree.to_instance()
    assert instance.inner.a == 99
    assert instance.inner.b == "default-b"


def test_set_value_none_overrides_nullable_scalar_default() -> None:
    tree = build_form_tree(NullableDefaults)

    result = tree.set_value("nickname", None)

    assert result.ok is True
    assert tree.to_python()["nickname"] is None
    assert tree.to_instance().nickname is None


def test_existing_none_overrides_nullable_scalar_default() -> None:
    tree = build_form_tree(NullableDefaults, existing={"nickname": None})

    assert tree.to_python()["nickname"] is None
    assert tree.to_instance().nickname is None
