"""pydantic-studio: interactive editor for Pydantic models."""

from __future__ import annotations

__version__ = "0.1.1"

from pydantic_studio.exceptions import (
    CancelledByUser,
    NoBuilderError,
    PydanticStudioError,
    ValidationFailedError,
)
from pydantic_studio.io import (
    load_config,
    load_json,
    load_toml,
    load_yaml,
    save_config,
    save_draft_yaml,
    save_json,
    save_toml,
    save_yaml,
)
from pydantic_studio.renderers.html import StudioServer, run_html_app
from pydantic_studio.renderers.textual_ import StudioApp, run_app
from pydantic_studio.tree.builder import (
    NodeBuilder,
    Registry,
    build_form_tree,
    default_registry,
    reset_default_registry,
)
from pydantic_studio.tree.draft import (
    delete_draft,
    draft_newer_than,
    find_draft,
    load_draft,
    save_draft,
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
    "StudioApp",
    "StudioServer",
    "TimeNode",
    "TimedeltaNode",
    "UnionNode",
    "UrlNode",
    "UuidNode",
    "ValidationFailedError",
    "ValidationResult",
    "__version__",
    "build_form_tree",
    "delete_draft",
    "draft_newer_than",
    "find_draft",
    "load_config",
    "load_draft",
    "load_json",
    "load_toml",
    "load_yaml",
    "register_builder",
    "reset_default_registry",
    "run_app",
    "run_html_app",
    "save_config",
    "save_draft",
    "save_draft_yaml",
    "save_json",
    "save_toml",
    "save_yaml",
]
