"""TextCell — covers 16 leaf node kinds via parse_for_kind.

Form mode: hosts a persistent Input (see InputCell) — the focused
field is the editable field. Parsing routes through ``parse_for_kind``
so each kind keeps its wire syntax (hex for bytes, ISO for temporal…).
"""

from __future__ import annotations

from typing import Any

from pydantic_studio.renderers.textual_.widgets.cells.input_cell import InputCell
from pydantic_studio.renderers.textual_.widgets.cells.parse import parse_for_kind


class TextCell(InputCell):
    """Single-line persistent editor for textual leaf kinds."""

    @property
    def display_value(self) -> str:
        v = getattr(self._node, "value", None)
        if v is None:
            return ""
        if self._node.kind == "bytes" and isinstance(v, (bytes, bytearray)):
            return bytes(v).hex()
        return str(v)

    def parse(self, raw: str) -> tuple[bool, Any]:
        return parse_for_kind(self._node.kind, raw)
