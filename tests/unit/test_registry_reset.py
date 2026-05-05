"""Tests for reset_default_registry()."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_studio.tree.builder import (
    default_registry,
    reset_default_registry,
)
from pydantic_studio.tree.nodes import StringNode

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


class _StubBuilder:
    """Minimal NodeBuilder for testing — matches str only."""

    def matches(self, type_: type) -> bool:
        return type_ is str

    def build(
        self, type_: type, field_info: FieldInfo, existing: Any
    ) -> StringNode:
        return StringNode(name="stub", value="stubbed")


def test_reset_returns_fresh_registry_after_register() -> None:
    reg1 = default_registry()
    reg1.register(_StubBuilder())
    reset_default_registry()
    reg2 = default_registry()
    # Must be a fresh instance, not the mutated one.
    assert reg1 is not reg2
    # The stub registration must not survive.
    found = reg2.find(str)
    assert not isinstance(found, _StubBuilder)


def test_reset_is_idempotent() -> None:
    reset_default_registry()
    reset_default_registry()  # second call must not error
    reg = default_registry()
    # Phase 1 default registry registers 6 builders: String, Int, Float,
    # Bool, Decimal, Group. The double-reset must produce the same baseline.
    assert len(reg) == 6
