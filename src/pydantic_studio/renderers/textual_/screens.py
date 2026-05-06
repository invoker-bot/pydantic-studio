"""Textual Screen for the editor — wraps the three-region layout."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header

from pydantic_studio.renderers.textual_.widgets.editor import EditorPane
from pydantic_studio.renderers.textual_.widgets.preview import PreviewPane
from pydantic_studio.renderers.textual_.widgets.sidebar import Sidebar

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType


class EditorScreen(Screen):
    """Single-screen layout: sidebar | editor | preview."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar(self.app.tree)
            yield EditorPane(self.app.tree)
            yield PreviewPane(self.app.tree)
        yield Footer()

    def action_quit(self) -> None:
        self.app.exit()

    def refresh_preview(self) -> None:
        """Called by NodeEditor.commit() after a successful set_value."""
        try:
            preview = self.query_one(PreviewPane)
        except Exception:
            return
        preview.refresh_preview()

    def on_tree_node_selected(self, event) -> None:
        """Sidebar emits this when the user picks a group. Update the
        EditorPane to focus that group's children."""
        path = event.node.data or ""
        try:
            editor = self.query_one(EditorPane)
        except Exception:
            return
        group = self._resolve_group(path)
        if group is not None:
            editor.set_group(group, path)

    def _resolve_group(self, path: str):
        """Walk ``self.app.tree.root`` along ``path`` and return the GroupNode."""
        from pydantic_studio.tree.nodes import GroupNode

        if path == "":
            return self.app.tree.root
        node = self.app.tree.root
        for seg in path.split("."):
            if not isinstance(node, GroupNode):
                return None
            child = node.find(seg)
            if child is None:
                return None
            node = child
        if isinstance(node, GroupNode):
            return node
        return None
