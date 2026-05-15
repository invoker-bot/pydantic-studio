"""FieldRow shell + PlaceholderCell for the TUI v2 chrome.

M1 ships the row chrome (focus marker, label, dotted leader, value
cell slot, drill marker, optional error helper). The value cell is a
PlaceholderCell that just stringifies node.value; M2 replaces it with
per-kind editor cells (TextCell / BoolCell / ChoiceCell / SecretCell).
The drill-marker logic for container kinds is wired here so the layout
is final, even though Enter-to-drill doesn't fire until M3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import AnyNode


_FOCUS_MARKER = "▸"  # filled right-pointing small triangle
_LEADER = " " + ("· " * 5)  # middle-dot leader

_DRILLABLE_KINDS = {"group", "sequence", "mapping", "union"}


class PlaceholderCell(Widget):
    """Minimal value cell for M1: stringifies node.value (or empty for None).

    Replaced by real cells in M2. Kept as a separate widget so M2's
    cell tests can be authored independently.
    """

    DEFAULT_CSS = ""

    def __init__(self, node: AnyNode) -> None:
        super().__init__()
        self._node = node

    @property
    def value_text(self) -> str:
        v = getattr(self._node, "value", None)
        return "" if v is None else str(v)

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value")


class FieldRow(Widget):
    """One row in the FieldListView.

    Composes marker + label + leader + value cell + drill marker, plus
    an optional error helper line below.
    """

    DEFAULT_CSS = ""

    def __init__(
        self,
        node: AnyNode,
        path: str,
        focused: bool = False,
    ) -> None:
        super().__init__()
        self._node = node
        self._path = path
        self._focused = focused
        self._error: str | None = None
        if focused:
            self.add_class("-focused")

    @property
    def node(self) -> AnyNode:
        return self._node

    @property
    def path(self) -> str:
        return self._path

    @property
    def label_text(self) -> str:
        return self._node.name

    @property
    def marker_text(self) -> str:
        return _FOCUS_MARKER if self._focused else " "

    @property
    def value_text(self) -> str:
        # Proxy through the inner PlaceholderCell so tests can hit it
        # without having to query the child widget tree.
        return PlaceholderCell(self._node).value_text

    @property
    def drill_marker_text(self) -> str:
        return ">" if self._node.kind in _DRILLABLE_KINDS else ""

    @property
    def helper_text(self) -> str:
        return "" if self._error is None else f"[!] {self._error}"

    def set_focused(self, focused: bool) -> None:
        self._focused = focused
        if focused:
            self.add_class("-focused")
        else:
            self.remove_class("-focused")
        self._refresh_marker()

    def set_error(self, message: str | None) -> None:
        self._error = message
        if message is None:
            self.remove_class("-error")
        else:
            self.add_class("-error")
        self._refresh_helper()

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal():
                yield Static(self.marker_text, classes="field-row--marker")
                yield Static(self.label_text, classes="field-row--label")
                yield Static(_LEADER, classes="field-row--leader")
                yield PlaceholderCell(self._node)
                yield Static(self.drill_marker_text, classes="field-row--drill")
            yield Static(self.helper_text, classes="field-row--helper")

    def _refresh_marker(self) -> None:
        # Query the marker Static and rewrite it. Cheap, avoids a full
        # recompose which would churn the value cell.
        try:
            marker = self.query_one(".field-row--marker", Static)
        except Exception:
            return
        marker.update(self.marker_text)

    def _refresh_helper(self) -> None:
        try:
            helper = self.query_one(".field-row--helper", Static)
        except Exception:
            return
        helper.update(self.helper_text)
