"""Builder for union and Optional annotations.

Optional unions (T | None) are demoted: we strip None and return whatever
the inner builder produces, with ``required=False``. True multi-variant
unions become a UnionNode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from pydantic_studio.tree.nodes import UnionNode
from pydantic_studio.types.annotated import (
    get_union_args,
    is_optional_type,
    is_union_type,
    strip_annotated,
)

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry


def _fq(t: Any) -> str:
    return f"{getattr(t, '__module__', 'builtins')}.{getattr(t, '__qualname__', repr(t))}"


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
            inner = inner_builder.build(inner_type, field_info, existing)
            inner.required = False  # Optional implies not required
            return inner

        variants = list(non_none_args)
        selected_index, selected = self._preselect(variants, existing)

        if selected is None:
            default = field_info.get_default(call_default_factory=True)
            if default is PydanticUndefined:
                default = None
            if default is not None:
                selected_index, selected = self._preselect(variants, default)

        return UnionNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            variant_type_names=[_fq(v) for v in variants],
            selected_index=selected_index,
            selected=selected,
        )

    def _preselect(
        self, variants: list[Any], candidate: Any
    ) -> tuple[int | None, Any]:
        """Find the first variant that ``candidate`` belongs to.

        Strategy: isinstance first (fast path for already-built instances);
        for BaseModel variants where isinstance fails, try model_validate
        (covers dict→model coercion). Build the variant node on success.
        """
        from pydantic.fields import FieldInfo as _FI

        if candidate is None:
            return None, None
        for i, v_type in enumerate(variants):
            try:
                if isinstance(candidate, v_type):
                    v_builder = self._registry.find(v_type)
                    selected = v_builder.build(
                        v_type, _FI(annotation=v_type), candidate
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
                    v_type, _FI(annotation=v_type), validated
                )
                return i, selected
        return None, None
