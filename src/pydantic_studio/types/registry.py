"""NodeBuilder protocol and Registry.

Builders are kept in an ordered list; ``find`` returns the first builder
whose ``matches`` returns True. New registrations are *prepended* so user
code can override defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic_studio.exceptions import NoBuilderError

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from pydantic_studio.tree.nodes import AnyNode


@runtime_checkable
class NodeBuilder(Protocol):
    """A builder turns one Python type into a FormNode."""

    def matches(self, type_: type) -> bool: ...

    def build(
        self,
        type_: type,
        field_info: FieldInfo,
        existing: Any,
    ) -> AnyNode: ...


class Registry:
    """Ordered list of builders. First match wins."""

    def __init__(self) -> None:
        self._builders: list[NodeBuilder] = []

    def register(self, builder: NodeBuilder) -> None:
        """Prepend ``builder``; new registrations take priority."""
        self._builders.insert(0, builder)

    def register_fallback(self, builder: NodeBuilder) -> None:
        """Append ``builder``; checked only after every other builder.

        Use for catch-all builders (schema introspection, generic
        delegates) that must not shadow more-specific registrations.
        Re-registering a fallback moves it to the end again.
        """
        self._builders.append(builder)

    def find(self, type_: type) -> NodeBuilder:
        for b in self._builders:
            if b.matches(type_):
                return b
        raise NoBuilderError(type_)

    def __len__(self) -> int:
        return len(self._builders)
