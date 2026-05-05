"""Sample BaseModels used across unit tests."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

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
    favorite: Color = Color.BLUE
