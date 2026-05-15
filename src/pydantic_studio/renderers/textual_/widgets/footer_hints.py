"""FooterHints widget — context-sensitive 2-line keybind bar at the bottom
of the ConfigScreen. Line 1 changes with the active mode; line 2 is the
always-visible save/quit reminder.
"""

from __future__ import annotations

from typing import Literal

from textual.widgets import Static

Mode = Literal["idle", "editing", "sequence", "mapping", "errors"]

_LINE1: dict[str, str] = {
    "idle": "↑↓ navigate · Enter edit · Tab cycle · Esc back",
    "editing": "Type to edit · Enter commit · Esc cancel",
    "sequence": "↑↓ navigate · Enter edit · D delete · Esc back",
    "mapping": "↑↓ navigate · Enter edit · R rename · D delete · Esc back",
    "errors": "Esc back to edit · Enter jump to first error",
}
_LINE2 = "Ctrl+S save · Ctrl+Q quit"


class FooterHints(Static):
    """2-line keybind bar. Read ``line1`` / ``line2`` for the raw strings."""

    DEFAULT_CSS = ""  # styled via theme.tcss

    def __init__(self, mode: str = "idle") -> None:
        self._mode = mode
        super().__init__(self._compute_text())

    @property
    def line1(self) -> str:
        return _LINE1.get(self._mode, _LINE1["idle"])

    @property
    def line2(self) -> str:
        return _LINE2

    def set_mode(self, mode: str) -> None:
        """Swap the active mode and re-render. Used by ConfigScreen when
        focus enters an editing cell."""
        self._mode = mode
        self.update(self._compute_text())

    def _compute_text(self) -> str:
        return f"{self.line1}\n{self.line2}"
