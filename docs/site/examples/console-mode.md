# Example: Console Prompt Mode

Console mode is the default `edit` frontend. It is useful over SSH, in plain
terminals, and when a full-screen TUI or browser is unnecessary.

```bash
$ pydantic-studio edit mypkg.config:ConsoleSettings settings.yaml
Editing ConsoleSettings
service [worker]: api
port [8080]: 9090
debug [false]: y
level (debug/info/warn) [info]: warn
saved to settings.yaml
```

Blank answers keep the value shown in brackets. Invalid input is rejected and
the same prompt is shown again:

```bash
port [8080]: abc
cannot parse 'abc' as int
port [8080]: 9090
```

## Run The Example

The repository includes a small console-focused example:

```bash
$ uv run python examples/05_console_prompts.py
$ uv run python examples/05_console_prompts.py console
```

Both commands ask one question per field and save to `ConsoleSettings.yaml`.
The same schema can still be opened with the other frontends:

```bash
$ uv run python examples/05_console_prompts.py tui
$ uv run python examples/05_console_prompts.py web
```

## Schema

```python
from typing import Literal

from pydantic import BaseModel, Field


class ConsoleSettings(BaseModel):
    service: str = Field(default="worker", description="Service name")
    port: int = Field(default=8080, ge=1, le=65535, description="Listen port")
    debug: bool = Field(default=False, description="Enable debug logging")
    level: Literal["debug", "info", "warn"] = Field(default="info")
```
