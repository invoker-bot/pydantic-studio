"""Helpers for field annotations that transform loaded wire values."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BeforeValidator, PlainValidator, TypeAdapter, ValidationError, WrapValidator
from pydantic.fields import FieldInfo

_TRANSFORMING_VALIDATORS = (PlainValidator, BeforeValidator, WrapValidator)


def field_info_from_annotation(annotation: Any) -> FieldInfo:
    """Build FieldInfo while preserving Annotated metadata."""
    return FieldInfo.from_annotation(annotation)


def has_transforming_validator(field_info: FieldInfo) -> bool:
    """True iff ``field_info`` metadata can rewrite the wire value."""
    return any(
        isinstance(meta, _TRANSFORMING_VALIDATORS) for meta in field_info.metadata
    )


def _annotation_with_metadata(field_info: FieldInfo) -> Any:
    annotation: Any = field_info.annotation
    if field_info.metadata:
        annotation = Annotated[tuple([annotation, *field_info.metadata])]
    return annotation


def validate_existing(field_info: FieldInfo, raw: Any) -> Any:
    return TypeAdapter(_annotation_with_metadata(field_info)).validate_python(raw)


def parse_existing(field_info: FieldInfo, raw: Any) -> Any:
    """Run a raw on-disk value through the field's own validators.

    Loading must be symmetric with saving: ``model_dump`` applies
    serializers, so the tree has to hold *post-validator* (runtime)
    values or every transform gets re-applied on save.

    ``ValidationError`` falls back to the raw value — the user may be
    repairing a broken file and needs to see what's on disk. Any other
    exception (e.g. a wrong decryption key) propagates: corrupting
    silently is worse than failing loudly.
    """
    try:
        return validate_existing(field_info, raw)
    except ValidationError:
        return raw


def parse_existing_if_transforming(field_info: FieldInfo, existing: Any) -> Any:
    if existing is not None and has_transforming_validator(field_info):
        return parse_existing(field_info, existing)
    return existing
