"""Format I/O for pydantic-studio."""

from __future__ import annotations

from pydantic_studio.io.dispatch import (
    format_for_path,
    load_config,
    save_config,
    supported_extensions,
    supported_formats,
)
from pydantic_studio.io.json_ import load_json, save_json
from pydantic_studio.io.toml import load_toml, save_toml
from pydantic_studio.io.yaml import load_yaml, save_yaml
from pydantic_studio.io.yaml_draft import save_draft_yaml

__all__ = [
    "format_for_path",
    "load_config",
    "load_json",
    "load_toml",
    "load_yaml",
    "save_config",
    "save_draft_yaml",
    "save_json",
    "save_toml",
    "save_yaml",
    "supported_extensions",
    "supported_formats",
]
