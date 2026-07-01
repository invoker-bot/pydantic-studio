"""Builder for union and Optional annotations.

Optional unions (T | None) are demoted: we strip None and return whatever
the inner builder produces, with ``required=False``. True multi-variant
unions become a UnionNode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from pydantic_studio.tree.nodes import GroupNode, MappingNode, SequenceNode, UnionNode
from pydantic_studio.types.annotated import (
    get_union_args,
    is_optional_type,
    is_union_type,
    strip_annotated,
)
from pydantic_studio.types.transforms import (
    field_info_from_annotation,
    has_transforming_validator,
    parse_existing_if_transforming,
    validate_existing,
)
from pydantic_studio.types.utils import _fq, field_default

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry


class UnionBuilder:
    """Builds either a UnionNode (true union) or delegates to the inner
    builder (Optional with one non-None variant)."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def matches(self, type_: type) -> bool:
        return is_union_type(type_)

    def build(self, type_: type, field_info: FieldInfo, existing: Any) -> Any:
        unwrapped = strip_annotated(type_)
        non_none_args = tuple(
            t for t in get_union_args(unwrapped) if t is not type(None)
        )

        # Optional[T] with a single non-None variant → just the inner builder
        # with required=False.
        if is_optional_type(unwrapped) and len(non_none_args) == 1:
            inner_type = non_none_args[0]
            inner_builder = self._registry.find(inner_type)
            inner_field_info = type(field_info).merge_field_infos(
                field_info,
                field_info_from_annotation(inner_type),
            )
            existing = parse_existing_if_transforming(inner_field_info, existing)
            inner = inner_builder.build(inner_type, inner_field_info, existing)
            inner.required = False  # Optional implies not required
            inner.nullable = True
            # Optional containers and models defaulting to None start
            # *omitted*: their child nodes may carry schema defaults for
            # display, but the field value is still None until the user
            # activates it. Without the flag, to_instance() would
            # materialize empty/defaulted structures instead of
            # round-tripping None.
            if (
                isinstance(inner, (GroupNode, SequenceNode, MappingNode))
                and existing is None
                and field_default(field_info) is None
            ):
                inner.omitted = True
            return inner

        variants = list(non_none_args)
        selected_index, selected = self._preselect(variants, existing)

        if selected is None:
            default = field_default(field_info)
            if default is not None:
                selected_index, selected = self._preselect(variants, default)

        union = UnionNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            nullable=is_optional_type(unwrapped),
            variant_type_names=[_fq(v) for v in variants],
            variant_annotations=variants,
            selected_index=selected_index,
            selected=selected,
        )
        union.validation_field_info = field_info if has_transforming_validator(field_info) else None
        return union

    def _preselect(
        self, variants: list[Any], candidate: Any
    ) -> tuple[int | None, Any]:
        """Find the first variant that ``candidate`` belongs to.

        Strategy: isinstance first (fast path for already-built instances);
        for BaseModel variants where isinstance fails, try model_validate
        (covers dict→model coercion). Build the variant node on success.
        """
        if candidate is None:
            return None, None
        transform_fallback: tuple[int, Any] | None = None
        for i, v_type in enumerate(variants):
            variant_field_info = field_info_from_annotation(v_type)
            if has_transforming_validator(variant_field_info):
                try:
                    parsed = validate_existing(variant_field_info, candidate)
                except ValidationError:
                    if transform_fallback is None:
                        v_builder = self._registry.find(v_type)
                        transform_fallback = (
                            i,
                            v_builder.build(v_type, variant_field_info, candidate),
                        )
                    continue
                v_builder = self._registry.find(v_type)
                selected = v_builder.build(v_type, variant_field_info, parsed)
                return i, selected
            try:
                if isinstance(candidate, v_type):
                    v_builder = self._registry.find(v_type)
                    selected = v_builder.build(
                        v_type, variant_field_info, candidate
                    )
                    return i, selected
            except TypeError:
                # Some types (Annotated, generics) reject isinstance; skip.
                continue
            # Dict→BaseModel coercion: when isinstance fails for a BaseModel
            # variant, see whether Pydantic could validate the candidate.
            if (
                isinstance(v_type, type)
                and issubclass(v_type, BaseModel)
                and isinstance(candidate, dict)
            ):
                try:
                    validated = v_type.model_validate(candidate)
                except Exception:
                    continue
                v_builder = self._registry.find(v_type)
                selected = v_builder.build(
                    v_type, variant_field_info, validated
                )
                return i, selected
        if transform_fallback is not None:
            return transform_fallback
        return None, None
