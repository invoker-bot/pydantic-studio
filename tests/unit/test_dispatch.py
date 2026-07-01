"""Tests for the format-dispatch load_config / save_config helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pydantic_studio import build_form_tree
from pydantic_studio.io.dispatch import format_for_path, load_config, save_config
from tests.fixtures.schemas import Server

if TYPE_CHECKING:
    from pathlib import Path


class TestFormatForPath:
    def test_io_package_reexports_format_helpers(self) -> None:
        from pathlib import Path

        import pydantic_studio.io as io_api

        assert io_api.format_for_path(Path("x.yaml")) == "yaml"
        assert io_api.supported_extensions() == (".json", ".toml", ".yaml", ".yml")

    def test_uses_public_format_helper_only(self) -> None:
        import pydantic_studio.io.dispatch as dispatch_module

        assert dispatch_module.format_for_path is format_for_path
        assert not hasattr(dispatch_module, "_format_for_path")

    def test_yaml(self) -> None:
        from pathlib import Path

        assert format_for_path(Path("x.yaml")) == "yaml"
        assert format_for_path(Path("x.yml")) == "yaml"

    def test_toml(self) -> None:
        from pathlib import Path

        assert format_for_path(Path("x.toml")) == "toml"

    def test_json(self) -> None:
        from pathlib import Path

        assert format_for_path(Path("x.json")) == "json"

    def test_unknown_extension_raises(self) -> None:
        from pathlib import Path

        with pytest.raises(ValueError, match="cannot infer format"):
            format_for_path(Path("x.xml"))


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

    def test_save_rejects_unknown_explicit_format(self, tmp_path: Path) -> None:
        tree = build_form_tree(Server)

        with pytest.raises(ValueError, match="unsupported format"):
            save_config(tree, tmp_path / "config", format="xml")

    def test_load_rejects_unknown_explicit_format(self, tmp_path: Path) -> None:
        src = tmp_path / "config.json"
        src.write_text("{}", encoding="utf-8")

        with pytest.raises(ValueError, match="unsupported format"):
            load_config(src, Server, format="xml")
