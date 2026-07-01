"""Builder for ``typing.Any`` fields and items.

Pydantic accepts ``Any`` as an "anything goes" escape hatch —
pydantic-studio represents that with ``AnyValueNode``, a polymorphic
node whose ``mode`` discriminator indicates the value's runtime shape.
Round-trip is direct: the value is held as-is and ``Any`` does no
validation on the way back.

Containers parameterised over ``Any`` (``dict[str, Any]`` /
``list[Any]``) are handled by the existing container builders, which
call ``registry.find(typing.Any)`` per item — landing here. Each entry
gets its own ``AnyValueNode`` with an independently-inferred mode, so
heterogeneous payloads (``{"a": "s", "b": 7, "c": [1, 2]}``) display
sensibly without any extra wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_studio.tree.nodes import AnyValueNode
from pydantic_studio.types.utils import field_default

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


class AnyBuilder:
    """Builds an ``AnyValueNode`` for ``typing.Any`` annotations."""

    def matches(self, type_: type) -> bool:
        # ``typing.Any`` is a singleton sentinel — identity check is the
        # canonical way to recognise it. ``object`` is intentionally
        # excluded: someone annotating with bare ``object`` is making a
        # different statement (covariant base) than with ``Any`` (escape
        # hatch).
        return type_ is Any

    def build(
        self,
        type_: type,
        field_info: FieldInfo,
        existing: Any,
    ) -> AnyValueNode:
        seed = existing if existing is not None else field_default(field_info)
        return AnyValueNode(
            name=field_info.alias or "<unnamed>",
            description=field_info.description,
            required=field_info.is_required(),
            nullable=True,
            mode=AnyValueNode.infer_mode(seed),
            value=seed,
        )
