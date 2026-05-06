"""Tests for the special-types family — Path, UUID, SecretStr, Pattern, bytes."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, SecretBytes, SecretStr

from pydantic_studio import BytesNode, PathNode, PatternNode, SecretNode, UuidNode, build_form_tree


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


class WithSecret(BaseModel):
    api_key: SecretStr = SecretStr("default-key")
    token: SecretBytes = SecretBytes(b"default-token")


class TestSecretNode:
    def test_build_str_uses_secret_node_kind_str(self) -> None:
        tree = build_form_tree(WithSecret)
        api = tree.root.find("api_key")
        assert isinstance(api, SecretNode)
        assert api.secret_kind == "str"
        assert api.value == "default-key"

    def test_build_bytes_uses_secret_node_kind_bytes(self) -> None:
        tree = build_form_tree(WithSecret)
        token = tree.root.find("token")
        assert isinstance(token, SecretNode)
        assert token.secret_kind == "bytes"
        assert token.value == b"default-token"

    def test_validate_str_accepts_string(self) -> None:
        node = SecretNode(name="x", secret_kind="str", value=None)
        assert node.validate_value("password") == ()

    def test_validate_str_rejects_bytes(self) -> None:
        node = SecretNode(name="x", secret_kind="str", value=None)
        errors = node.validate_value(b"password")
        assert errors

    def test_validate_bytes_accepts_bytes(self) -> None:
        node = SecretNode(name="x", secret_kind="bytes", value=None)
        assert node.validate_value(b"token") == ()

    def test_validate_bytes_rejects_str(self) -> None:
        node = SecretNode(name="x", secret_kind="bytes", value=None)
        errors = node.validate_value("token")
        assert errors

    def test_to_python_str_wraps_secret(self) -> None:
        node = SecretNode(name="x", secret_kind="str", value="password")
        result = node.to_python()
        assert isinstance(result, SecretStr)
        assert result.get_secret_value() == "password"

    def test_to_python_bytes_wraps_secret(self) -> None:
        node = SecretNode(name="x", secret_kind="bytes", value=b"token")
        result = node.to_python()
        assert isinstance(result, SecretBytes)
        assert result.get_secret_value() == b"token"

    def test_snapshot_round_trip_str(self) -> None:
        node = SecretNode(name="x", secret_kind="str", value="password")
        raw = node.model_dump_json()
        restored = SecretNode.model_validate_json(raw)
        assert restored.value == "password"
        assert restored.secret_kind == "str"

    def test_snapshot_round_trip_bytes(self) -> None:
        """Pydantic encodes bytes as base64 in JSON; round-trip recovers them."""
        node = SecretNode(name="x", secret_kind="bytes", value=b"token")
        raw = node.model_dump_json()
        restored = SecretNode.model_validate_json(raw)
        assert restored.value == b"token"
        assert restored.secret_kind == "bytes"

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithSecret)
        instance = tree.to_instance()
        assert instance.api_key.get_secret_value() == "default-key"
        assert instance.token.get_secret_value() == b"default-token"

    def test_set_value_replaces_secret(self) -> None:
        tree = build_form_tree(WithSecret)
        result = tree.set_value("api_key", "new-secret")
        assert result.ok
        instance = tree.to_instance()
        assert instance.api_key.get_secret_value() == "new-secret"


class WithPattern(BaseModel):
    name_re: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9_]*$")
    flag_re: re.Pattern[str] = re.compile(r"hello", re.IGNORECASE)


class TestPatternNode:
    def test_build_uses_pattern_node(self) -> None:
        tree = build_form_tree(WithPattern)
        name_re = tree.root.find("name_re")
        assert isinstance(name_re, PatternNode)
        assert name_re.value == r"^[a-z][a-z0-9_]*$"
        assert name_re.flags == 0

    def test_build_preserves_flags(self) -> None:
        tree = build_form_tree(WithPattern)
        flag_re = tree.root.find("flag_re")
        assert isinstance(flag_re, PatternNode)
        assert flag_re.flags & re.IGNORECASE

    def test_validate_accepts_string(self) -> None:
        node = PatternNode(name="x", value=None)
        assert node.validate_value(r"^abc$") == ()

    def test_validate_rejects_invalid_regex(self) -> None:
        node = PatternNode(name="x", value=None)
        errors = node.validate_value(r"[unclosed")
        assert errors
        assert "regex" in errors[0].lower()

    def test_validate_rejects_non_string(self) -> None:
        node = PatternNode(name="x", value=None)
        errors = node.validate_value(42)
        assert errors

    def test_to_python_compiles(self) -> None:
        node = PatternNode(name="x", value=r"^[a-z]+$", flags=0)
        result = node.to_python()
        assert isinstance(result, re.Pattern)
        assert result.match("abc")
        assert not result.match("ABC")

    def test_to_python_applies_flags(self) -> None:
        node = PatternNode(name="x", value=r"hello", flags=re.IGNORECASE)
        result = node.to_python()
        assert result.match("HELLO")

    def test_snapshot_round_trip(self) -> None:
        node = PatternNode(name="x", value=r"^foo$", flags=re.IGNORECASE)
        raw = node.model_dump_json()
        restored = PatternNode.model_validate_json(raw)
        assert restored.value == r"^foo$"
        assert restored.flags == re.IGNORECASE

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithPattern)
        instance = tree.to_instance()
        assert instance.name_re.match("hello")


class WithBytes(BaseModel):
    blob: bytes = b"\x00\x01\x02"
    nonce: bytes = b""


class TestBytesNode:
    def test_build_uses_bytes_node(self) -> None:
        tree = build_form_tree(WithBytes)
        blob = tree.root.find("blob")
        assert isinstance(blob, BytesNode)
        assert blob.value == b"\x00\x01\x02"

    def test_validate_accepts_bytes(self) -> None:
        node = BytesNode(name="x", value=None)
        assert node.validate_value(b"data") == ()

    def test_validate_accepts_bytearray(self) -> None:
        node = BytesNode(name="x", value=None)
        assert node.validate_value(bytearray(b"data")) == ()

    def test_validate_rejects_str(self) -> None:
        node = BytesNode(name="x", value=None)
        errors = node.validate_value("data")
        assert errors

    def test_to_python_returns_bytes(self) -> None:
        node = BytesNode(name="x", value=b"hello")
        assert node.to_python() == b"hello"

    def test_snapshot_round_trip(self) -> None:
        """Pydantic emits bytes as base64 in JSON; round-trip recovers them."""
        node = BytesNode(name="x", value=b"\x00\xff\x80")
        raw = node.model_dump_json()
        restored = BytesNode.model_validate_json(raw)
        assert restored.value == node.value

    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithBytes)
        instance = tree.to_instance()
        assert instance.blob == b"\x00\x01\x02"
