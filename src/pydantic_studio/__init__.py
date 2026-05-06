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
    BytesNode,
    DateNode,
    DatetimeNode,
    DecimalNode,
    EmailNode,
    EnumNode,
    FloatNode,
    FormNode,
    FormTree,
    GroupNode,
    IntNode,
    IpAddressNode,
    IpNetworkNode,
    LiteralNode,
    MappingNode,
    PathNode,
    PatternNode,
    SecretNode,
    SequenceNode,
    StringNode,
    TimedeltaNode,
    TimeNode,
    UnionNode,
    UrlNode,
    UuidNode,
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
    "BytesNode",
    "CancelledByUser",
    "DateNode",
    "DatetimeNode",
    "DecimalNode",
    "EmailNode",
    "EnumNode",
    "FloatNode",
    "FormNode",
    "FormTree",
    "GroupNode",
    "IntNode",
    "IpAddressNode",
    "IpNetworkNode",
    "LiteralNode",
    "MappingNode",
    "NoBuilderError",
    "NodeBuilder",
    "PathNode",
    "PatternNode",
    "PydanticStudioError",
    "Registry",
    "SecretNode",
    "SequenceNode",
    "StringNode",
    "TimeNode",
    "TimedeltaNode",
    "UnionNode",
    "UrlNode",
    "UuidNode",
    "ValidationFailedError",
    "ValidationResult",
    "__version__",
    "build_form_tree",
    "register_builder",
    "reset_default_registry",
]
