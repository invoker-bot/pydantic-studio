"""SecretCell — persistent masked Input for SecretNode.

Form mode: the Input lives with ``password=True`` so the value renders
as bullets at all times, typing included. The plaintext never appears
on screen; it remains in the widget value for editing.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic_studio.renderers.textual_.widgets.cells.input_cell import InputCell


class SecretCell(InputCell):
    """Masked persistent editor for SecretNode."""

    password: ClassVar[bool] = True

    @property
    def display_value(self) -> str:
        v = getattr(self._node, "value", None)
        if v is None:
            return ""
        if hasattr(v, "get_secret_value"):
            inner = v.get_secret_value()
            if isinstance(inner, bytes):
                return inner.decode("utf-8", errors="replace")
            return str(inner)
        if isinstance(v, bytes):
            return v.decode("utf-8", errors="replace")
        return str(v)

    def parse(self, raw: str) -> tuple[bool, Any]:
        if getattr(self._node, "secret_kind", None) == "bytes":
            return True, raw.encode()
        return True, raw
