"""Tests for YAML I/O — load + save + round-trip + smart comments."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from pydantic_studio import load_yaml
from pydantic_studio.tree.builder import build_form_tree
from tests.fixtures.schemas import Server

if TYPE_CHECKING:
    from pathlib import Path


class TestLoadYaml:
    def test_load_basic_file(self, tmp_path: Path) -> None:
        src = tmp_path / "config.yaml"
        src.write_text(
            "name: prod\nport: 8080\ndebug: true\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        instance = tree.to_instance()
        assert instance.name == "prod"
        assert instance.port == 8080
        assert instance.debug is True

    def test_load_empty_file_yields_defaults(self, tmp_path: Path) -> None:
        src = tmp_path / "empty.yaml"
        src.write_text("", encoding="utf-8")
        tree = load_yaml(src, Server)
        instance = tree.to_instance()
        # All defaults applied.
        assert instance.name == "prod"
        assert instance.port == 8080
        assert instance.debug is False

    def test_load_preserves_source_for_round_trip(self, tmp_path: Path) -> None:
        src = tmp_path / "config.yaml"
        src.write_text(
            "# top-level comment\nname: alpha  # inline comment\nport: 9090\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        # yaml_source must be a CommentedMap (or at least a dict containing the data).
        assert tree.yaml_source is not None
        assert tree.yaml_source.get("name") == "alpha"

    def test_load_unknown_field_is_dropped_silently(
        self, tmp_path: Path
    ) -> None:
        """Per spec O-1: unknown fields drop with a stderr warning by default.
        For now we drop silently in v0.0.4; --strict mode comes in a later
        release. Verify the unknown field doesn't reach the FormTree."""
        src = tmp_path / "config.yaml"
        src.write_text(
            "name: prod\nport: 8080\nunknown_field: ignored\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        # FormTree only knows about schema fields.
        assert {f.name for f in tree.root.fields} == {"name", "port", "debug"}

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError):
            load_yaml(src, Server)

    def test_load_malformed_yaml_raises(self, tmp_path: Path) -> None:
        from ruamel.yaml import YAMLError

        src = tmp_path / "bad.yaml"
        src.write_text(
            "name: prod\nport: [unclosed\n",
            encoding="utf-8",
        )
        with pytest.raises(YAMLError):
            load_yaml(src, Server)


class TestSaveYamlNewFile:
    """save_yaml when no source file exists — must auto-generate
    description comments from the schema."""

    def test_save_creates_file_with_values(self, tmp_path: Path) -> None:
        from pydantic_studio import save_yaml

        tree = build_form_tree(Server)
        out = tmp_path / "config.yaml"
        save_yaml(tree, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        # Default values appear.
        assert "prod" in content
        assert "8080" in content

    def test_save_emits_description_comments(self, tmp_path: Path) -> None:
        from pydantic_studio import save_yaml

        tree = build_form_tree(Server)
        out = tmp_path / "config.yaml"
        save_yaml(tree, out)
        content = out.read_text(encoding="utf-8")
        # Each field's description should appear as a comment.
        assert "Service identifier" in content
        assert "Listening port" in content
        assert "Enable debug logging" in content

    def test_save_preserves_schema_field_order(self, tmp_path: Path) -> None:
        from pydantic_studio import save_yaml

        tree = build_form_tree(Server)
        out = tmp_path / "config.yaml"
        save_yaml(tree, out)
        content = out.read_text(encoding="utf-8")
        # Per spec §10.1 rule #1: schema definition order, not arbitrary.
        # Server defines name → port → debug.
        i_name = content.index("name:")
        i_port = content.index("port:")
        i_debug = content.index("debug:")
        assert i_name < i_port < i_debug

    def test_save_round_trip_load_back(self, tmp_path: Path) -> None:
        """Save a tree, reload it, confirm the FormTree state matches."""
        tree = build_form_tree(Server)
        tree.set_value("port", 9999)
        out = tmp_path / "config.yaml"
        from pydantic_studio import save_yaml

        save_yaml(tree, out)
        reloaded = load_yaml(out, Server)
        instance = reloaded.to_instance()
        assert instance.port == 9999
        assert instance.name == "prod"  # default unchanged

    def test_save_atomic_temp_rename(self, tmp_path: Path) -> None:
        """A failed write must not corrupt an existing file. We test the
        atomicity by writing twice and checking no .tmp leftovers."""
        from pydantic_studio import save_yaml

        tree = build_form_tree(Server)
        out = tmp_path / "config.yaml"
        save_yaml(tree, out)
        save_yaml(tree, out)
        # No temp files left behind.
        leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp-")]
        assert leftovers == []

    def test_save_creates_parent_directory(self, tmp_path: Path) -> None:
        """Like draft_save, save_yaml should create parent dirs as needed."""
        from pydantic_studio import save_yaml

        tree = build_form_tree(Server)
        out = tmp_path / "nested" / "subdir" / "config.yaml"
        save_yaml(tree, out)
        assert out.exists()


class TestSaveYamlPreservesComments:
    """When a source file or yaml_source exists, save_yaml must preserve
    user-edited comments on fields that still exist in the schema."""

    def test_user_comment_survives_round_trip(self, tmp_path: Path) -> None:
        from pydantic_studio import save_yaml

        # User-authored YAML with a custom comment.
        src = tmp_path / "config.yaml"
        src.write_text(
            "# my custom note about the service\n"
            "name: prod\n"
            "port: 8080\n"
            "debug: false\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        tree.set_value("port", 9090)
        save_yaml(tree, src)

        content = src.read_text(encoding="utf-8")
        # User comment must still appear.
        assert "my custom note about the service" in content
        # Updated value applied.
        assert "9090" in content
        assert "8080" not in content

    def test_unknown_field_is_dropped_on_save(self, tmp_path: Path) -> None:
        """Per spec §10.1 rule #4 — fields no longer in the schema get
        dropped on save."""
        from pydantic_studio import save_yaml

        src = tmp_path / "config.yaml"
        src.write_text(
            "name: prod\n"
            "port: 8080\n"
            "obsolete_field: gone\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        save_yaml(tree, src)
        content = src.read_text(encoding="utf-8")
        assert "obsolete_field" not in content
        assert "gone" not in content

    def test_save_to_existing_file_without_load(self, tmp_path: Path) -> None:
        """If the user calls save_yaml with a tree that was NOT loaded from
        the target path but the path already exists, comments from the file
        should still be preserved (re-load on save semantics)."""
        from pydantic_studio import save_yaml

        # Pre-existing file with a comment.
        src = tmp_path / "config.yaml"
        src.write_text(
            "# pre-existing comment\n"
            "name: alpha\n"
            "port: 7777\n",
            encoding="utf-8",
        )

        # Build a fresh tree (NOT loaded from the file).
        tree = build_form_tree(Server)
        tree.set_value("port", 9090)
        save_yaml(tree, src)

        content = src.read_text(encoding="utf-8")
        assert "pre-existing comment" in content
        assert "9090" in content

    def test_inline_comment_preserved(self, tmp_path: Path) -> None:
        """Inline (end-of-line) comments must also survive."""
        from pydantic_studio import save_yaml

        src = tmp_path / "config.yaml"
        src.write_text(
            "name: prod  # production deployment\n"
            "port: 8080  # standard HTTP\n"
            "debug: false\n",
            encoding="utf-8",
        )
        tree = load_yaml(src, Server)
        tree.set_value("port", 9090)
        save_yaml(tree, src)

        content = src.read_text(encoding="utf-8")
        assert "production deployment" in content
        assert "standard HTTP" in content


class TestSaveYamlEnumBearing:
    """Regression: save_yaml on schemas with Enum fields."""

    def test_save_yaml_with_enum_field(self, tmp_path: Path) -> None:
        from enum import Enum

        from pydantic_studio import build_form_tree, save_yaml

        class Color(Enum):
            RED = "red"
            BLUE = "blue"

        class M(BaseModel):
            favorite: Color = Color.RED

        out = tmp_path / "out.yaml"
        tree = build_form_tree(M)
        save_yaml(tree, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "red" in content
