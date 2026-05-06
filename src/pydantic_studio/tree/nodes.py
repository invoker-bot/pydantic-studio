"""Form tree node hierarchy.

The tree is a Pydantic v2 hierarchy with a ``kind`` discriminator.
Concrete node types are added in subsequent tasks; this file defines
the abstract base ``FormNode``.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta
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


def _resolve_type_name(name: str) -> Any:
    """Look up a fully-qualified type name (``module.Qualname``).

    Handles ``builtins.str`` etc. specially so unit tests don't need to
    import builtins. Raises ValueError on miss with a diagnostic message.
    """
    parts = name.rsplit(".", 1)
    if len(parts) != 2:
        msg = f"malformed type name {name!r} (expected 'module.Qualname')"
        raise ValueError(msg)
    module_name, qualname = parts
    if module_name == "builtins":
        builtin = (
            __builtins__.get(qualname)
            if isinstance(__builtins__, dict)
            else getattr(__builtins__, qualname, None)
        )
        if builtin is None:
            msg = f"unknown builtin {qualname!r}"
            raise ValueError(msg)
        return builtin
    module = sys.modules.get(module_name)
    if module is None:
        msg = (
            f"module {module_name!r} not in sys.modules — "
            f"import it before resolving {name!r}"
        )
        raise ValueError(msg)
    obj: Any = module
    for part in qualname.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            msg = f"{module_name!r} has no {part!r} (resolving {name!r})"
            raise ValueError(msg)
    return obj


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


class DatetimeNode(FormNode):
    """Holds a timezone-aware-or-naive ``datetime.datetime`` value.

    Pydantic emits ISO 8601 strings on ``model_dump_json`` and parses them
    back on ``model_validate_json``, so no custom serializer is needed.
    """

    kind: Literal["datetime"] = "datetime"
    value: datetime | None = None
    default: datetime | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        # Reject date/time subclasses explicitly — datetime IS-A date in Python,
        # but a date field cannot take a datetime and vice versa. We need an
        # exact-type check.
        if type(value) is not datetime:
            return (f"expected datetime, got {type(value).__name__}",)
        return ()

    def to_python(self) -> datetime | None:
        return self.value


class DateNode(FormNode):
    """Holds a ``datetime.date`` value (no time component)."""

    kind: Literal["date"] = "date"
    value: date | None = None
    default: date | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if type(value) is not date:  # exact-type: rejects datetime subclass
            return (f"expected date, got {type(value).__name__}",)
        return ()

    def to_python(self) -> date | None:
        return self.value


class TimeNode(FormNode):
    """Holds a ``datetime.time`` value (no date component)."""

    kind: Literal["time"] = "time"
    value: time | None = None
    default: time | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if type(value) is not time:
            return (f"expected time, got {type(value).__name__}",)
        return ()

    def to_python(self) -> time | None:
        return self.value


class TimedeltaNode(FormNode):
    """Holds a ``datetime.timedelta`` value (a duration).

    Pydantic emits ISO 8601 duration strings (``PT1H30M``) on JSON dump
    and parses them back on load — round-trip works without a custom
    serializer.
    """

    kind: Literal["timedelta"] = "timedelta"
    value: timedelta | None = None
    default: timedelta | None = None

    def validate_value(self, value: Any) -> tuple[str, ...]:
        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, timedelta):
            return (f"expected timedelta, got {type(value).__name__}",)
        return ()

    def to_python(self) -> timedelta | None:
        return self.value


class EnumNode(FormNode):
    """Holds a single value drawn from a closed set of Enum members.

    Snapshot round-trip: ``value``, ``default``, and the member side of
    each ``choices`` tuple are serialized as the member's ``.name`` (a
    string) and rehydrated back into Enum members on validation, using
    ``enum_class_name`` for sys.modules lookup. This matches the pattern
    GroupNode uses for ``schema_class``.

    Invariant: ``choices[i][1]`` is always an Enum member when the node is
    in a fresh-from-builder OR fresh-from-snapshot-load state. After JSON
    serialization but before re-validation it is transiently a string.
    """

    kind: Literal["enum"] = "enum"
    value: Any = None
    default: Any = None
    enum_class_name: str
    choices: list[tuple[str, Any]] = []

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    @field_serializer("value", "default", when_used="json")
    def _serialize_member(self, value: Any) -> Any:
        from enum import Enum

        if isinstance(value, Enum):
            return value.name
        return value

    @field_serializer("choices", when_used="json")
    def _serialize_choices(
        self, choices: list[tuple[str, Any]]
    ) -> list[tuple[str, Any]]:
        from enum import Enum

        return [
            (name, member.name if isinstance(member, Enum) else member)
            for name, member in choices
        ]

    @model_validator(mode="after")
    def _rehydrate_members(self) -> EnumNode:
        """After JSON load, ``value`` / ``default`` / ``choices[i][1]`` may
        be strings (member names). Look up the Enum class and convert back.

        This runs on every validation including initial construction, but
        only mutates when the field is a string — Enum members short-circuit.
        """
        from enum import Enum

        enum_cls = self._lookup_enum_class()
        if enum_cls is None:
            # If the class can't be resolved (e.g., the module isn't
            # imported), skip rehydration and let downstream code see
            # raw strings. validate_value will catch this.
            return self

        def to_member(v: Any) -> Any:
            if isinstance(v, str) and not isinstance(v, Enum):
                try:
                    return enum_cls[v]
                except KeyError:
                    return v
            return v

        self.value = to_member(self.value)
        self.default = to_member(self.default)
        new_choices: list[tuple[str, Any]] = []
        for name, member in self.choices:
            new_choices.append((name, to_member(member)))
        self.choices = new_choices
        return self

    def _lookup_enum_class(self) -> Any:
        """Resolve ``enum_class_name`` (e.g. ``mymodule.Color``) via
        sys.modules. Returns the class, or None if not importable."""
        import sys
        from enum import Enum

        parts = self.enum_class_name.rsplit(".", 1)
        if len(parts) != 2:
            return None
        module_name, class_name = parts
        module = sys.modules.get(module_name)
        if module is None:
            return None
        cls = getattr(module, class_name, None)
        if cls is None or not (isinstance(cls, type) and issubclass(cls, Enum)):
            return None
        return cls

    def to_python(self) -> Any:
        return self.value

    def validate_value(self, value: Any) -> tuple[str, ...]:
        from enum import Enum

        if value is None:
            return () if not self.required else ("value is required",)
        if not isinstance(value, Enum):
            short_name = self.enum_class_name.rsplit(".", 1)[-1]
            return (f"{value!r} is not a {short_name} member",)
        # Compare by name to avoid identity drift across imports.
        if value.name not in [name for name, _ in self.choices]:
            short_name = self.enum_class_name.rsplit(".", 1)[-1]
            return (f"{value!r} is not a {short_name} member",)
        return ()


class LiteralNode(FormNode):
    """Holds a value drawn from a closed list defined by ``Literal[...]``.

    Literal values are always JSON-friendly primitives (str / int / bool /
    None / Enum members), so no special serializer is needed — Pydantic's
    default JSON encoding round-trips them correctly.
    """

    kind: Literal["literal"] = "literal"
    value: Any = None
    default: Any = None
    choices: list[Any] = []

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        return self.value

    def validate_value(self, value: Any) -> tuple[str, ...]:
        # If None is a declared choice, treat it like any other member.
        if value is None and None not in self.choices:
            return () if not self.required else ("value is required",)
        if value not in self.choices:
            return (f"{value!r} not in choices {self.choices!r}",)
        return ()


class SequenceNode(FormNode):
    """Container for list / set / tuple values.

    ``origin`` selects the Python container used by ``to_python``.
    ``item_type_name`` is the FQ name of the (homogeneous) item annotation,
    used by ``FormTree.add_item`` to build a fresh child via the registry.
    For fixed-length heterogeneous tuples (``origin="tuple_fixed"``),
    ``slot_type_names`` carries one FQ name per slot.
    """

    kind: Literal["sequence"] = "sequence"
    origin: Literal["list", "set", "tuple", "tuple_fixed"]
    items: "list[AnyNode]" = []
    item_type_name: str | None = None
    slot_type_names: list[str] | None = None
    min_length: int | None = None
    max_length: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        values = [it.to_python() for it in self.items]
        if self.origin == "list":
            return values
        if self.origin == "set":
            return set(values)
        # For fixed-length heterogeneous tuples: if every slot is None
        # (i.e. no existing data was provided), return None so GroupNode
        # can omit the key and let Pydantic apply the field's default.
        if self.origin == "tuple_fixed" and all(v is None for v in values):
            return None
        return tuple(values)  # both "tuple" and "tuple_fixed"

    def validate_value(self, value: Any) -> tuple[str, ...]:
        # Whole-sequence replacement isn't a typical mutation; renderers
        # use add_item / remove_item / move_item instead. Accept anything
        # iterable for now and let the schema do the work at submit time.
        return ()


class MappingNode(FormNode):
    """Container for ``dict[K, V]`` values.

    ``entries`` preserves insertion order; each entry is a (key_node,
    value_node) pair built from the corresponding annotations.
    """

    kind: Literal["mapping"] = "mapping"
    entries: "list[tuple[AnyNode, AnyNode]]" = []
    key_type_name: str
    value_type_name: str
    min_length: int | None = None
    max_length: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> dict[Any, Any]:
        return {k.to_python(): v.to_python() for k, v in self.entries}

    def validate_value(self, value: Any) -> tuple[str, ...]:
        return ()  # whole-mapping replacement deferred to v0.2


class UnionNode(FormNode):
    """Holds a value that could be one of several types.

    The user picks a variant; the node's ``selected`` carries the chosen
    variant's child node. ``variant_type_names`` records all candidate
    types for ``select_variant`` to rebuild on switch.
    """

    kind: Literal["union"] = "union"
    variant_type_names: list[str]
    selected_index: int | None = None
    selected: "AnyNode | None" = None

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    def to_python(self) -> Any:
        if self.selected is None:
            return None
        return self.selected.to_python()

    def validate_value(self, value: Any) -> tuple[str, ...]:
        # Per-leaf validation happens on the inner node; the union itself
        # accepts any value the user is staging.
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
    StringNode
    | IntNode
    | FloatNode
    | BoolNode
    | DecimalNode
    | DatetimeNode
    | DateNode
    | TimeNode
    | TimedeltaNode
    | EnumNode
    | LiteralNode
    | SequenceNode
    | MappingNode
    | UnionNode
    | GroupNode,
    Discriminator("kind"),
]


# Resolve the forward references inside GroupNode.fields, SequenceNode.items,
# MappingNode.entries, and UnionNode.selected.
GroupNode.model_rebuild()
SequenceNode.model_rebuild()
MappingNode.model_rebuild()
UnionNode.model_rebuild()


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

        Path segments may be field names (str) — for navigating into
        GroupNode children — or integer indices — for SequenceNode items
        and MappingNode entries (where the index targets the *value* side
        of the (key, value) pair). The terminal segment identifies the
        node whose ``value`` field is mutated.

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

        # Walk all but the last segment, pivoting on the current node's type.
        node: Any = self.root
        for seg in path_obj.segments[:-1]:
            node = self._descend(node, seg)

        # Resolve the terminal segment to a target node.
        last = path_obj.segments[-1]
        target = self._descend(node, last)

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

    def _descend(self, node: Any, seg: Any) -> Any:
        """Navigate one path segment into ``node``.

        Pivots on ``node``'s type:
        - GroupNode + str → child by name
        - SequenceNode + int → items[seg]
        - MappingNode + int → entries[seg][1] (the value node)

        Raises KeyError on any mismatch (out-of-range index, unknown name,
        or type/segment mismatch).
        """
        if isinstance(node, GroupNode) and isinstance(seg, str):
            child = node.find(seg)
            if child is None:
                msg = f"no field named {seg!r} at this level"
                raise KeyError(msg)
            return child
        if isinstance(node, SequenceNode) and isinstance(seg, int):
            if not (0 <= seg < len(node.items)):
                msg = f"index {seg} out of range for sequence of length {len(node.items)}"
                raise KeyError(msg)
            return node.items[seg]
        if isinstance(node, MappingNode) and isinstance(seg, int):
            if not (0 <= seg < len(node.entries)):
                msg = f"index {seg} out of range for mapping of length {len(node.entries)}"
                raise KeyError(msg)
            # Index into mapping selects the value side of the pair —
            # rename_key handles the key side via its dedicated mutation.
            return node.entries[seg][1]
        msg = (
            f"cannot navigate segment {seg!r} into {type(node).__name__} "
            f"(no rule for ({type(node).__name__}, {type(seg).__name__}))"
        )
        raise KeyError(msg)

    def _walk_to_sequence(self, path: str) -> SequenceNode:
        """Resolve ``path`` and return the SequenceNode at that location."""
        from pydantic_studio.tree.paths import Path as _Path

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            msg = "empty path"
            raise ValueError(msg)
        node: Any = self.root
        for seg in path_obj.segments:
            if isinstance(node, GroupNode) and isinstance(seg, str):
                child = node.find(seg)
                if child is None:
                    msg = f"no field named {seg!r}"
                    raise KeyError(msg)
                node = child
            else:
                msg = f"cannot navigate {seg!r}"
                raise KeyError(msg)
        if not isinstance(node, SequenceNode):
            msg = f"{path!r} is not a SequenceNode"
            raise TypeError(msg)
        return node

    def add_item(self, path: str, value: Any = None) -> ValidationResult:
        """Append a default child to the SequenceNode at ``path``."""
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        seq = self._walk_to_sequence(path)
        if seq.origin == "tuple_fixed":
            return ValidationResult.fail(["cannot add to a fixed-length tuple"])
        if seq.item_type_name is None:
            return ValidationResult.fail(["sequence has no item_type_name"])
        # Resolve + build BEFORE snapshotting — failure here must not pollute
        # the undo history (mirrors the validate-first contract of set_value).
        item_type = _resolve_type_name(seq.item_type_name)
        builder = default_registry().find(item_type)
        child = builder.build(item_type, FieldInfo(annotation=item_type), value)
        child.name = str(len(seq.items))
        self._push_snapshot(_snap.take(self.root))
        seq.items = [*seq.items, child]
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def remove_item(self, path: str, index: int) -> ValidationResult:
        """Remove the child at ``index`` from the SequenceNode at ``path``."""
        from pydantic_studio.tree import snapshots as _snap

        seq = self._walk_to_sequence(path)
        if not (0 <= index < len(seq.items)):
            return ValidationResult.fail([f"index {index} out of range"])
        self._push_snapshot(_snap.take(self.root))
        new_items = [it for i, it in enumerate(seq.items) if i != index]
        for i, it in enumerate(new_items):
            it.name = str(i)
        seq.items = new_items
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def insert_item(
        self, path: str, index: int, value: Any = None
    ) -> ValidationResult:
        """Insert a new child at ``index`` in the SequenceNode at ``path``."""
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        seq = self._walk_to_sequence(path)
        if seq.origin == "tuple_fixed":
            return ValidationResult.fail(
                ["cannot insert into a fixed-length tuple"]
            )
        if not (0 <= index <= len(seq.items)):
            return ValidationResult.fail([f"index {index} out of range"])
        if seq.item_type_name is None:
            return ValidationResult.fail(["sequence has no item_type_name"])
        item_type = _resolve_type_name(seq.item_type_name)
        builder = default_registry().find(item_type)
        child = builder.build(item_type, FieldInfo(annotation=item_type), value)
        self._push_snapshot(_snap.take(self.root))
        new_items = [*seq.items[:index], child, *seq.items[index:]]
        for i, it in enumerate(new_items):
            it.name = str(i)
        seq.items = new_items
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def move_item(
        self, path: str, from_index: int, to_index: int
    ) -> ValidationResult:
        """Move the child at ``from_index`` to ``to_index`` in the SequenceNode at ``path``."""
        from pydantic_studio.tree import snapshots as _snap

        seq = self._walk_to_sequence(path)
        if not (0 <= from_index < len(seq.items)):
            return ValidationResult.fail(
                [f"from_index {from_index} out of range"]
            )
        if not (0 <= to_index < len(seq.items)):
            return ValidationResult.fail(
                [f"to_index {to_index} out of range"]
            )
        self._push_snapshot(_snap.take(self.root))
        items = list(seq.items)
        item = items.pop(from_index)
        items.insert(to_index, item)
        for i, it in enumerate(items):
            it.name = str(i)
        seq.items = items
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def _walk_to_mapping(self, path: str) -> MappingNode:
        """Resolve ``path`` and return the MappingNode at that location."""
        from pydantic_studio.tree.paths import Path as _Path

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            msg = "empty path"
            raise ValueError(msg)
        node: Any = self.root
        for seg in path_obj.segments:
            if isinstance(node, GroupNode) and isinstance(seg, str):
                child = node.find(seg)
                if child is None:
                    msg = f"no field named {seg!r}"
                    raise KeyError(msg)
                node = child
            else:
                msg = f"cannot navigate {seg!r}"
                raise KeyError(msg)
        if not isinstance(node, MappingNode):
            msg = f"{path!r} is not a MappingNode"
            raise TypeError(msg)
        return node

    def add_entry(
        self, path: str, key: Any, value: Any = None
    ) -> ValidationResult:
        """Append a (key, value) entry to the MappingNode at ``path``."""
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        mp = self._walk_to_mapping(path)
        key_type = _resolve_type_name(mp.key_type_name)
        value_type = _resolve_type_name(mp.value_type_name)
        reg = default_registry()
        k_builder = reg.find(key_type)
        v_builder = reg.find(value_type)
        k_node = k_builder.build(key_type, FieldInfo(annotation=key_type), key)
        v_node = v_builder.build(value_type, FieldInfo(annotation=value_type), value)
        k_node.name = "key"
        v_node.name = "value"
        self._push_snapshot(_snap.take(self.root))
        mp.entries = [*mp.entries, (k_node, v_node)]
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def remove_entry(self, path: str, index: int) -> ValidationResult:
        """Remove the entry at ``index`` from the MappingNode at ``path``."""
        from pydantic_studio.tree import snapshots as _snap

        mp = self._walk_to_mapping(path)
        if not (0 <= index < len(mp.entries)):
            return ValidationResult.fail([f"index {index} out of range"])
        self._push_snapshot(_snap.take(self.root))
        mp.entries = [e for i, e in enumerate(mp.entries) if i != index]
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()

    def rename_key(
        self, path: str, index: int, new_key: Any
    ) -> ValidationResult:
        """Rename the key at ``index`` in the MappingNode at ``path``."""
        from pydantic_studio.tree import snapshots as _snap

        mp = self._walk_to_mapping(path)
        if not (0 <= index < len(mp.entries)):
            return ValidationResult.fail([f"index {index} out of range"])
        k_node, _v_node = mp.entries[index]
        errors = k_node.validate_value(new_key)
        if errors:
            return ValidationResult.fail(list(errors))
        # Validation passed — push snapshot and mutate.
        self._push_snapshot(_snap.take(self.root))
        k_node.value = new_key
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

    def _walk_to_union(self, path: str) -> UnionNode:
        from pydantic_studio.tree.paths import Path as _Path

        path_obj = _Path.parse(path)
        if not path_obj.segments:
            msg = "empty path"
            raise ValueError(msg)
        node: Any = self.root
        for seg in path_obj.segments:
            if isinstance(node, GroupNode) and isinstance(seg, str):
                child = node.find(seg)
                if child is None:
                    msg = f"no field named {seg!r}"
                    raise KeyError(msg)
                node = child
            else:
                msg = f"cannot navigate {seg!r}"
                raise KeyError(msg)
        if not isinstance(node, UnionNode):
            msg = f"{path!r} is not a UnionNode"
            raise TypeError(msg)
        return node

    def select_variant(
        self, path: str, variant_index: int, seed: Any = None
    ) -> ValidationResult:
        """Switch the UnionNode at ``path`` to its ``variant_index``-th variant.

        If ``seed`` is provided, the freshly-built variant is initialized
        with that value (otherwise its value is None / default).
        """
        from pydantic.fields import FieldInfo

        from pydantic_studio.tree import snapshots as _snap
        from pydantic_studio.tree.builder import default_registry

        union = self._walk_to_union(path)
        if not (0 <= variant_index < len(union.variant_type_names)):
            return ValidationResult.fail(
                [
                    f"variant index {variant_index} out of range "
                    f"(0..{len(union.variant_type_names) - 1})"
                ]
            )
        v_type = _resolve_type_name(union.variant_type_names[variant_index])
        builder = default_registry().find(v_type)
        new_selected = builder.build(v_type, FieldInfo(annotation=v_type), seed)
        self._push_snapshot(_snap.take(self.root))
        union.selected_index = variant_index
        union.selected = new_selected
        if self.draft_path is not None:
            _snap.draft_save(self, self.draft_path)
        return ValidationResult.ok()
