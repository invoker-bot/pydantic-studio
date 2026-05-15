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
    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import GroupNode


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
