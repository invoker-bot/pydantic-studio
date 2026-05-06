"""Tests for the special-types family — Path, UUID, SecretStr, Pattern, bytes."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from pydantic_studio import PathNode, build_form_tree


class WithPath(BaseModel):
    home: Path = Path("/home/user")
    workdir: Path = Path("/tmp/work")


class TestPathNode:
    def test_build_uses_path_node(self) -> None:
        tree = build_form_tree(WithPath)
        home = tree.root.find("home")
        assert isinstance(home, PathNode)
        # Stored as a string for cross-OS portability.
        assert home.value == str(Path("/home/user"))

    def test_validate_accepts_string(self) -> None:
        node = PathNode(name="x", value=None)
        assert node.validate_value("/etc/config.yaml") == ()

    def test_validate_accepts_path_instance(self) -> None:
        node = PathNode(name="x", value=None)
        assert node.validate_value(Path("/etc/config.yaml")) == ()

    def test_validate_rejects_non_path(self) -> None:
        node = PathNode(name="x", value=None)
        errors = node.validate_value(42)
        assert errors
        assert "expected str or Path" in errors[0]

    def test_required_none_fails(self) -> None:
        node = PathNode(name="x", required=True, value=None)
        assert node.validate_value(None) == ("value is required",)

    def test_to_python_coerces_to_path(self) -> None:
        node = PathNode(name="x", value="/etc/config.yaml")
        result = node.to_python()
        assert isinstance(result, Path)
        assert str(result) == str(Path("/etc/config.yaml"))

    def test_snapshot_round_trip(self) -> None:
        node = PathNode(name="x", value="/var/log/app.log")
        raw = node.model_dump_json()
        restored = PathNode.model_validate_json(raw)
        assert restored.value == node.value

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithPath)
        instance = tree.to_instance()
        assert instance.home == Path("/home/user")

    def test_set_value_with_string(self) -> None:
        tree = build_form_tree(WithPath)
        result = tree.set_value("home", "/new/home")
        assert result.ok
        instance = tree.to_instance()
        assert instance.home == Path("/new/home")

    def test_set_value_with_path_instance(self) -> None:
        tree = build_form_tree(WithPath)
        result = tree.set_value("home", Path("/another/home"))
        assert result.ok
        # PathNode stores as string regardless of input form.
        home = tree.root.find("home")
        assert isinstance(home.value, str)
