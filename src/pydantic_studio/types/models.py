"""Builder for nested Pydantic BaseModel subclasses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from pydantic_studio.tree.nodes import GroupNode

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.types.registry import Registry


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
        existing_dict: dict[str, Any] = existing if isinstance(existing, dict) else {}

        children: list[Any] = []
        for fname, finfo in type_.model_fields.items():
            child_type = finfo.annotation
            if child_type is None:
                child_type = str  # fallback — shouldn't happen in practice
            child_builder = self._registry.find(child_type)
            child = child_builder.build(child_type, finfo, existing_dict.get(fname))
            # The child builder didn't know the field name (it sees only the
            # type); we set it here from the parent's perspective. This avoids
            # the FieldInfo.alias hack and respects users' real aliases.
            child.name = fname
            children.append(child)

        return GroupNode(
            name=field_info.alias or type_.__name__,
            description=field_info.description,
            required=field_info.is_required(),
            schema_class=type_,
            fields=children,
        )
