"""AnyCell — JSON-aware persistent editor for ``typing.Any`` nodes.

Form mode: same InputCell contract as TextCell; values parse as JSON
when possible and fall back to plain text (matching the node's
mode-inference round-trip).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic_studio.io._json_strict import loads_strict_json
from pydantic_studio.renderers.textual_.widgets.cells.input_cell import InputCell


class AnyCell(InputCell):
    """Edit arbitrary values as JSON when possible, plain text otherwise."""

    @property
    def display_value(self) -> str:
        value = getattr(self._node, "value", None)
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def parse(self, raw: str) -> tuple[bool, Any]:
        stripped = raw.strip()
        if stripped == "":
            return True, None
        try:
            return True, loads_strict_json(stripped)
        except (json.JSONDecodeError, ValueError):
            return True, raw
