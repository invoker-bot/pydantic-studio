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
        ("ctrl+s", "save", "Save"),
        ("ctrl+z", "undo", "Undo"),
        ("ctrl+y", "redo", "Redo"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._last_save_snapshot_count: int = 0
        self._quit_confirm_active: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar(self.app.tree)
            yield EditorPane(self.app.tree)
            yield PreviewPane(self.app.tree)
        yield Footer()

    def action_quit(self) -> None:
        """Quit. If dirty, show a confirm prompt; otherwise exit immediately.

        First Ctrl+Q on dirty tree → set _quit_confirm_active + notify.
        Second Ctrl+Q within the window → exit unconditionally.
        Esc → cancel the prompt (handled in on_key).
        """
        if getattr(self, "_quit_confirm_active", False):
            # Confirm-discard.
            self.app.exit()
            return
        is_dirty = (
            len(self.app.tree.snapshots)
            > getattr(self, "_last_save_snapshot_count", 0)
        )
        if not is_dirty:
            self.app.exit()
            return
        self._quit_confirm_active = True
        self.notify(
            "Unsaved changes! Press Ctrl+Q again to discard, Esc to cancel.",
            severity="warning",
            timeout=10,
        )

    def on_key(self, event) -> None:
        if (
            getattr(self, "_quit_confirm_active", False)
            and event.key == "escape"
        ):
            self._quit_confirm_active = False

    def action_save(self) -> None:
        """Persist the tree to save_path. No-op if save_path is None."""
        save_path = self.app.save_path
        if save_path is None:
            self.notify("Read-only mode (no save path)", severity="warning")
            return
        try:
            from pydantic_studio import save_yaml

            save_yaml(self.app.tree, save_path)
            self.notify(f"Saved to {save_path}", severity="information")
            self._last_save_snapshot_count = len(self.app.tree.snapshots)
        except Exception as e:
            self.notify(f"Save failed: {e}", severity="error", timeout=8)

    def action_undo(self) -> None:
        if self.app.tree.undo():
            self._reload_editor_pane()
            self.refresh_preview()

    def action_redo(self) -> None:
        if self.app.tree.redo():
            self._reload_editor_pane()
            self.refresh_preview()

    def _reload_editor_pane(self) -> None:
        """After undo/redo the FormTree was rehydrated from a snapshot —
        re-mount the editor pane so its widgets reflect the new state."""
        try:
            editor = self.query_one(EditorPane)
        except Exception:
            return
        # Re-resolve the focused group at the same path.
        path = getattr(editor, "_current_group_path", "")
        group = self._resolve_group(path)
        if group is not None:
            editor.set_group(group, path)

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
