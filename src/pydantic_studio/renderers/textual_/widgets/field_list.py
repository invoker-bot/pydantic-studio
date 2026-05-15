"""FieldListView — the scrollable vertical stack of FieldRows that
sits between the Breadcrumb and FooterHints inside a ConfigScreen.

Owns the focused-row cursor and translates up/down key events into
cursor moves. Scroll is delegated to Textual's VerticalScroll
container; we never set scroll_y manually.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll

from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow

if TYPE_CHECKING:
    from typing import ClassVar

    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import FormTree, GroupNode


class FieldListView(VerticalScroll):
    """Scrollable vertical stack of FieldRows for a GroupNode."""

    DEFAULT_CSS = ""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor_up", "up", show=False),
        Binding("down", "cursor_down", "down", show=False),
        Binding("enter", "activate_focused", "edit", show=False),
        Binding("space", "toggle_focused", "toggle", show=False),
        Binding("tab", "cycle_next_focused", "next", show=False, priority=True),
        Binding(
            "shift+tab", "cycle_prev_focused", "prev", show=False, priority=True
        ),
        Binding("escape", "cancel_focused", "cancel", show=False),
    ]

    def __init__(
        self,
        group: GroupNode,
        form_tree: FormTree,
        base_path: str = "",
    ) -> None:
        super().__init__()
        self._group = group
        self._form_tree = form_tree
        self._base_path = base_path
        self._cursor: int = 0

    @property
    def cursor(self) -> int:
        return self._cursor

    def compose(self) -> ComposeResult:
        for idx, child in enumerate(self._group.fields):
            path = (
                f"{self._base_path}.{child.name}" if self._base_path else child.name
            )
            yield FieldRow(
                node=child,
                path=path,
                form_tree=self._form_tree,
                focused=(idx == 0),
            )

    def action_cursor_up(self) -> None:
        if self._cursor <= 0:
            return
        self._move_cursor(self._cursor - 1)

    def action_cursor_down(self) -> None:
        if self._cursor >= len(self._group.fields) - 1:
            return
        self._move_cursor(self._cursor + 1)

    def _move_cursor(self, new_idx: int) -> None:
        rows = list(self.query(FieldRow))
        if not rows:
            return
        rows[self._cursor].set_focused(False)
        self._cursor = new_idx
        rows[new_idx].set_focused(True)
        # Let VerticalScroll bring the newly focused row into view.
        rows[new_idx].scroll_visible()

    def _focused_cell(self):
        """Return the Cell mounted inside the cursor-focused row, or None."""
        from pydantic_studio.renderers.textual_.widgets.cells import Cell

        rows = list(self.query(FieldRow))
        if not (0 <= self._cursor < len(rows)):
            return None
        try:
            return rows[self._cursor].query_one(Cell)
        except Exception:
            return None

    def action_activate_focused(self) -> None:
        """Enter on the focused row -> primary action of its cell."""
        from pydantic_studio.renderers.textual_.widgets.cells import (
            BoolCell,
            ChoiceCell,
        )

        cell = self._focused_cell()
        if cell is None:
            return
        if isinstance(cell, BoolCell):
            cell.toggle()
            return
        if isinstance(cell, ChoiceCell) and cell.large_choice:
            cell.open_chooser()
            return
        cell.enter_edit()

    def action_toggle_focused(self) -> None:
        """Space on the focused row -> toggle (BoolCell only)."""
        from pydantic_studio.renderers.textual_.widgets.cells import BoolCell

        cell = self._focused_cell()
        if isinstance(cell, BoolCell):
            cell.toggle()

    def action_cycle_next_focused(self) -> None:
        """Tab on the focused row -> cycle_next (ChoiceCell small only)."""
        from pydantic_studio.renderers.textual_.widgets.cells import ChoiceCell

        cell = self._focused_cell()
        if isinstance(cell, ChoiceCell) and not cell.large_choice:
            cell.cycle_next()

    def action_cycle_prev_focused(self) -> None:
        """Shift+Tab on the focused row -> cycle_prev (ChoiceCell small only)."""
        from pydantic_studio.renderers.textual_.widgets.cells import ChoiceCell

        cell = self._focused_cell()
        if isinstance(cell, ChoiceCell) and not cell.large_choice:
            cell.cycle_prev()

    def action_cancel_focused(self) -> None:
        """Esc on the focused row -> cancel_edit if editing."""
        cell = self._focused_cell()
        if cell is None:
            return
        if cell.editing:
            cell.cancel_edit()
