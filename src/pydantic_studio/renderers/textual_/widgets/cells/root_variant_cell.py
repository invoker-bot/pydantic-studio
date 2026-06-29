"""RootVariantCell -- display-only selector for FormTree root variants."""

from __future__ import annotations

from textual.widgets import Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell


class RootVariantCell(Cell):
    """Display the selected root variant; FieldListView owns cycling."""

    DEFAULT_CSS = ""

    @property
    def value_text(self) -> str:
        selected_id = getattr(self._node, "selected_id", "")
        label = selected_id
        for option in getattr(self._node, "options", []):
            if getattr(option, "id", None) == selected_id:
                label = getattr(option, "label", selected_id)
                break
        return f"‹ {label} ›"  # noqa: RUF001

    def compose(self):
        yield Static(self.value_text, classes="field-row--value", markup=False)
