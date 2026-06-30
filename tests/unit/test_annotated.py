"""Type-detection predicates and Annotated unwrapping for the dispatch layer."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, Field

from pydantic_studio.types.annotated import (
    get_optional_inner,
    get_union_args,
    is_enum_type,
    is_literal_type,
    is_optional_type,
    is_pydantic_model,
    is_union_type,
    strip_annotated,
)


class Color(Enum):
    RED = "red"
    BLUE = "blue"


class Inner(BaseModel):
    x: int = 0


def test_strip_annotated_unwraps_metadata() -> None:
    typ = Annotated[int, Field(ge=0)]
    assert strip_annotated(typ) is int


def test_strip_annotated_passes_through_plain_types() -> None:
    assert strip_annotated(int) is int
    assert strip_annotated(str) is str


def test_is_union_type_detects_pep604_and_typing_union() -> None:
    assert is_union_type(int | str) is True
    from typing import Union  # testing the legacy typing.Union form
    assert is_union_type(Union[int, str]) is True  # noqa: UP007
    assert is_union_type(int) is False


def test_is_optional_type_detects_t_or_none() -> None:
    assert is_optional_type(int | None) is True
    assert is_optional_type(int | str | None) is True
    assert is_optional_type(int | str) is False  # union but no None
    assert is_optional_type(int) is False


def test_get_optional_inner_strips_none() -> None:
    assert get_optional_inner(int | None) is int
    # Multi-variant Optional: returns the union of remaining members,
    # preserving original order.
    inner = get_optional_inner(int | str | None)
    assert get_union_args(inner) == (int, str)


def test_get_optional_inner_returns_input_when_not_optional() -> None:
    assert get_optional_inner(int) is int


def test_is_literal_type() -> None:
    assert is_literal_type(Literal["a", "b"]) is True
    assert is_literal_type(int) is False


def test_is_enum_type() -> None:
    assert is_enum_type(Color) is True
    assert is_enum_type(int) is False


def test_is_pydantic_model() -> None:
    assert is_pydantic_model(Inner) is True
    assert is_pydantic_model(int) is False
    assert is_pydantic_model("not a class") is False


def test_predicates_unwrap_annotated() -> None:
    assert is_literal_type(Annotated[Literal["a", "b"], "meta"]) is True
    assert is_enum_type(Annotated[Color, "meta"]) is True
    assert is_pydantic_model(Annotated[Inner, "meta"]) is True


def test_fq_strips_annotated_for_round_trip() -> None:
    """Regression (Sentry hft-python #15 — ``NoBuilderError: typing.Annotated``):
    ``_fq`` must encode an ``Annotated[T, ...]`` variant/element type as T's
    fully-qualified name. A union variant typed ``Annotated[T, ...]`` (e.g.
    Pydantic's ``StrictBool == Annotated[bool, Strict()]``) otherwise collapsed
    to the bare ``typing.Annotated`` (the inner type lost), and
    ``_resolve_type_name`` rebuilt the builder-less special form — so
    ``select_variant`` raised NoBuilderError at registry lookup. Metadata can't
    survive string serialization anyway, and every builder strips Annotated
    internally, so the round-trippable name is the *inner* type's name.
    """
    from pydantic import StrictBool

    from pydantic_studio.tree.nodes import _resolve_type_name
    from pydantic_studio.types.utils import _fq

    assert _fq(StrictBool) == "builtins.bool"
    assert _resolve_type_name(_fq(StrictBool)) is bool
    assert _fq(Annotated[int, Field(ge=0)]) == "builtins.int"
    assert _resolve_type_name(_fq(Annotated[int, Field(ge=0)])) is int
    # plain (non-Annotated) types are unaffected by the strip.
    assert _fq(str) == "builtins.str"
    assert _fq(Inner) == f"{Inner.__module__}.{Inner.__qualname__}"
    # Annotated wrapping a Literal still round-trips the parametrized Literal
    # (the strip composes with the Literal JSON encoding).
    assert _resolve_type_name(_fq(Annotated[Literal["x", "y"], Field()])) == Literal["x", "y"]


def test_fq_round_trips_union_type_names() -> None:
    from pydantic_studio.tree.nodes import _resolve_type_name
    from pydantic_studio.types.utils import _fq

    encoded = _fq(str | Inner)

    assert encoded.startswith("typing.Union[")
    assert _resolve_type_name(encoded) == str | Inner


def test_fq_round_trips_parameterized_container_type_names() -> None:
    from pydantic_studio.tree.nodes import _resolve_type_name
    from pydantic_studio.types.utils import _fq

    assert _resolve_type_name(_fq(list[int])) == list[int]
    assert _resolve_type_name(_fq(dict[str, int])) == dict[str, int]
    assert _resolve_type_name(_fq(set[int])) == set[int]
    assert _resolve_type_name(_fq(tuple[int, str])) == tuple[int, str]
    assert _resolve_type_name(_fq(tuple[int, ...])) == tuple[int, ...]


@pytest.mark.parametrize(
    "encoded",
    [
        "typing.List[123]",
        "typing.Dict[\"builtins.str\", 123]",
        "typing.Tuple[123]",
        "typing.Union[123]",
    ],
)
def test_resolve_type_name_rejects_non_string_structural_type_names(
    encoded: str,
) -> None:
    from pydantic_studio.tree.nodes import _resolve_type_name

    with pytest.raises(ValueError, match="type name"):
        _resolve_type_name(encoded)
