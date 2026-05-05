from __future__ import annotations

import pytest

from pydantic_studio.exceptions import NoBuilderError
from pydantic_studio.tree.builder import NodeBuilder, Registry, default_registry


def test_default_registry_is_non_empty():
    """The default registry should already have at least one builder
    (more added in subsequent tasks; for now we just check shape)."""
    assert isinstance(default_registry(), Registry)


def test_registry_no_match_raises_no_builder_error():
    """If no builder matches, the registry raises NoBuilderError(type)."""
    reg = Registry()  # empty
    with pytest.raises(NoBuilderError) as exc_info:
        reg.find(int)
    assert exc_info.value.type_ is int


def test_registry_register_prepends_builder():
    """Registering puts the new builder at the front (overrides earlier)."""

    class Always(NodeBuilder):
        def matches(self, type_: type) -> bool:
            return True

        def build(self, type_, field_info, existing):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    reg = Registry()
    a, b = Always(), Always()
    reg.register(a)
    reg.register(b)  # b prepended
    assert reg.find(int) is b
