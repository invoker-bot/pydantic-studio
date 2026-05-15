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

    from pydantic_studio.tree.nodes import GroupNode


class FieldListView(VerticalScroll):
    """Scrollable vertical stack of FieldRows for a GroupNode."""

    DEFAULT_CSS = ""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor_up", "up", show=False),
        Binding("down", "cursor_down", "down", show=False),
    ]

    def __init__(self, group: GroupNode, base_path: str = "") -> None:
        super().__init__()
        self._group = group
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
            yield FieldRow(node=child, path=path, focused=(idx == 0))

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
