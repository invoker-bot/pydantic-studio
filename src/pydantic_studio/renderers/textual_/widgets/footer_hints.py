"""FooterHints widget — context-sensitive keybind bar at the bottom
of the ConfigScreen.
"""

from __future__ import annotations

from typing import Literal

from textual.widgets import Static

Mode = Literal["idle", "editing", "sequence", "mapping", "union", "errors"]

_LINE1: dict[str, str] = {
    "idle": (
        "Ctrl+S save+exit | Ctrl+C cancel | Up/Down navigate | Enter edit | "
        "Tab cycle | N next required | Esc back"
    ),
    "editing": "Ctrl+C cancel session | Enter commit | Esc cancel edit",
    "sequence": (
        "Ctrl+S save+exit | Ctrl+C cancel | Up/Down navigate | Enter edit | "
        "A add | D delete | Ctrl+Up/Down move | Esc back"
    ),
    "mapping": (
        "Ctrl+S save+exit | Ctrl+C cancel | Up/Down navigate | Enter edit | "
        "A add | R rename | D delete | Esc back"
    ),
    "union": "Ctrl+S save+exit | Ctrl+C cancel | Enter edit | Tab variant | Esc back",
    "errors": "Esc / Enter back to edit (cursor jumps to the first error)",
}
_LINE2 = ""


class FooterHints(Static):
    """Keybind bar. Read ``line1`` / ``line2`` for the raw strings."""

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
        if not self.line2:
            return self.line1
        return f"{self.line1}\n{self.line2}"
