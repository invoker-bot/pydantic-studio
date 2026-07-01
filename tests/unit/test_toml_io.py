"""Tests for TOML I/O — load + save."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import Server, WithOptional

if TYPE_CHECKING:
    from pathlib import Path


class TestLoadToml:
    def test_load_basic_file(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml

        src = tmp_path / "config.toml"
        src.write_text(
            'name = "prod"\n'
            "port = 8080\n"
            "debug = true\n",
            encoding="utf-8",
        )
        tree = load_toml(src, Server)
        instance = tree.to_instance()
        assert instance.name == "prod"
        assert instance.port == 8080
        assert instance.debug is True

    def test_load_empty_file_yields_defaults(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml

        src = tmp_path / "empty.toml"
        src.write_text("", encoding="utf-8")
        tree = load_toml(src, Server)
        instance = tree.to_instance()
        assert instance.name == "prod"

    def test_load_unknown_field_dropped(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml

        src = tmp_path / "config.toml"
        src.write_text(
            'name = "prod"\n'
            "port = 8080\n"
            'unknown_field = "ignored"\n',
            encoding="utf-8",
        )
        tree = load_toml(src, Server)
        assert {f.name for f in tree.root.fields} == {"name", "port", "debug"}

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml

        with pytest.raises(FileNotFoundError):
            load_toml(tmp_path / "nope.toml", Server)


class TestSaveToml:
    def test_save_uses_field_aliases(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml, save_toml

        class AliasConfig(BaseModel):
            api_key: str = Field(default="secret", alias="api-key")

        out = tmp_path / "alias.toml"
        tree = build_form_tree(AliasConfig)
        result = tree.set_value("api_key", "rotated")
        assert result.ok is True

        save_toml(tree, out)

        content = out.read_text(encoding="utf-8")
        assert "api-key" in content
        assert "api_key" not in content
        assert "rotated" in content
        assert load_toml(out, AliasConfig).to_instance().api_key == "rotated"

    def test_save_creates_file_with_values(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import save_toml

        out = tmp_path / "out.toml"
        tree = build_form_tree(Server)
        save_toml(tree, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "prod" in content
        assert "8080" in content

    def test_save_round_trip(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import load_toml, save_toml

        tree = build_form_tree(Server)
        tree.set_value("port", 9090)
        out = tmp_path / "out.toml"
        save_toml(tree, out)
        reloaded = load_toml(out, Server)
        instance = reloaded.to_instance()
        assert instance.port == 9090

    def test_save_emits_description_comments(self, tmp_path: Path) -> None:
        from pydantic_studio.io.toml import save_toml

        out = tmp_path / "out.toml"
        tree = build_form_tree(Server)
        save_toml(tree, out)
        content = out.read_text(encoding="utf-8")
        assert "Service identifier" in content
        assert "Listening port" in content

    def test_save_omits_none_values_that_toml_cannot_represent(
        self, tmp_path: Path
    ) -> None:
        from pydantic_studio.io.toml import load_toml, save_toml

        out = tmp_path / "optional.toml"
        tree = build_form_tree(WithOptional)
        save_toml(tree, out)

        content = out.read_text(encoding="utf-8")
        assert "nickname" not in content
        assert "age" not in content
        reloaded = load_toml(out, WithOptional).to_instance()
        assert reloaded.nickname is None
        assert reloaded.age is None

    def test_save_omits_none_values_inside_optional_nested_model(
        self, tmp_path: Path
    ) -> None:
        from pydantic_studio.io.toml import load_toml, save_toml

        class OptionalInner(BaseModel):
            enabled: bool = True
            note: str | None = None

        class OptionalOuter(BaseModel):
            inner: OptionalInner | None = Field(default_factory=OptionalInner)

        out = tmp_path / "optional-nested.toml"
        tree = build_form_tree(OptionalOuter)

        save_toml(tree, out)

        content = out.read_text(encoding="utf-8")
        assert "enabled = true" in content
        assert "note" not in content
        assert load_toml(out, OptionalOuter).to_instance().inner == OptionalInner()
