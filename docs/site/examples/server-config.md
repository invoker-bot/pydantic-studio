# Example: Server config

A schema with nested BaseModels, a list of replicas, an enum, and a
secret.

```python
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, SecretStr


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class Replica(BaseModel):
    host: str = Field(description="Replica hostname or IP")
    port: int = Field(default=5432, description="Replica port")


class Database(BaseModel):
    primary: Replica = Field(description="Primary database replica")
    read_replicas: list[Replica] = Field(
        default_factory=list,
        description="Read-only replicas for query offload",
    )
    password: SecretStr = Field(description="Connection password")


class Logging(BaseModel):
    level: LogLevel = Field(default=LogLevel.INFO, description="Log verbosity")
    format: Literal["json", "text"] = Field(default="text", description="Log format")


class ServerConfig(BaseModel):
    name: str = Field(description="Service identifier")
    api_url: HttpUrl = Field(description="Upstream API endpoint")
    database: Database
    logging: Logging = Field(default_factory=Logging)
```

## Generate a stub

```bash
$ pydantic-studio fill mypkg.server:ServerConfig --out server.yaml
```

```yaml
# Service identifier
name: '?'
# Upstream API endpoint
api_url: '?'
database:
  primary:
    # Replica hostname or IP
    host: '?'
    # Replica port
    port: 5432
  # Read-only replicas for query offload
  read_replicas: []
  # Connection password
  password: '?'
logging:
  # Log verbosity
  level: info
  # Log format
  format: text
```

(Required fields without defaults appear as the string `?`; YAML quotes it so
the generated stub remains parseable while you fill it in.)

## Edit interactively

```bash
$ pydantic-studio edit mypkg.server:ServerConfig server.yaml
```

The default console mode asks one prompt per field. If you want a visual
hierarchy, use one of the richer frontends:

```bash
$ pydantic-studio edit --frontend tui mypkg.server:ServerConfig server.yaml
$ pydantic-studio edit --frontend web mypkg.server:ServerConfig server.yaml
```

The TUI/web hierarchy shows:

- ServerConfig
  - database
  - logging

Focus a group to edit its fields. Add replicas through the `read_replicas`
container controls.

## Validate

```bash
$ pydantic-studio check mypkg.server:ServerConfig server.yaml
server.yaml: OK
```
