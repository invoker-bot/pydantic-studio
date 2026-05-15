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

    def _focused_row(self) -> FieldRow | None:
        """Return the cursor-focused FieldRow, or None."""
        rows = list(self.query(FieldRow))
        if not (0 <= self._cursor < len(rows)):
            return None
        return rows[self._cursor]

    def action_activate_focused(self) -> None:
        """Enter on the focused row -> drill-down (container) or edit (leaf).

        Drill-down takes priority over cell editing: Enter on a Group
        row pushes a child ConfigScreen scoped to that group's fields.
        Sequence / Mapping / Union containers are deferred to a later
        milestone (their cell stub falls through to enter_edit, which
        is a no-op for non-text kinds).
        """
        from pydantic_studio.renderers.textual_.widgets.cells import (
            BoolCell,
            ChoiceCell,
        )
        from pydantic_studio.tree.nodes import GroupNode

        row = self._focused_row()
        if row is not None and isinstance(row.node, GroupNode):
            self._push_child_screen(row.node)
            return

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

    def _push_child_screen(self, group) -> None:
        """Push a child ConfigScreen scoped to ``group``.

        Inherits the parent screen's breadcrumb parts and appends the
        group's name. Uses late imports to break the screens <-> widgets
        cycle (screens.py imports FieldListView; FieldListView pushing
        a screen needs ConfigScreen).
        """
        from pydantic_studio.renderers.textual_.screens import ConfigScreen

        parent = self.screen
        parent_parts = list(getattr(parent, "_breadcrumb_parts", []))
        parts = [*parent_parts, group.name]
        self.app.push_screen(
            ConfigScreen(
                group=group,
                form_tree=self._form_tree,
                breadcrumb_parts=parts,
            )
        )

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
        """Esc on the focused row.

        - If a cell is in edit mode → cancel the edit (in-place).
        - Else if the active screen is a drilled-in child (more than
          one ConfigScreen on the stack) → pop one level.
        - Else (root screen, no edit) → no-op.
        """
        from pydantic_studio.renderers.textual_.screens import ConfigScreen

        cell = self._focused_cell()
        if cell is not None and cell.editing:
            cell.cancel_edit()
            return
        config_screens = [
            s for s in self.app.screen_stack if isinstance(s, ConfigScreen)
        ]
        if len(config_screens) > 1:
            self.app.pop_screen()
