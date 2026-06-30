"""Tests for JSON I/O — load + save."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, Field

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

    def test_load_rejects_non_finite_numbers(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import load_json

        class FloatConfig(BaseModel):
            value: float = 0.0

        for constant in ("NaN", "Infinity", "-Infinity"):
            src = tmp_path / f"{constant}.json"
            src.write_text(f'{{"value": {constant}}}', encoding="utf-8")

            with pytest.raises(ValueError, match="non-finite JSON constant"):
                load_json(src, FloatConfig)


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

    def test_save_rejects_non_finite_numbers(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import save_json

        class FloatConfig(BaseModel):
            value: float = float("nan")

        with pytest.raises(ValueError, match="JSON compliant"):
            save_json(build_form_tree(FloatConfig), tmp_path / "out.json")

    def test_save_uses_field_aliases(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import save_json

        class AliasConfig(BaseModel):
            api_key: str = Field(default="secret", alias="api-key")

        out = tmp_path / "out.json"
        tree = build_form_tree(AliasConfig)
        save_json(tree, out)
        content = out.read_text(encoding="utf-8")
        assert '"api-key": "secret"' in content
        assert "api_key" not in content

    def test_save_preserves_edited_alias_field_value(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import save_json

        class AliasConfig(BaseModel):
            api_key: str = Field(default="secret", alias="api-key")

        out = tmp_path / "out.json"
        tree = build_form_tree(AliasConfig)
        result = tree.set_value("api_key", "rotated")
        assert result.ok is True
        save_json(tree, out)

        content = out.read_text(encoding="utf-8")
        assert '"api-key": "rotated"' in content

    def test_save_alias_field_round_trips_through_load(self, tmp_path: Path) -> None:
        from pydantic_studio.io.json_ import load_json, save_json

        class AliasConfig(BaseModel):
            api_key: str = Field(default="secret", alias="api-key")

        out = tmp_path / "out.json"
        tree = build_form_tree(AliasConfig)
        result = tree.set_value("api_key", "rotated")
        assert result.ok is True
        save_json(tree, out)

        reloaded = load_json(out, AliasConfig)

        assert reloaded.to_instance().api_key == "rotated"
