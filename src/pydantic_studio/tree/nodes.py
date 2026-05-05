"""Form tree node hierarchy.

The tree is a Pydantic v2 hierarchy with a ``kind`` discriminator.
Concrete node types are added in subsequent tasks; this file defines
the abstract base ``FormNode``.
"""

from __future__ import annotations

import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path as FsPath
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from pydantic_studio.tree.validation import ValidationResult


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

    def validate_value(self, value: Any) -> tuple[str, ...]:
        """Return tuple of error messages for ``value`` against this node's
        type. Empty tuple = valid. Default: accept any value.

        Subclasses override to enforce per-type rules.
        """
        return ()

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

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, str):
            return (f"expected str, got {type(value).__name__}",)
        return ()

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

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Reject bool explicitly even though it is an int subclass.
        if isinstance(value, bool) or not isinstance(value, int):
            return (f"expected int, got {type(value).__name__}",)
        return ()

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

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Accept int (Pydantic coerces). Reject bool.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return (f"expected float, got {type(value).__name__}",)
        return ()

    def to_python(self) -> float | None:
        return self.value


class BoolNode(FormNode):
    """Holds a boolean value."""

    kind: Literal["bool"] = "bool"
    value: bool | None = None
    default: bool | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, bool):
            return (f"expected bool, got {type(value).__name__}",)
        return ()

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
    gt: Decimal | None = None
    lt: Decimal | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Reject bool first — Pydantic's Decimal validation rejects it.
        if isinstance(value, bool):
            return (f"expected Decimal, got {type(value).__name__}",)
        if isinstance(value, Decimal):
            return ()
        # Pydantic coerces int / float / str via Decimal(str(...)). Mirror
        # that behavior so validate_value does not flag values the schema
        # would happily accept.
        if isinstance(value, (int, float, str)):
            try:
                Decimal(str(value)) if isinstance(value, float) else Decimal(value)
            except (InvalidOperation, ValueError):
                return (f"cannot convert {value!r} to Decimal",)
            return ()
        return (f"expected Decimal, got {type(value).__name__}",)

    def to_python(self) -> Decimal | None:
        return self.value


class EnumNode(FormNode):
    """Holds a single value drawn from a closed set of Enum members."""

    kind: Literal["enum"] = "enum"
    value: Any = None  # an Enum member or None
    default: Any = None
    # Enum members serialized as (name, member) pairs. Member objects are
    # not Pydantic-friendly across snapshots, so we also store the FQ name
    # of the Enum class for round-trip via sys.modules lookup.
    enum_class_name: str
    choices: list[tuple[str, Any]] = []

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        return self.value

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from enum import Enum

        short_name = self.enum_class_name.rsplit(".", 1)[-1]
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, Enum):
            return (f"{value!r} is not a {short_name} member",)
        # Compare by name to avoid identity drift across imports.
        if value.name not in [name for name, _ in self.choices]:
            return (f"{value!r} is not a {short_name} member",)
        return ()


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
        """Collect child values into a dict keyed by child names.

        Filters by *omitting the key from the returned dict* whenever a
        child's ``to_python()`` returns ``None`` — which causes Pydantic to
        apply the field's schema default. An all-None nested ``GroupNode``
        returns ``{}`` (empty dict), which is NOT itself filtered: Pydantic
        treats ``{}`` as "use all of the nested model's defaults", and
        keeping the empty dict in the parent yields more precise validation
        error messages when a required leaf is missing.

        Known v0.1 limitation: users cannot save an Optional[T] field as
        explicit None — that requires v0.2's explicit-null toggle.
        """
        out: dict[str, Any] = {}
        for f in self.fields:
            v = f.to_python()
            if v is None:
                continue
            out[f.name] = v
        return out


# Discriminated union — every concrete node type uses ``kind`` as discriminator.
AnyNode = Annotated[
    StringNode | IntNode | FloatNode | BoolNode | DecimalNode | EnumNode | GroupNode,
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

    def to_instance(self) -> BaseModel:
        """Materialize the tree into the user's schema_class.

        Raises:
            ValidationFailedError: if the schema rejects the produced dict.
        """
        from pydantic import ValidationError

        from pydantic_studio.exceptions import ValidationFailedError

        if self.schema_class is None:
            msg = "FormTree.schema_class is not set"
            raise RuntimeError(msg)
        # GroupNode.to_python now filters None at every depth, so no
        # additional top-level filtering is needed here.
        data = self.to_python()
        try:
            return self.schema_class.model_validate(data)
        except ValidationError as e:
            errors = [
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                for err in e.errors()
            ]
            raise ValidationFailedError(errors) from e

    @model_validator(mode="after")
    def _inject_schema_from_context(self, info: ValidationInfo) -> FormTree:
        """If schema_class is missing (e.g., loaded from JSON), pull it
        from the validation context (which ``draft_load`` supplies)."""
        if self.schema_class is None and info.context and "schema_class" in info.context:
            self.schema_class = info.context["schema_class"]
        return self

    # ----- mutations -----

    def set_value(self, path: str, value: Any) -> ValidationResult:
        """Set ``value`` at the given path; runs node-local validation.

        On success: push a snapshot, write the value to the target node,
        clear ``target.error``, and return ``ValidationResult.ok()``.

        On failure: leave ``target.value`` untouched (so the FormTree's
        typed fields stay type-correct and snapshots remain serializable),
        record the first error message on ``target.error`` for renderer
        display, and return ``ValidationResult.fail(...)``. Note that
        ``target.error`` carries only the primary message; the full list
        of errors lives in the returned ``ValidationResult``.

        Cross-field validation runs at submit time (``to_instance``).
        """
        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.paths import Path as _Path

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            msg = "cannot set value on the root group itself"
            raise ValueError(msg)
        parent: Any = self.root
        for seg in path_obj.segments[:-1]:
            if isinstance(parent, GroupNode) and isinstance(seg, str):
                child = parent.find(seg)
                if child is None:
                    msg = f"no field named {seg!r} at this level"
                    raise KeyError(msg)
                parent = child
            else:
                msg = f"cannot navigate segment {seg!r} (not a group)"
                raise KeyError(msg)

        last = path_obj.segments[-1]
        if not (isinstance(parent, GroupNode) and isinstance(last, str)):
            msg = f"cannot set on non-group parent at segment {last!r}"
            raise KeyError(msg)
        target = parent.find(last)
        if target is None:
            msg = f"no field named {last!r}"
            raise KeyError(msg)

        errors = target.validate_value(value)
        if errors:
            target.error = errors[0]
            return ValidationResult.fail(list(errors))

        # Validation passed: snapshot before mutating so undo can revert.
        self._push_snapshot(_snap.take(self.root))
        target.value = value
        target.error = None
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    # ----- snapshot internals -----

    def _push_snapshot(self, snap: bytes) -> None:
        # If the cursor is not at the tail, drop the redo tail before pushing.
        if self.cursor < len(self.snapshots):
            self.snapshots = self.snapshots[: self.cursor]
        self.snapshots.append(snap)
        # Bound: drop oldest until under the limit.
        while len(self.snapshots) > self.snapshot_limit:
            self.snapshots.pop(0)
        self.cursor = len(self.snapshots)

    def undo(self) -> bool:
        """Restore the previous state. Returns True if anything was undone."""
        from pydantic_studio.tree import snapshots as _snap

        if self.cursor == 0:
            return False
        # The current state isn't yet on the stack; only prior states are.
        # Step back: cursor points to the snapshot that *was* the state before
        # the most recent mutation. To allow redo, capture the current state
        # first if cursor == len(snapshots).
        if self.cursor == len(self.snapshots):
            self.snapshots.append(_snap.take(self.root))
        self.cursor -= 1
        self.root = _snap.restore(self.snapshots[self.cursor])
        return True

    def redo(self) -> bool:
        """Re-apply a previously undone mutation."""
        from pydantic_studio.tree import snapshots as _snap

        if self.cursor + 1 >= len(self.snapshots):
            return False
        self.cursor += 1
        self.root = _snap.restore(self.snapshots[self.cursor])
        return True
