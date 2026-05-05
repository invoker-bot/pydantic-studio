"""Sample BaseModels used across unit tests."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Simple(BaseModel):
    """Flat schema with one of each primitive type."""

    name: str = Field(description="The thing's name")
    age: int = Field(default=0, ge=0, description="Age in years")
    height: float = 1.7
    enabled: bool = True
    balance: Decimal = Decimal("0.00")


class Address(BaseModel):
    street: str
    city: str


class Person(BaseModel):
    name: str
    address: Address  # nested BaseModel


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class WithColor(BaseModel):
    # NOTE(T14): an ``accent: Color | None = None`` field will be added
    # in T14 once UnionBuilder handles Optional. Don't add it earlier.
    favorite: Color = Color.BLUE


LogLevel = Literal["debug", "info", "warn", "error"]


class WithLogLevel(BaseModel):
    level: LogLevel = "info"
    severity: Literal[1, 2, 3] = 2


class WithList(BaseModel):
    tags: list[str] = []
    counts: list[int] = []


class WithSet(BaseModel):
    flags: set[str] = set()


class WithTuple(BaseModel):
    coords: tuple[int, ...] = ()


class WithFixedTuple(BaseModel):
    rgb: tuple[int, int, int] = (0, 0, 0)
    pair: tuple[str, int] = ("k", 0)


class WithDict(BaseModel):
    settings: dict[str, int] = {}
    labels: dict[str, str] = {}
