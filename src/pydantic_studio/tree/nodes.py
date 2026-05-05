"""Form tree node hierarchy.

The tree is a Pydantic v2 hierarchy with a ``kind`` discriminator.
Concrete node types are added in subsequent tasks; this file defines
the abstract base ``FormNode``.
"""

from __future__ import annotations

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path as FsPath
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, field_serializer, field_validator


class FormNode(BaseModel):
    """Abstract base. Concrete subclasses set their own ``kind`` literal.

    All FormNodes carry minimal metadata: ``name`` (the field name in the
    parent's schema), ``description`` (markdown, may be None), ``required``
    (mirrors the schema's required-ness), and ``error`` (last validation
    message; None when valid).
    """

    model_config = ConfigDict(extra="forbid")

    kind: str  # set by subclass
    name: str
    description: str | None = None
    required: bool = True
    error: str | None = None

    # Convenience hook used in subsequent tasks; subclasses may override.
    def to_python(self) -> Any:
        """Return this node's value in a form suitable for `model_validate`."""
        msg = f"{type(self).__name__}.to_python is not implemented"
        raise NotImplementedError(msg)


class StringNode(FormNode):
    """Holds a string value, with optional length / regex / multiline / secret hints."""

    kind: Literal["string"] = "string"
    value: str | None = None
    default: str | None = None

    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None  # regex source; rendered as a label, not enforced here
    multiline: bool = False
    secret: bool = False

    def to_python(self) -> str | None:
        return self.value


class IntNode(FormNode):
    """Holds an integer value, with optional comparison and multiple-of constraints."""

    kind: Literal["int"] = "int"
    value: int | None = None
    default: int | None = None

    ge: int | None = None
    le: int | None = None
    gt: int | None = None
    lt: int | None = None
    multiple_of: int | None = None

    def to_python(self) -> int | None:
        return self.value


class FloatNode(FormNode):
    """Holds a float value, with optional comparison and infinity/NaN constraints."""

    kind: Literal["float"] = "float"
    value: float | None = None
    default: float | None = None

    ge: float | None = None
    le: float | None = None
    gt: float | None = None
    lt: float | None = None
    multiple_of: float | None = None
    allow_inf_nan: bool = True

    def to_python(self) -> float | None:
        return self.value


class BoolNode(FormNode):
    """Holds a boolean value."""

    kind: Literal["bool"] = "bool"
    value: bool | None = None
    default: bool | None = None

    def to_python(self) -> bool | None:
        return self.value


class DecimalNode(FormNode):
    """Holds a Decimal value, with optional digit and comparison constraints."""

    kind: Literal["decimal"] = "decimal"
    value: Decimal | None = None
    default: Decimal | None = None

    max_digits: int | None = None
    decimal_places: int | None = None
    ge: Decimal | None = None
    le: Decimal | None = None

    def to_python(self) -> Decimal | None:
        return self.value


class GroupNode(FormNode):
    """Represents a nested Pydantic BaseModel with a list of child nodes."""

    kind: Literal["group"] = "group"
    schema_class: type[BaseModel]
    fields: "list[AnyNode]"  # forward ref; rebuilt at module bottom

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    @field_serializer("schema_class", when_used="json")
    def serialize_schema_class(self, value: type[BaseModel]) -> str:
        """Serialize schema_class to a fully qualified name for JSON."""
        return f"{value.__module__}.{value.__name__}"

    @field_validator("schema_class", mode="before")
    @classmethod
    def _deserialize_schema_class(cls, v: Any) -> Any:
        """If ``v`` is a serialized string (`module.ClassName`), look up the
        class from ``sys.modules``. Raise ValueError with diagnostic info on
        failure so debugging draft-load problems is easier."""
        if not isinstance(v, str):
            return v  # already a class object — no change needed
        parts = v.rsplit(".", 1)
        if len(parts) != 2:
            msg = (
                f"Cannot deserialize schema_class from {v!r}: expected the "
                f"'module.ClassName' format produced by the field_serializer."
            )
            raise ValueError(msg)
        module_name, class_name = parts
        module = sys.modules.get(module_name)
        if module is None:
            msg = (
                f"Cannot deserialize schema_class {v!r}: module {module_name!r} "
                f"is not in sys.modules. Ensure the module is imported before "
                f"loading the snapshot/draft."
            )
            raise ValueError(msg)
        if not hasattr(module, class_name):
            msg = (
                f"Cannot deserialize schema_class {v!r}: module {module_name!r} "
                f"has no attribute {class_name!r}. The class may have been "
                f"renamed or moved since the snapshot/draft was created."
            )
            raise ValueError(msg)
        return getattr(module, class_name)

    def find(self, name: str) -> AnyNode | None:
        """Find a child node by name, or None if not found."""
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def to_python(self) -> dict[str, Any]:
        """Collect child values into a dict keyed by child names."""
        return {f.name: f.to_python() for f in self.fields}


# Discriminated union — every concrete node type uses ``kind`` as discriminator.
AnyNode = Annotated[
    StringNode | IntNode | FloatNode | BoolNode | DecimalNode | GroupNode,
    Discriminator("kind"),
]


# Resolve the forward reference inside GroupNode.fields.
GroupNode.model_rebuild()


class FormTree(BaseModel):
    """Root container: schema reference, root group, and history (added later)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    schema_class: type[BaseModel] | None = None  # may be re-attached via context on load
    schema_name: str
    root: GroupNode
    created_at: datetime
    snapshots: list[bytes] = []
    cursor: int = 0
    snapshot_limit: int = 50
    draft_path: FsPath | None = None

    def to_python(self) -> dict[str, Any]:
        return self.root.to_python()
