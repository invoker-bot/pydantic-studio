"""Example 2 — Nested BaseModels, Enum, Literal, SecretStr, HttpUrl, list.

The canonical config-file shape: groups of fields, a sub-model in a
list, a masked credential, an Enum drop-down, a Literal choice, and a
URL. The TUI sidebar mirrors the GroupNode hierarchy; the web renderer
collapses each group into a section.

Run with::

    python examples/02_server_config.py             # default: console prompts
    python examples/02_server_config.py console     # console prompts
    python examples/02_server_config.py tui         # Textual terminal UI
    python examples/02_server_config.py web         # browser UI
    python examples/02_server_config.py show        # print form tree
    python examples/02_server_config.py fill        # print YAML stub
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from _runner import run_demo
from pydantic import BaseModel, Field, HttpUrl, SecretStr


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class Replica(BaseModel):
    host: str = Field(description="Replica hostname or IP")
    port: int = Field(default=5432, description="Replica port", ge=1, le=65535)


class Database(BaseModel):
    primary: Replica = Field(description="Primary replica")
    read_replicas: list[Replica] = Field(
        default_factory=list,
        description="Read-only replicas for query offload",
    )
    password: SecretStr = Field(description="Connection password (masked)")


class Logging(BaseModel):
    level: LogLevel = Field(default=LogLevel.INFO, description="Log verbosity")
    format: Literal["json", "text"] = Field(default="text", description="Log format")


class ServerConfig(BaseModel):
    name: str = Field(description="Service identifier", min_length=1)
    api_url: HttpUrl = Field(description="Upstream API endpoint")
    database: Database = Field(description="Database connection")
    logging: Logging = Field(default_factory=Logging, description="Logging policy")


if __name__ == "__main__":
    run_demo(
        ServerConfig,
        existing={
            "name": "billing-api",
            "api_url": "https://api.example.com/v1",
            "database": {
                "primary": {"host": "db-primary.internal", "port": 5432},
                "read_replicas": [
                    {"host": "db-replica-1.internal", "port": 5432},
                    {"host": "db-replica-2.internal", "port": 5432},
                ],
                "password": "s3cret-do-not-share",
            },
            "logging": {"level": LogLevel.WARN, "format": "json"},
        },
    )
