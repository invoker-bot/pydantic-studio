"""Textual screens for pydantic-studio.

After the M1 cutover, the only screen is ``ConfigScreen`` — the
single-panel Claude Code /config-style editor. The legacy three-pane
``EditorScreen`` (sidebar + editor pane + preview) was retired along
with its supporting widgets in `widgets/scalars.py`, `containers.py`,
`editor.py`, `sidebar.py`, `preview.py`. M2-M5 build editing /
drill-down / save flow on top of ConfigScreen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.screen import Screen

from pydantic_studio.renderers.textual_.widgets.breadcrumb import Breadcrumb
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.footer_hints import FooterHints

if TYPE_CHECKING:
    from typing import Any

    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import AnyNode, FormTree, GroupNode


class ConfigScreen(Screen):
    """TUI v2 single-panel screen: Breadcrumb + FieldListView + FooterHints.

    M1 ships the chrome with PlaceholderCell value rendering. Editing
    cells, container drill-down, sequence/mapping management, union
    cycling, and the errors screen land in M2-M5.
    """

    CSS_PATH = "theme.tcss"

    def __init__(
        self,
        group: GroupNode,
        breadcrumb_parts: list[str],
    ) -> None:
        super().__init__()
        self._group = group
        self._breadcrumb_parts = breadcrumb_parts

    def compose(self) -> ComposeResult:
        yield Breadcrumb(parts=self._breadcrumb_parts)
        yield FieldListView(group=self._group, base_path="")
        yield FooterHints(mode="idle")


class ChooserScreen(Screen):
    """Push-screen presenter for ChoiceCell large-choice fields.

    Lists all options; up/down to navigate, Enter to commit + pop.
    """

    CSS_PATH = "theme.tcss"

    def __init__(
        self,
        node: AnyNode,
        path: str,
        form_tree: FormTree,
    ) -> None:
        super().__init__()
        self._node = node
        self._path = path
        self._form_tree = form_tree

    @property
    def options(self) -> list[tuple[str, Any]]:
        if self._node.kind == "enum":
            from pydantic_studio.renderers.textual_.widgets.cells.labels import enum_label

            return [(enum_label(member), member) for _, member in self._node.choices]
        return [(str(c), c) for c in self._node.choices]

    def select(self, idx: int) -> None:
        if not (0 <= idx < len(self.options)):
            return
        _, value = self.options[idx]
        self._form_tree.set_value(self._path, value)
        self.app.pop_screen()

    def compose(self) -> ComposeResult:
        from textual.widgets import Label, ListItem, ListView

        with ListView(id="chooser-list"):
            for label, _ in self.options:
                yield ListItem(Label(label))
