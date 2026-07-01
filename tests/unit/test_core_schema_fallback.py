"""Tests for ``CoreSchemaFallbackBuilder`` — honouring custom types
declared via ``__get_pydantic_core_schema__`` (issue #1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import core_schema

if TYPE_CHECKING:
    from uuid import UUID

from pydantic_studio.exceptions import NoBuilderError
from pydantic_studio.tree.builder import build_form_tree
from pydantic_studio.tree.nodes import (
    DateNode,
    DecimalNode,
    FloatNode,
    GroupNode,
    IntNode,
    LiteralNode,
    MappingNode,
    SequenceNode,
    StringNode,
    UnionNode,
    UuidNode,
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


class BoundedString:
    """Wraps ``str`` with min/max length and a regex pattern."""

    def __init__(self, value: str) -> None:
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(min_length=3, max_length=12, pattern=r"^[a-z]+$"),
        )

    @classmethod
    def _validate(cls, value: Any) -> BoundedString:
        return value if isinstance(value, cls) else cls(value)


class RangedFloat:
    """Wraps ``float`` with ge/le/multiple_of."""

    def __init__(self, value: float) -> None:
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.float_schema(ge=-1.0, le=1.0, multiple_of=0.1),
        )

    @classmethod
    def _validate(cls, value: Any) -> RangedFloat:
        return value if isinstance(value, cls) else cls(value)


class FiniteCoreFloat:
    """Wraps ``float`` with allow_inf_nan disabled in core schema."""

    def __init__(self, value: float) -> None:
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.float_schema(allow_inf_nan=False),
        )

    @classmethod
    def _validate(cls, value: Any) -> FiniteCoreFloat:
        return value if isinstance(value, cls) else cls(value)


class SmallList:
    """Wraps ``list[str]`` with min/max length on the container."""

    def __init__(self, items: list[str]) -> None:
        self.items = list(items)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_wrap_validator_function(
            cls._validate_wrap,
            core_schema.list_schema(
                core_schema.str_schema(), min_length=1, max_length=4
            ),
        )

    @classmethod
    def _validate_wrap(cls, value: Any, handler) -> SmallList:
        return value if isinstance(value, cls) else cls(handler(value))


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
    class M(BaseModel):
        n: BoundedInt

    tree = build_form_tree(M)
    n_node = next(c for c in tree.root.fields if c.name == "n")
    assert isinstance(n_node, IntNode)


def test_bounded_int_propagates_ge_constraint():
    class M(BaseModel):
        n: BoundedInt

    tree = build_form_tree(M)
    n_node = next(c for c in tree.root.fields if c.name == "n")
    assert n_node.ge == 0


def test_bounded_string_propagates_length_and_pattern():
    class M(BaseModel):
        s: BoundedString

    tree = build_form_tree(M)
    s_node = next(c for c in tree.root.fields if c.name == "s")
    assert isinstance(s_node, StringNode)
    assert s_node.min_length == 3
    assert s_node.max_length == 12
    assert s_node.pattern == r"^[a-z]+$"


def test_ranged_float_propagates_ge_le_multiple_of():
    class M(BaseModel):
        v: RangedFloat

    tree = build_form_tree(M)
    v_node = next(c for c in tree.root.fields if c.name == "v")
    assert isinstance(v_node, FloatNode)
    assert v_node.ge == -1.0
    assert v_node.le == 1.0
    assert v_node.multiple_of == 0.1


def test_core_schema_float_propagates_allow_inf_nan_constraint():
    class M(BaseModel):
        v: FiniteCoreFloat

    tree = build_form_tree(M)
    v_node = next(c for c in tree.root.fields if c.name == "v")
    assert isinstance(v_node, FloatNode)
    assert v_node.allow_inf_nan is False


def test_small_list_propagates_container_length_constraints():
    class M(BaseModel):
        items: SmallList = SmallList(["seed"])

    tree = build_form_tree(M, existing={"items": ["x"]})
    items_node = next(c for c in tree.root.fields if c.name == "items")
    assert isinstance(items_node, SequenceNode)
    assert items_node.min_length == 1
    assert items_node.max_length == 4


def test_user_metadata_overrides_schema_constraint():
    """Schema-derived constraints are *defaults* — when the user adds
    their own ``Annotated[Custom, Ge(...)]``, the user-supplied value
    wins (last-item-wins in ``extract_constraints``)."""
    from typing import Annotated

    from annotated_types import Ge

    class M(BaseModel):
        n: Annotated[BoundedInt, Ge(10)]

    tree = build_form_tree(M)
    n_node = next(c for c in tree.root.fields if c.name == "n")
    assert n_node.ge == 10


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


# ---------- extended schema kinds: temporal, uuid, literal, union, decimal ----------


class Timestamp:
    """Wraps ``date``."""

    def __init__(self, value: date) -> None:
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.date_schema(),
        )

    @classmethod
    def _validate(cls, value: Any) -> Timestamp:
        return value if isinstance(value, cls) else cls(value)


class RequestId:
    """Wraps ``UUID``."""

    def __init__(self, value: UUID) -> None:
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.uuid_schema(),
        )

    @classmethod
    def _validate(cls, value: Any) -> RequestId:
        return value if isinstance(value, cls) else cls(value)


class Status:
    """Wraps ``Literal['active', 'paused', 'archived']`` — domain enum-like
    type that carries methods on top of a constrained string."""

    def __init__(self, value: str) -> None:
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.literal_schema(["active", "paused", "archived"]),
        )

    @classmethod
    def _validate(cls, value: Any) -> Status:
        return value if isinstance(value, cls) else cls(value)


class MaybeNum:
    """Wraps ``Union[str, int]`` — value that may be either text or a
    numeric ID."""

    def __init__(self, value: Any) -> None:
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.union_schema(
                [core_schema.str_schema(), core_schema.int_schema()]
            ),
        )

    @classmethod
    def _validate(cls, value: Any) -> MaybeNum:
        return value if isinstance(value, cls) else cls(value)


class Money:
    """Wraps ``Decimal`` with max_digits / decimal_places / ge constraints."""

    def __init__(self, value: Decimal) -> None:
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _src: Any, _h: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.decimal_schema(max_digits=10, decimal_places=2, ge=0),
        )

    @classmethod
    def _validate(cls, value: Any) -> Money:
        return value if isinstance(value, cls) else cls(Decimal(value))


def test_timestamp_resolves_to_date_node():
    class M(BaseModel):
        when: Timestamp

    tree = build_form_tree(M, existing={"when": date(2026, 5, 7)})
    when_node = next(c for c in tree.root.fields if c.name == "when")
    assert isinstance(when_node, DateNode)


def test_request_id_resolves_to_uuid_node():
    class M(BaseModel):
        rid: RequestId

    tree = build_form_tree(M)
    rid_node = next(c for c in tree.root.fields if c.name == "rid")
    assert isinstance(rid_node, UuidNode)


def test_status_resolves_to_literal_node_with_choices():
    class M(BaseModel):
        s: Status

    tree = build_form_tree(M)
    s_node = next(c for c in tree.root.fields if c.name == "s")
    assert isinstance(s_node, LiteralNode)
    assert s_node.choices == ["active", "paused", "archived"]


def test_status_round_trip_reconstructs_custom_class():
    class M(BaseModel):
        s: Status

    tree = build_form_tree(M)
    tree.set_value("s", "active")
    inst = tree.to_instance()
    assert isinstance(inst.s, Status)
    assert inst.s.value == "active"


def test_maybe_num_resolves_to_union_node():
    class M(BaseModel):
        v: MaybeNum

    tree = build_form_tree(M)
    v_node = next(c for c in tree.root.fields if c.name == "v")
    assert isinstance(v_node, UnionNode)
    # Order in the schema's choices list is preserved.
    assert any("str" in n for n in v_node.variant_type_names)
    assert any("int" in n for n in v_node.variant_type_names)


def test_money_propagates_decimal_constraints():
    class M(BaseModel):
        amount: Money

    tree = build_form_tree(M)
    amount_node = next(c for c in tree.root.fields if c.name == "amount")
    assert isinstance(amount_node, DecimalNode)
    assert amount_node.max_digits == 10
    assert amount_node.decimal_places == 2
    assert amount_node.ge == 0


def test_custom_type_instance_as_default_strips_to_none():
    """When a user passes a custom-type instance as the field default
    (``when: Timestamp = Timestamp(date(...))``), the underlying scalar
    builder cannot validate the wrapper against ``DateNode(default=...)``.
    The fallback strips the default rather than crashing — the form
    still builds with default=None, and ``required`` reflects that the
    user *did* supply a default originally."""

    class M(BaseModel):
        when: Timestamp = Timestamp(date(2026, 1, 1))

    tree = build_form_tree(M)
    when_node = next(c for c in tree.root.fields if c.name == "when")
    assert isinstance(when_node, DateNode)
    assert when_node.default is None
    # User supplied a default → field is not required, even though we
    # stripped the un-unwrappable value.
    assert when_node.required is False
