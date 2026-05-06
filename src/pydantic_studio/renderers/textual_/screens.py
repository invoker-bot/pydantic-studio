"""Textual Screen for the editor — wraps the three-region layout."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from pydantic_studio.renderers.textual_.widgets.sidebar import Sidebar

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType


class EditorScreen(Screen):
    """Single-screen layout: sidebar | editor | preview.

    Phase-5 scaffold uses Static placeholders. Tasks 3-5 replace each
    region with real widgets (Sidebar, EditorPane, PreviewPane).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar(self.app.tree)
            yield Static("[editor]", id="editor-placeholder")
            yield Static("[preview]", id="preview-placeholder")
        yield Footer()

    def action_quit(self) -> None:
        self.app.exit()
