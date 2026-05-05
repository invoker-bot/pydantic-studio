"""Type-detection predicates and Annotated unwrapping for the dispatch layer."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

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
