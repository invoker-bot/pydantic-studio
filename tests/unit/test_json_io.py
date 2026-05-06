"""Tests for JSON I/O — load + save."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import Server

if TYPE_CHECKING:
    from pathlib import Path


class TestLoadJson:
    def test_load_basic_file(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import load_json

        src = tmp_path / "config.json"
        src.write_text(
            '{"name": "prod", "port": 8080, "debug": true}\n',
            encoding="utf-8",
        )
        tree = load_json(src, Server)
        instance = tree.to_instance()
        assert instance.name == "prod"
        assert instance.port == 8080
        assert instance.debug is True

    def test_load_empty_object_yields_defaults(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import load_json

        src = tmp_path / "empty.json"
        src.write_text("{}", encoding="utf-8")
        tree = load_json(src, Server)
        instance = tree.to_instance()
        assert instance.name == "prod"

    def test_load_unknown_field_dropped(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import load_json

        src = tmp_path / "config.json"
        src.write_text(
            '{"name": "prod", "port": 8080, "extra": "ignored"}',
            encoding="utf-8",
        )
        tree = load_json(src, Server)
        assert {f.name for f in tree.root.fields} == {"name", "port", "debug"}


class TestSaveJson:
    def test_save_creates_file_with_values(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import save_json

        out = tmp_path / "out.json"
        tree = build_form_tree(Server)
        save_json(tree, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "prod" in content
        assert "8080" in content

    def test_save_round_trip(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import load_json, save_json

        tree = build_form_tree(Server)
        tree.set_value("port", 9090)
        out = tmp_path / "out.json"
        save_json(tree, out)
        reloaded = load_json(out, Server)
        instance = reloaded.to_instance()
        assert instance.port == 9090

    def test_save_uses_indent_two(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import save_json

        out = tmp_path / "out.json"
        tree = build_form_tree(Server)
        save_json(tree, out)
        content = out.read_text(encoding="utf-8")
        assert "\n  " in content
