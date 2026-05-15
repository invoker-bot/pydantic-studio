"""Breadcrumb widget for the TUI v2 ConfigScreen title bar.

Renders the navigation path as ``"a > b > c"`` (joined with U+203A
SINGLE RIGHT-POINTING ANGLE QUOTATION MARK). Past depth 3, the
middle parts collapse to ellipsis so the title bar stays within
modal width.
"""

from __future__ import annotations

from textual.widgets import Static

_SEP = " › "          # ' > ' with thin spaces
_ELLIPSIS = "…"       # ' ... '


class Breadcrumb(Static):
    """Single-line breadcrumb. Read ``label_text`` to inspect the rendered string."""

    DEFAULT_CSS = ""  # styling comes from theme.tcss

    def __init__(self, parts: list[str]) -> None:
        self._parts = list(parts)
        super().__init__(self._compute_label())

    @property
    def label_text(self) -> str:
        """The plain text of the breadcrumb (no markup)."""
        return self._compute_label()

    def _compute_label(self) -> str:
        if not self._parts:
            return ""
        if len(self._parts) <= 3:
            return _SEP.join(self._parts)
        # 4+ parts: keep first + last, collapse middle to ellipsis.
        return f"{self._parts[0]}{_SEP}{_ELLIPSIS}{_SEP}{self._parts[-1]}"
