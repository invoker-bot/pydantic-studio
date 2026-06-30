"""ContainerCell -- non-editing summaries for drillable container rows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell

if TYPE_CHECKING:
    from textual.app import ComposeResult


class ContainerCell(Cell):
    """Display a compact summary for group, sequence, mapping, and union nodes."""

    DEFAULT_CSS = ""

    @property
    def value_text(self) -> str:
        node = self._node
        if node.kind == "group":
            if not getattr(node, "required", True) and getattr(node, "omitted", False):
                return "not set"
            count = len(getattr(node, "fields", []))
            return f"{count} field{'s' if count != 1 else ''}"
        if node.kind == "sequence":
            count = len(getattr(node, "items", []))
            return f"{count} item{'s' if count != 1 else ''}"
        if node.kind == "mapping":
            count = len(getattr(node, "entries", []))
            return f"{count} entr{'ies' if count != 1 else 'y'}"
        if node.kind == "union":
            idx = getattr(node, "selected_index", None)
            names = getattr(node, "variant_type_names", [])
            if idx is None or not (0 <= idx < len(names)):
                return "select variant"
            return names[idx].rsplit(".", 1)[-1]
        return ""

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value", markup=False)
