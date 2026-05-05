"""Form tree node hierarchy.

The tree is a Pydantic v2 hierarchy with a ``kind`` discriminator.
Concrete node types are added in subsequent tasks; this file defines
the abstract base ``FormNode``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


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
