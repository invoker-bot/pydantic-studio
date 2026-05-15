"""FieldRow — per-field row chrome with per-kind cell dispatch.

Composes focus marker + label + dotted leader + value cell + drill
marker, plus an optional error helper line below. The value cell is
selected by ``make_cell(node, path, form_tree)`` from the cells
package. ``PlaceholderCell`` is gone — TextCell/BoolCell/ChoiceCell/
SecretCell cover M2's editable surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

from pydantic_studio.renderers.textual_.widgets.cells import make_cell

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import AnyNode, FormTree


_FOCUS_MARKER = "▸"
_LEADER = " " + ("· " * 5)
_DRILLABLE_KINDS = {"group", "sequence", "mapping", "union"}


class FieldRow(Widget):
    """One row in FieldListView. Dispatches to a per-kind Cell."""

    DEFAULT_CSS = ""

    def __init__(
        self,
        node: AnyNode,
        path: str,
        form_tree: FormTree,
        focused: bool = False,
    ) -> None:
        super().__init__()
        self._node = node
        self._path = path
        self._form_tree = form_tree
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
        if self._is_required_and_missing():
            return f"*{self._node.name}"
        return self._node.name

    def _is_required_and_missing(self) -> bool:
        """True iff this row's node is required and has no value yet.

        Only leaf nodes (those with a ``value`` attribute) participate
        — Group / Sequence / Mapping / Union containers never show a
        missing-marker on themselves, because drilling into them
        surfaces their own required children's markers.
        """
        node = self._node
        if not getattr(node, "required", False):
            return False
        if not hasattr(node, "value"):
            return False
        return getattr(node, "value", None) is None

    @property
    def marker_text(self) -> str:
        return _FOCUS_MARKER if self._focused else " "

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
        try:
            marker = self.query_one(".field-row--marker", Static)
            marker.update(self.marker_text)
        except Exception:
            return

    def set_error(self, message: str | None) -> None:
        self._error = message
        if message is None:
            self.remove_class("-error")
        else:
            self.add_class("-error")
        try:
            helper = self.query_one(".field-row--helper", Static)
            helper.update(self.helper_text)
        except Exception:
            return

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal():
                yield Static(self.marker_text, classes="field-row--marker")
                yield Static(self.label_text, classes="field-row--label")
                yield Static(_LEADER, classes="field-row--leader")
                yield make_cell(self._node, self._path, self._form_tree)
                yield Static(self.drill_marker_text, classes="field-row--drill")
            yield Static(self.helper_text, classes="field-row--helper")
