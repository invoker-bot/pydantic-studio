"""Sample BaseModels used across unit tests."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from ipaddress import IPv4Address, IPv6Network
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl, SecretBytes, SecretStr


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
    accent: Color | None = None


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


class WithUnion(BaseModel):
    value: int | str = 0


class WithOptional(BaseModel):
    nickname: str | None = None
    age: int | None = None


class Server(BaseModel):
    """Minimal schema with descriptions for YAML golden tests."""

    name: str = Field(default="prod", description="Service identifier")
    port: int = Field(default=8080, description="Listening port", ge=1, le=65535)
    debug: bool = Field(default=False, description="Enable debug logging")


class Phase3Sink(BaseModel):
    """Kitchen-sink schema covering every Plan 3 type. Defaults exercise
    the build path; Phase-3 smoke tests mutate one field at a time and
    confirm round-trip through ``to_instance``."""

    # Temporal
    when: datetime = datetime(2026, 5, 6, 12, 0)
    on: date = date(2026, 5, 6)
    at: time = time(9, 30)
    interval: timedelta = timedelta(seconds=30)

    # Network
    bind: IPv4Address = IPv4Address("127.0.0.1")
    allow: IPv6Network = IPv6Network("fe80::/64")
    api: HttpUrl = HttpUrl("https://api.example.com")
    contact: EmailStr = "ops@example.com"

    # Special
    home: Path = Path("/home/user")
    request_id: UUID = UUID("00000000-0000-0000-0000-000000000000")
    api_key: SecretStr = SecretStr("default-key")
    token: SecretBytes = SecretBytes(b"default-token")
    name_re: re.Pattern[str] = re.compile(r"^[a-z]+$")
    blob: bytes = b"\x00\x01\x02"
