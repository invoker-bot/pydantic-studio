"""extract_constraints: pull annotated_types / pydantic constraints from a FieldInfo."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.types.metadata import extract_constraints


class StrSchema(BaseModel):
    name: str = Field(min_length=2, max_length=10, pattern=r"^[A-Z]")


class IntSchema(BaseModel):
    age: int = Field(ge=0, le=120, multiple_of=1)
    count: int = Field(gt=0, lt=100)


class FloatSchema(BaseModel):
    ratio: float = Field(ge=0.0, le=1.0)


class DecimalSchema(BaseModel):
    price: Decimal = Field(max_digits=10, decimal_places=2, ge=Decimal("0"))


def test_extract_string_constraints() -> None:
    finfo = StrSchema.model_fields["name"]
    c = extract_constraints(finfo)
    assert c["min_length"] == 2
    assert c["max_length"] == 10
    assert c["pattern"] == r"^[A-Z]"


def test_extract_int_constraints_inclusive() -> None:
    finfo = IntSchema.model_fields["age"]
    c = extract_constraints(finfo)
    assert c["ge"] == 0
    assert c["le"] == 120
    assert c["multiple_of"] == 1


def test_extract_int_constraints_exclusive() -> None:
    finfo = IntSchema.model_fields["count"]
    c = extract_constraints(finfo)
    assert c["gt"] == 0
    assert c["lt"] == 100


def test_extract_float_constraints() -> None:
    finfo = FloatSchema.model_fields["ratio"]
    c = extract_constraints(finfo)
    assert c["ge"] == 0.0
    assert c["le"] == 1.0


def test_extract_decimal_constraints() -> None:
    finfo = DecimalSchema.model_fields["price"]
    c = extract_constraints(finfo)
    assert c["max_digits"] == 10
    assert c["decimal_places"] == 2
    assert c["ge"] == Decimal("0")


def test_string_node_carries_constraints_after_build() -> None:
    tree = build_form_tree(StrSchema)
    name = tree.root.find("name")
    assert name is not None
    assert name.min_length == 2
    assert name.max_length == 10
    assert name.pattern == r"^[A-Z]"


def test_int_node_carries_constraints_after_build() -> None:
    tree = build_form_tree(IntSchema)
    age = tree.root.find("age")
    assert age is not None
    assert age.ge == 0
    assert age.le == 120
    assert age.multiple_of == 1


def test_constrained_int_type_works_via_metadata() -> None:
    """Pydantic v2's ``conint`` desugars to Annotated[int, Interval(...)],
    so the metadata extractor handles it transparently."""
    from pydantic import conint

    class S(BaseModel):
        n: conint(ge=5, le=10)  # type: ignore[valid-type]

    tree = build_form_tree(S)
    n = tree.root.find("n")
    assert n is not None
    assert n.ge == 5
    assert n.le == 10


def test_annotated_constraints_via_annotated_types() -> None:
    """Direct Annotated[int, Ge(5)] should also work."""
    from annotated_types import Ge, Le

    class S(BaseModel):
        n: Annotated[int, Ge(5), Le(10)]

    tree = build_form_tree(S)
    n = tree.root.find("n")
    assert n is not None
    assert n.ge == 5
    assert n.le == 10


def test_zero_boundary_values_extract_correctly() -> None:
    """The is-not-None guard must not collapse zero (a falsy but valid bound)."""
    from annotated_types import Ge, Le, MinLen

    class IntZero(BaseModel):
        n: Annotated[int, Ge(0), Le(0)]

    class StrZero(BaseModel):
        s: Annotated[str, MinLen(0)]

    c = extract_constraints(IntZero.model_fields["n"])
    assert c["ge"] == 0
    assert c["le"] == 0

    c2 = extract_constraints(StrZero.model_fields["s"])
    assert c2["min_length"] == 0


def test_duplicate_keys_last_one_wins() -> None:
    """Documented behavior: when two metadata items set the same key,
    the later item's value wins (dict assignment order)."""
    from annotated_types import Ge

    class S(BaseModel):
        n: Annotated[int, Ge(5), Ge(10)]

    c = extract_constraints(S.model_fields["n"])
    assert c["ge"] == 10  # second Ge wins


def test_decimal_gt_lt_constraints_carry_into_node() -> None:
    """DecimalNode now has gt/lt fields — verify the wiring."""
    from decimal import Decimal

    class S(BaseModel):
        price: Decimal = Field(gt=Decimal("0"), lt=Decimal("1000"))

    tree = build_form_tree(S)
    price = tree.root.find("price")
    assert price is not None
    assert price.gt == Decimal("0")
    assert price.lt == Decimal("1000")
