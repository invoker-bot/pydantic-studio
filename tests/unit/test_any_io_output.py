from __future__ import annotations

import json
import tomllib
from typing import Any

from pydantic import BaseModel

from pydantic_studio import build_form_tree, load_yaml


class _AnyConfig(BaseModel):
    payload: Any = None


class _OpaqueValue:
    def __str__(self) -> str:
        return "opaque-value"


def _tree_with_opaque_any():
    return build_form_tree(_AnyConfig, existing={"payload": _OpaqueValue()})


def test_save_json_serializes_non_json_native_any_value(tmp_path) -> None:
    from pydantic_studio.io.json_ import save_json

    out = tmp_path / "config.json"

    save_json(_tree_with_opaque_any(), out)

    assert json.loads(out.read_text(encoding="utf-8")) == {"payload": "opaque-value"}


def test_save_yaml_serializes_non_json_native_any_value(tmp_path) -> None:
    from pydantic_studio.io.yaml import save_yaml

    out = tmp_path / "config.yaml"

    save_yaml(_tree_with_opaque_any(), out)

    assert load_yaml(out, _AnyConfig).to_instance().payload == "opaque-value"


def test_save_toml_serializes_non_json_native_any_value(tmp_path) -> None:
    from pydantic_studio.io.toml import save_toml

    out = tmp_path / "config.toml"

    save_toml(_tree_with_opaque_any(), out)

    assert tomllib.loads(out.read_text(encoding="utf-8")) == {"payload": "opaque-value"}
