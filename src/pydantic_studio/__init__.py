"""pydantic-studio: interactive editor for Pydantic models."""

from __future__ import annotations

__version__ = "0.0.1"

from pydantic_studio.exceptions import (
    CancelledByUser,
    NoBuilderError,
    PydanticStudioError,
    ValidationFailedError,
)
from pydantic_studio.tree.builder import (
    NodeBuilder,
    Registry,
    build_form_tree,
    default_registry,
    reset_default_registry,
)
from pydantic_studio.tree.nodes import (
    BoolNode,
    DecimalNode,
    EnumNode,
    FloatNode,
    FormNode,
    FormTree,
    GroupNode,
    IntNode,
    LiteralNode,
    MappingNode,
    SequenceNode,
    StringNode,
    UnionNode,
)
from pydantic_studio.tree.validation import ValidationResult


def register_builder(builder: NodeBuilder) -> None:
    """Register a custom NodeBuilder into the global default registry.

    The new builder is *prepended*, so it overrides any prior builder that
    matches the same type.
    """
    default_registry().register(builder)


__all__ = [
    "BoolNode",
    "CancelledByUser",
    "DecimalNode",
    "EnumNode",
    "FloatNode",
    "FormNode",
    "FormTree",
    "GroupNode",
    "IntNode",
    "LiteralNode",
    "MappingNode",
    "NoBuilderError",
    "NodeBuilder",
    "PydanticStudioError",
    "Registry",
    "SequenceNode",
    "StringNode",
    "UnionNode",
    "ValidationFailedError",
    "ValidationResult",
    "__version__",
    "build_form_tree",
    "register_builder",
    "reset_default_registry",
]
