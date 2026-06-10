"""Builder for nested Pydantic BaseModel subclasses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    PlainValidator,
    TypeAdapter,
    ValidationError,
    WrapValidator,
)

from pydantic_studio.tree.nodes import GroupNode

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry

_TRANSFORMING_VALIDATORS = (PlainValidator, BeforeValidator, WrapValidator)


def _has_transforming_validator(field_info: FieldInfo) -> bool:
    """True iff the field's metadata can rewrite the wire value into a
    different runtime representation (decrypt, normalize, …)."""
    return any(
        isinstance(meta, _TRANSFORMING_VALIDATORS) for meta in field_info.metadata
    )


def _parse_existing(field_info: FieldInfo, raw: Any) -> Any:
    """Run a raw on-disk value through the field's own validators.

    Loading must be symmetric with saving: ``model_dump`` applies
    serializers, so the tree has to hold *post-validator* (runtime)
    values or every transform gets re-applied on save (the
    double-encryption bug for encrypt/decrypt secret fields).

    ``ValidationError`` falls back to the raw value — the user may be
    repairing a broken file and needs to see what's on disk. Any other
    exception (e.g. a wrong decryption key) propagates: corrupting
    silently is worse than failing loudly.
    """
    annotation: Any = field_info.annotation
    if field_info.metadata:
        annotation = Annotated[tuple([annotation, *field_info.metadata])]
    try:
        return TypeAdapter(annotation).validate_python(raw)
    except ValidationError:
        return raw


class GroupBuilder:
    """Recursive builder for any ``BaseModel`` subclass.

    Owns a back-reference to the registry so it can dispatch each field of
    the model to whichever builder matches that field's annotation.
    """

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return isinstance(type_, type) and issubclass(type_, BaseModel)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> GroupNode:
        assert issubclass(type_, BaseModel)
        # ``UnionBuilder._preselect`` validates dict-shaped seeds against
        # BaseModel variants and passes the resulting instance through to
        # the inner builder. Accept that form by dumping back to the
        # plain Python dict the per-field child builders expect — without
        # this branch, seeded ``list[DiscriminatedUnion]`` data would lose
        # every inner field value and ``to_instance()`` would fail with
        # ``union_tag_not_found``.
        if isinstance(existing, BaseModel):
            existing_dict: dict[str, Any] = existing.model_dump(mode="python")
            # model_dump applies field serializers even in python mode —
            # for transform fields (encrypt/decrypt and friends) that
            # re-serializes the runtime value back into wire form. Pull
            # those straight off the instance instead.
            for fname, finfo in type(existing).model_fields.items():
                if fname in existing_dict and _has_transforming_validator(finfo):
                    existing_dict[fname] = getattr(existing, fname)
        elif isinstance(existing, dict):
            existing_dict = existing
        else:
            existing_dict = {}

        children: list[Any] = []
        for fname, finfo in type_.model_fields.items():
            child_type = finfo.annotation
            if child_type is None:
                child_type = str  # fallback — shouldn't happen in practice
            child_builder = self._registry.find(child_type)
            child_existing = existing_dict.get(fname)
            if child_existing is not None and _has_transforming_validator(finfo):
                child_existing = _parse_existing(finfo, child_existing)
            child = child_builder.build(child_type, finfo, child_existing)
            # The child builder uses ``field_info.alias`` (or "<unnamed>") as a
            # placeholder; overwrite with the real field-attribute name from
            # the parent's ``model_fields`` so users' aliases stay untouched.
            child.name = fname
            children.append(child)

        return GroupNode(
            name=field_info.alias or type_.__name__,
            description=field_info.description,
            required=field_info.is_required(),
            schema_class=type_,
            fields=children,
        )
