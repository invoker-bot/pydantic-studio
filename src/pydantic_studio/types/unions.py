"""Builder for union and Optional annotations.

Optional unions (T | None) are demoted: we strip None and return whatever
the inner builder produces, with ``required=False``. True multi-variant
unions become a UnionNode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
        from pydantic.fields import FieldInfo as _FI

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

        # True union: build a UnionNode. If existing matches one variant by
        # isinstance, pre-select that variant.
        variants = list(non_none_args)
        selected_index: int | None = None
        selected: Any = None
        if existing is not None:
            for i, v_type in enumerate(variants):
                try:
                    if isinstance(existing, v_type):
                        selected_index = i
                        v_finfo = _FI(annotation=v_type)
                        v_builder = self._registry.find(v_type)
                        selected = v_builder.build(v_type, v_finfo, existing)
                        break
                except TypeError:
                    continue

        default = field_info.get_default(call_default_factory=True)
        if default is PydanticUndefined:
            default = None
        # If no existing was provided but a default exists, pre-select via the
        # default's runtime type — same logic.
        if selected is None and default is not None:
            for i, v_type in enumerate(variants):
                try:
                    if isinstance(default, v_type):
                        selected_index = i
                        v_finfo = _FI(annotation=v_type)
                        v_builder = self._registry.find(v_type)
                        selected = v_builder.build(v_type, v_finfo, default)
                        break
                except TypeError:
                    continue

        return UnionNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            variant_type_names=[_fq(v) for v in variants],
            selected_index=selected_index,
            selected=selected,
        )
