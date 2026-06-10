"""BoolCell — Space toggles the value immediately.

No edit mode, no inline Input widget. The cell IS the toggle. Renders
``● on`` / ``○ off`` (fixed width so the column doesn't jitter); the
filled dot picks up the accent color via the ``-on`` class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell

if TYPE_CHECKING:
    from textual.app import ComposeResult


_OFF = "○ off"
_ON = "● on "


class BoolCell(Cell):
    """Inline toggle for BoolNode."""

    DEFAULT_CSS = ""

    @property
    def value_text(self) -> str:
        v = bool(getattr(self._node, "value", False) or False)
        return _ON if v else _OFF

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value", markup=False)

    def _sync_on_class(self) -> None:
        if bool(getattr(self._node, "value", False) or False):
            self.add_class("-on")
        else:
            self.remove_class("-on")

    def on_mount(self) -> None:
        self._sync_on_class()

    def toggle(self) -> None:
        """Flip the boolean and commit. No edit mode."""
        current = bool(getattr(self._node, "value", False) or False)
        self.commit(not current)
        self._sync_on_class()
        # Re-render the static.
        try:
            static = self.query_one(Static)
        except Exception:
            return
        static.update(self.value_text)
