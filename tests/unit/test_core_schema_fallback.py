"""Tests for ``CoreSchemaFallbackBuilder`` — honouring custom types
declared via ``__get_pydantic_core_schema__`` (issue #1)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import core_schema

from pydantic_studio.exceptions import NoBuilderError
from pydantic_studio.tree.builder import build_form_tree
from pydantic_studio.tree.nodes import (
    GroupNode,
    IntNode,
    MappingNode,
    SequenceNode,
    StringNode,
)

# ---------- helper custom types ----------


class StringRef:
    """Wraps a string; declares itself as ``str`` to Pydantic."""

    def __init__(self, name: str) -> None:
        self.name = name

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: v.name if isinstance(v, StringRef) else v,
                info_arg=False,
            ),
        )

    @classmethod
    def _validate(cls, value: Any) -> StringRef:
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(value)
        raise TypeError(value)


class StringRefList:
    """Wraps ``list[str]``; uses wrap-validator semantics."""

    def __init__(self, items: list[str]) -> None:
        self.items = list(items)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_wrap_validator_function(
            cls._validate_wrap,
            core_schema.list_schema(core_schema.str_schema()),
        )

    @classmethod
    def _validate_wrap(cls, value: Any, handler) -> StringRefList:
        if isinstance(value, cls):
            return value
        return cls(handler(value))


class StrToStrMap:
    """Wraps ``dict[str, str]``."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = dict(mapping)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_wrap_validator_function(
            cls._validate_wrap,
            core_schema.dict_schema(
                core_schema.str_schema(), core_schema.str_schema()
            ),
        )

    @classmethod
    def _validate_wrap(cls, value: Any, handler) -> StrToStrMap:
        if isinstance(value, cls):
            return value
        return cls(handler(value))


class BoundedInt:
    """Wraps ``int`` with a ge=0 constraint."""

    def __init__(self, value: int) -> None:
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.int_schema(ge=0),
        )

    @classmethod
    def _validate(cls, value: Any) -> BoundedInt:
        return value if isinstance(value, cls) else cls(value)


class OpaqueValue:
    """Declares only a ``function-plain`` schema — no inner schema for
    pydantic-studio to introspect, so fallback should pass it through."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(lambda v: v)


# ---------- forward dispatch ----------


def test_string_ref_field_builds_string_node():
    class M(BaseModel):
        name: StringRef

    tree = build_form_tree(M)
    assert isinstance(tree.root, GroupNode)
    name_node = next(c for c in tree.root.fields if c.name == "name")
    assert isinstance(name_node, StringNode)


def test_string_ref_list_field_builds_sequence_node():
    class M(BaseModel):
        items: StringRefList = StringRefList([])

    tree = build_form_tree(M, existing={"items": ["a", "b", "c"]})
    items_node = next(c for c in tree.root.fields if c.name == "items")
    assert isinstance(items_node, SequenceNode)
    assert items_node.origin == "list"
    assert len(items_node.items) == 3
    assert all(isinstance(child, StringNode) for child in items_node.items)


def test_str_to_str_map_field_builds_mapping_node():
    class M(BaseModel):
        m: StrToStrMap = StrToStrMap({})

    tree = build_form_tree(M, existing={"m": {"x": "1", "y": "2"}})
    m_node = next(c for c in tree.root.fields if c.name == "m")
    assert isinstance(m_node, MappingNode)
    assert len(m_node.entries) == 2


def test_bounded_int_resolves_to_int_node():
    """A custom int-wrapping type builds an IntNode (constraint
    passthrough from core_schema → field_info is a follow-up — see
    `xfail` test below)."""

    class M(BaseModel):
        n: BoundedInt

    tree = build_form_tree(M)
    n_node = next(c for c in tree.root.fields if c.name == "n")
    assert isinstance(n_node, IntNode)


@pytest.mark.xfail(
    reason="constraints declared in a custom type's core_schema "
    "(e.g. int_schema(ge=0)) don't yet propagate into the resulting "
    "node. Follow-up to issue #1.",
    strict=True,
)
def test_bounded_int_propagates_ge_constraint():
    class M(BaseModel):
        n: BoundedInt

    tree = build_form_tree(M)
    n_node = next(c for c in tree.root.fields if c.name == "n")
    assert n_node.ge == 0


# ---------- round-trip ----------


def test_string_ref_round_trip_reconstructs_custom_class():
    class M(BaseModel):
        name: StringRef

    tree = build_form_tree(M)
    tree.set_value("name", "alice")
    inst = tree.to_instance()
    assert isinstance(inst.name, StringRef)
    assert inst.name.name == "alice"


def test_str_to_str_map_round_trip_reconstructs_custom_class():
    class M(BaseModel):
        tags: StrToStrMap

    tree = build_form_tree(M, existing={"tags": {"env": "prod"}})
    inst = tree.to_instance()
    assert isinstance(inst.tags, StrToStrMap)
    assert inst.tags.mapping == {"env": "prod"}


def test_load_yaml_then_save_round_trip(tmp_path):
    """End-to-end: read existing YAML containing a custom-typed field,
    edit nothing, validate via ``to_instance``. Exercises ``load_yaml``,
    the fallback dispatch, and Pydantic's reconstruction in one path."""
    from pydantic_studio.io.yaml import load_yaml

    class M(BaseModel):
        where: StringRef
        tags: StrToStrMap

    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        "where: prod\ntags:\n  env: prod\n  region: eu-west-1\n",
        encoding="utf-8",
    )

    tree = load_yaml(yaml_path, M)
    inst = tree.to_instance()
    assert isinstance(inst.where, StringRef)
    assert inst.where.name == "prod"
    assert isinstance(inst.tags, StrToStrMap)
    assert inst.tags.mapping == {
        "env": "prod",
        "region": "eu-west-1",
    }


# ---------- negative space ----------


def test_function_plain_schema_raises_no_builder_error():
    """``function-plain`` schemas have no inner schema; the fallback must
    fail open so genuinely unsupported types remain visible to the user."""

    class M(BaseModel):
        x: OpaqueValue

        model_config = {"arbitrary_types_allowed": True}

    with pytest.raises(NoBuilderError):
        build_form_tree(M)


def test_basemodel_subclass_still_uses_group_builder():
    """The fallback's ``matches`` excludes BaseModel — verify nested
    BaseModel fields still build as GroupNodes."""

    class Inner(BaseModel):
        v: str = "x"

    class Outer(BaseModel):
        inner: Inner = Inner()

    tree = build_form_tree(Outer)
    inner_node = next(c for c in tree.root.fields if c.name == "inner")
    assert isinstance(inner_node, GroupNode)
