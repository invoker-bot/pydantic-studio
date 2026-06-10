"""FooterHints widget — context-sensitive keybind bar at the bottom
of the ConfigScreen.
"""

from __future__ import annotations

from typing import Literal

from textual.widgets import Static

Mode = Literal["idle", "editing", "sequence", "mapping", "union", "errors"]

_LINE1: dict[str, str] = {
    "idle": (
        "type to edit | Tab/Enter next | Space toggle | ←→ cycle | "
        "Ctrl+N next required | Ctrl+F filter | Esc revert/back"
    ),
    "editing": "type to edit | Enter commit+next | Esc revert",
    "sequence": (
        "Tab/Enter next | click [ + add item ] / ✕ | Del delete | "
        "Ctrl+↑↓ move | Esc back"
    ),
    "mapping": (
        "Tab/Enter next | click [ + add item ] / ✕ | F2 rename | "
        "Del delete | Esc back"
    ),
    "union": "←→ switch variant | Enter open | Esc back",
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
