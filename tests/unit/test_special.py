"""Tests for the special-types family — Path, UUID, SecretStr, Pattern, bytes."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel

from pydantic_studio import PathNode, UuidNode, build_form_tree


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


class WithUuid(BaseModel):
    request_id: UUID = UUID("00000000-0000-0000-0000-000000000000")
    session_id: UUID = UUID("11111111-1111-1111-1111-111111111111")


class TestUuidNode:
    def test_build_uses_uuid_node(self) -> None:
        tree = build_form_tree(WithUuid)
        rid = tree.root.find("request_id")
        assert isinstance(rid, UuidNode)
        assert rid.value == UUID("00000000-0000-0000-0000-000000000000")

    def test_validate_accepts_uuid(self) -> None:
        node = UuidNode(name="x", value=None)
        assert node.validate_value(uuid4()) == ()

    def test_validate_rejects_string(self) -> None:
        """The renderer parses user-input strings into UUIDs before
        calling set_value. validate_value expects already-parsed UUIDs."""
        node = UuidNode(name="x", value=None)
        errors = node.validate_value("00000000-0000-0000-0000-000000000000")
        assert errors
        assert "expected UUID" in errors[0]

    def test_required_none_fails(self) -> None:
        node = UuidNode(name="x", required=True, value=None)
        assert node.validate_value(None) == ("value is required",)

    def test_to_python_returns_uuid(self) -> None:
        u = uuid4()
        node = UuidNode(name="x", value=u)
        assert node.to_python() == u

    def test_snapshot_round_trip(self) -> None:
        u = uuid4()
        node = UuidNode(name="x", value=u)
        raw = node.model_dump_json()
        restored = UuidNode.model_validate_json(raw)
        assert restored.value == u

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithUuid)
        instance = tree.to_instance()
        assert instance.request_id == UUID("00000000-0000-0000-0000-000000000000")
