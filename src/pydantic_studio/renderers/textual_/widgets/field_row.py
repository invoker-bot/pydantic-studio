"""FieldRow — per-field row chrome with per-kind cell dispatch.

Composes focus marker + label + dotted leader + value cell + drill
marker (+ a clickable ✕ on container screens), plus an optional error
helper line below. The value cell is selected by
``make_cell(node, path, form_tree)`` from the cells package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from pydantic_studio.renderers.textual_.widgets.cells import (
    CellValueChanged,
    make_cell,
)

if TYPE_CHECKING:
    from textual import events
    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import AnyNode, FormTree


_FOCUS_MARKER = "▎"  # slim accent bar, colored via .-focused css
_REQUIRED_BADGE = "●"  # amber dot while a required field is still unset
_DRILLABLE_KINDS = {"group", "sequence", "mapping", "union"}


@dataclass
class RowClicked(Message):
    """Mouse click on a row's chrome — FieldListView moves the cursor."""

    path: str


@dataclass
class RowDeleteRequested(Message):
    """Click on a row's ✕ mark (container screens only)."""

    path: str


class _DeleteMark(Static):
    """The clickable ✕ at the end of sequence/mapping item rows."""

    def __init__(self, path: str) -> None:
        super().__init__("✕", classes="field-row--x", markup=False)
        self._path = path

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(RowDeleteRequested(path=self._path))


class FieldRow(Widget):
    """One row in FieldListView. Dispatches to a per-kind Cell."""

    DEFAULT_CSS = ""

    def __init__(
        self,
        node: AnyNode,
        path: str,
        form_tree: FormTree,
        focused: bool = False,
        label_override: str | None = None,
        readonly: bool = False,
        label_width: int | None = None,
        deletable: bool = False,
    ) -> None:
        super().__init__()
        self._node = node
        self._path = path
        self._form_tree = form_tree
        self._focused = focused
        self._label_override = label_override
        self._readonly = readonly
        self._label_width = label_width
        self._deletable = deletable
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
    def readonly(self) -> bool:
        return self._readonly

    @property
    def label_text(self) -> str:
        label = (
            self._label_override
            if self._label_override is not None
            else self._node.name
        )
        if self._readonly:
            label += "  🔒"
        if self._label_width is not None and len(label) > self._label_width:
            # Honest truncation: a real ellipsis instead of the silent
            # hard cut that made auto_tracking_orders_a/_b identical.
            label = label[: self._label_width - 1] + "…"
        return label

    @property
    def required_badge_text(self) -> str:
        """Amber ● while required-and-unset; clears once a value lands."""
        return _REQUIRED_BADGE if self._is_required_and_missing() else " "

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
        return "›" if self._node.kind in _DRILLABLE_KINDS else ""  # noqa: RUF001

    @property
    def helper_text(self) -> str:
        return "" if self._error is None else f"↳ {self._error}"

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

    def on_edit_mode_exited(self) -> None:
        """Refresh row chrome after a legacy modal cell commits or cancels."""
        self._refresh_chrome()

    def on_cell_value_changed(self, event: CellValueChanged) -> None:
        """Refresh row chrome after a form-mode commit attempt / revert.

        Don't stop the event — ConfigScreen also listens to refresh the
        HelpBar's missing-required counter.
        """
        self._refresh_chrome(error=event.error)

    def _refresh_chrome(self, error: str | None = None) -> None:
        try:
            label = self.query_one(".field-row--label", Static)
            label.update(self.label_text)
            badge = self.query_one(".field-row--required", Static)
            badge.update(self.required_badge_text)
        except Exception:
            pass
        if error is not None:
            self.set_error(error)
            return
        try:
            from pydantic_studio.renderers.textual_.widgets.cells import Cell

            cell = self.query_one(Cell)
            self.set_error(getattr(cell, "last_error", None))
        except Exception:
            pass

    def on_click(self, event: events.Click) -> None:
        """Click on the row chrome (label/marker/leader/value statics).

        Clicks landing on the cell's Input are consumed by the Input
        itself (focus) and reach the cursor via DescendantFocus instead.
        """
        event.stop()
        self.post_message(RowClicked(path=self._path))

    def compose(self) -> ComposeResult:
        with Vertical(classes="field-row--stack"):
            with Horizontal(classes="field-row--line"):
                yield Static(
                    self.marker_text, classes="field-row--marker", markup=False
                )
                label = Static(
                    self.label_text, classes="field-row--label", markup=False
                )
                if self._label_width is not None:
                    # Inline style beats the fixed width in theme.tcss —
                    # the column is sized to the longest label on screen.
                    label.styles.width = self._label_width
                yield label
                yield Static(
                    self.required_badge_text,
                    classes="field-row--required",
                    markup=False,
                )
                cell = make_cell(self._node, self._path, self._form_tree)
                cell.add_class("field-row--cell")
                if self._readonly:
                    # Physical enforcement: a disabled cell can't take
                    # focus or input; the guard messages stay for keys.
                    cell.disabled = True
                yield cell
                yield Static(
                    self.drill_marker_text, classes="field-row--drill", markup=False
                )
                if self._deletable:
                    yield _DeleteMark(self._path)
            yield Static(self.helper_text, classes="field-row--helper", markup=False)
