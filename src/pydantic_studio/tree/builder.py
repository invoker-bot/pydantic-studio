"""Public entry point for tree construction.

The dispatch layer (Registry, NodeBuilder Protocol, concrete builders)
lives in ``pydantic_studio.types``. This module is a thin facade that
wires the default registry and exposes ``build_form_tree``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic_studio.types.choices import EnumBuilder, LiteralBuilder
from pydantic_studio.types.mapping import DictBuilder
from pydantic_studio.types.models import GroupBuilder
from pydantic_studio.types.primitives import (
    BoolBuilder,
    DecimalBuilder,
    FloatBuilder,
    IntBuilder,
    StringBuilder,
)
from pydantic_studio.types.registry import NodeBuilder, Registry
from pydantic_studio.types.sequences import ListBuilder, SetBuilder, TupleBuilder
from pydantic_studio.types.temporal import (
    DateBuilder,
    DatetimeBuilder,
    TimeBuilder,
    TimedeltaBuilder,
)
from pydantic_studio.types.unions import UnionBuilder

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = [
    "NodeBuilder",
    "Registry",
    "build_form_tree",
    "default_registry",
    "reset_default_registry",
]

_DEFAULT_REGISTRY: Registry | None = None


def default_registry() -> Registry:
    """Return the global default registry (lazily constructed).

    Subsequent tasks register concrete builders into this registry. v0.1
    stays single-process and does not need cross-thread isolation.
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        reg = Registry()
        # Register in *reverse* priority order — last registered wins for same type.
        # Primitive builders are mutually exclusive on type, so order doesn't matter
        # within this group, but we follow a stable convention.
        reg.register(StringBuilder())
        reg.register(IntBuilder())
        reg.register(FloatBuilder())
        reg.register(BoolBuilder())
        reg.register(DecimalBuilder())
        reg.register(EnumBuilder())
        reg.register(LiteralBuilder())
        reg.register(DatetimeBuilder())
        reg.register(DateBuilder())
        reg.register(TimeBuilder())
        reg.register(TimedeltaBuilder())
        reg.register(ListBuilder(reg))
        reg.register(SetBuilder(reg))
        reg.register(TupleBuilder(reg))
        reg.register(DictBuilder(reg))
        reg.register(UnionBuilder(reg))      # before GroupBuilder
        # GroupBuilder is registered last so it matches *any* BaseModel
        # only when no more-specific builder did. It also needs a back-
        # reference to the registry for recursive dispatch.
        reg.register(GroupBuilder(reg))
        _DEFAULT_REGISTRY = reg
    return _DEFAULT_REGISTRY


def reset_default_registry() -> None:
    """Drop the cached default registry so the next ``default_registry()``
    call rebuilds it from scratch.

    Tests that mutate the registry (e.g., via ``register_builder``) should
    call this in setup/teardown — otherwise registrations leak between tests.
    """
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None


def build_form_tree(
    schema: type[BaseModel],
    existing: dict[str, Any] | None = None,
    registry: Registry | None = None,
) -> Any:
    """Build a FormTree from a Pydantic BaseModel subclass.

    Args:
        schema: The user's Pydantic model class.
        existing: Optional dict to pre-populate field values.
        registry: Optional custom registry (defaults to the global default).

    Returns:
        FormTree: Root container with schema reference, root group, and history fields.
    """
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.nodes import FormTree, GroupNode  # avoid circular at import time

    reg = registry if registry is not None else default_registry()
    builder = reg.find(schema)
    root = builder.build(schema, FieldInfo(annotation=schema), existing or {})
    assert isinstance(root, GroupNode), f"expected GroupNode for BaseModel, got {type(root)}"
    schema_name = f"{schema.__module__}:{schema.__qualname__}"
    return FormTree(
        schema_class=schema,
        schema_name=schema_name,
        root=root,
        created_at=datetime.now(tz=UTC),
    )
