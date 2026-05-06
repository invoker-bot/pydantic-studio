"""Tests for the network type family — IP / URL / Email."""

from __future__ import annotations

from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
)

from pydantic import BaseModel

from pydantic_studio import IpAddressNode, IpNetworkNode, build_form_tree


class WithIp(BaseModel):
    bind_v4: IPv4Address = IPv4Address("127.0.0.1")
    bind_v6: IPv6Address = IPv6Address("::1")
    allow_v4: IPv4Network = IPv4Network("10.0.0.0/8")
    allow_v6: IPv6Network = IPv6Network("fe80::/64")


class TestIpAddressNode:
    def test_build_v4_uses_ip_node_with_version_4(self) -> None:
        tree = build_form_tree(WithIp)
        bind = tree.root.find("bind_v4")
        assert isinstance(bind, IpAddressNode)
        assert bind.version == 4
        assert bind.value == "127.0.0.1"

    def test_build_v6_uses_ip_node_with_version_6(self) -> None:
        tree = build_form_tree(WithIp)
        bind = tree.root.find("bind_v6")
        assert isinstance(bind, IpAddressNode)
        assert bind.version == 6
        assert bind.value == "::1"

    def test_validate_accepts_string_form(self) -> None:
        node = IpAddressNode(name="x", version=4, value=None)
        assert node.validate_value("192.168.1.1") == ()

    def test_validate_accepts_ipvX_instance(self) -> None:
        node = IpAddressNode(name="x", version=4, value=None)
        assert node.validate_value(IPv4Address("192.168.1.1")) == ()

    def test_validate_rejects_wrong_version(self) -> None:
        node = IpAddressNode(name="x", version=4, value=None)
        errors = node.validate_value("::1")
        assert errors
        assert "expected IPv4" in errors[0]

    def test_validate_rejects_garbage(self) -> None:
        node = IpAddressNode(name="x", version=4, value=None)
        errors = node.validate_value("not.an.ip")
        assert errors
        assert "invalid" in errors[0].lower()

    def test_to_python_coerces_to_instance(self) -> None:
        node = IpAddressNode(name="x", version=4, value="10.0.0.1")
        assert node.to_python() == IPv4Address("10.0.0.1")

    def test_to_python_v6(self) -> None:
        node = IpAddressNode(name="x", version=6, value="2001:db8::1")
        assert node.to_python() == IPv6Address("2001:db8::1")

    def test_snapshot_round_trip(self) -> None:
        node = IpAddressNode(name="x", version=4, value="10.0.0.1")
        raw = node.model_dump_json()
        restored = IpAddressNode.model_validate_json(raw)
        assert restored.value == "10.0.0.1"
        assert restored.version == 4


class TestIpNetworkNode:
    def test_build_v4_network(self) -> None:
        tree = build_form_tree(WithIp)
        allow = tree.root.find("allow_v4")
        assert isinstance(allow, IpNetworkNode)
        assert allow.version == 4
        assert allow.value == "10.0.0.0/8"

    def test_build_v6_network(self) -> None:
        tree = build_form_tree(WithIp)
        allow = tree.root.find("allow_v6")
        assert isinstance(allow, IpNetworkNode)
        assert allow.version == 6
        assert allow.value == "fe80::/64"

    def test_validate_accepts_cidr(self) -> None:
        node = IpNetworkNode(name="x", version=4, value=None)
        assert node.validate_value("192.168.0.0/16") == ()

    def test_validate_rejects_address_without_prefix(self) -> None:
        """Pydantic's IPvX_Network treats `192.168.1.1` as a /32 — accept it."""
        node = IpNetworkNode(name="x", version=4, value=None)
        # ipaddress.IPv4Network accepts bare addresses (defaults to /32),
        # so this MUST validate as a network.
        assert node.validate_value("192.168.1.1") == ()

    def test_validate_rejects_garbage(self) -> None:
        node = IpNetworkNode(name="x", version=4, value=None)
        errors = node.validate_value("not.a.cidr")
        assert errors

    def test_to_python_coerces(self) -> None:
        node = IpNetworkNode(name="x", version=4, value="10.0.0.0/8")
        assert node.to_python() == IPv4Network("10.0.0.0/8")

    def test_snapshot_round_trip(self) -> None:
        node = IpNetworkNode(name="x", version=6, value="fe80::/64")
        raw = node.model_dump_json()
        restored = IpNetworkNode.model_validate_json(raw)
        assert restored.value == "fe80::/64"
        assert restored.version == 6


class TestEndToEnd:
    def test_to_instance_round_trip(self) -> None:
        tree = build_form_tree(WithIp)
        instance = tree.to_instance()
        assert instance.bind_v4 == IPv4Address("127.0.0.1")
        assert instance.bind_v6 == IPv6Address("::1")
        assert instance.allow_v4 == IPv4Network("10.0.0.0/8")
        assert instance.allow_v6 == IPv6Network("fe80::/64")

    def test_set_value_via_string_round_trips(self) -> None:
        tree = build_form_tree(WithIp)
        result = tree.set_value("bind_v4", "192.168.1.1")
        assert result.ok
        instance = tree.to_instance()
        assert instance.bind_v4 == IPv4Address("192.168.1.1")
