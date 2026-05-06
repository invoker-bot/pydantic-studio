"""Tests for YAML I/O — load + save + round-trip + smart comments."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pydantic_studio import load_yaml
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
