"""Tests for the format-dispatch load_config / save_config helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pydantic_studio import build_form_tree
from pydantic_studio.io.dispatch import _format_for_path, load_config, save_config
from tests.fixtures.schemas import Server

if TYPE_CHECKING:
    from pathlib import Path


class TestFormatForPath:
    def test_yaml(self) -> None:
        from pathlib import Path

        assert _format_for_path(Path("x.yaml")) == "yaml"
        assert _format_for_path(Path("x.yml")) == "yaml"

    def test_toml(self) -> None:
        from pathlib import Path

        assert _format_for_path(Path("x.toml")) == "toml"

    def test_json(self) -> None:
        from pathlib import Path

        assert _format_for_path(Path("x.json")) == "json"

    def test_unknown_extension_raises(self) -> None:
        from pathlib import Path

        with pytest.raises(ValueError, match="cannot infer format"):
            _format_for_path(Path("x.xml"))


class TestDispatcher:
    def test_save_load_yaml(self, tmp_path: Path) -> None:
        out = tmp_path / "x.yaml"
        tree = build_form_tree(Server)
        save_config(tree, out)
        reloaded = load_config(out, Server)
        assert reloaded.to_instance().name == "prod"

    def test_save_load_toml(self, tmp_path: Path) -> None:
        out = tmp_path / "x.toml"
        tree = build_form_tree(Server)
        save_config(tree, out)
        reloaded = load_config(out, Server)
        assert reloaded.to_instance().name == "prod"

    def test_save_load_json(self, tmp_path: Path) -> None:
        out = tmp_path / "x.json"
        tree = build_form_tree(Server)
        save_config(tree, out)
        reloaded = load_config(out, Server)
        assert reloaded.to_instance().name == "prod"

    def test_explicit_format_override(self, tmp_path: Path) -> None:
        out = tmp_path / "config"  # no extension
        tree = build_form_tree(Server)
        save_config(tree, out, format="yaml")
        reloaded = load_config(out, Server, format="yaml")
        assert reloaded.to_instance().name == "prod"
