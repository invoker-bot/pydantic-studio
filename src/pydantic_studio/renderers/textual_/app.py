"""StudioApp — the Textual App entry point for pydantic-studio."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree


class StudioApp(App):
    """Textual application that hosts the form-tree editor.

    Args:
        tree: the FormTree to edit (typically built via
            ``build_form_tree`` or ``load_yaml``).
        save_path: optional path to write to on Ctrl+S. None disables
            save (read-only mode).

    Note:
        Textual's :class:`textual.app.App` ships a read-only ``tree``
        property (a Rich renderable of the DOM, used for debugging via
        ``self.log(self.tree)``). We override it with a writable
        property in this subclass so callers and widgets can reach the
        :class:`FormTree` via ``app.tree``. The parent's DOM-debug
        renderable is rarely useful in production code.
    """

    CSS = ""  # custom theme CSS lands in Plan 8

    def __init__(
        self,
        tree: FormTree,
        save_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self._tree = tree
        self.save_path = Path(save_path) if save_path is not None else None

    @property
    def tree(self) -> FormTree:  # type: ignore[override]
        """The :class:`FormTree` being edited.

        Overrides Textual's read-only ``App.tree`` (a Rich DOM
        renderable) with our editable form tree.
        """
        return self._tree

    @tree.setter
    def tree(self, value: FormTree) -> None:
        self._tree = value

    def on_mount(self) -> None:
        import os

        if os.environ.get("PYDANTIC_STUDIO_TUI_V2") == "1":
            # M1+ chrome path; cells / drill / save land in M2-M5.
            from pydantic_studio.renderers.textual_.screens import ConfigScreen

            short_name = (
                self.tree.schema_name.split(":")[-1]
                if ":" in self.tree.schema_name
                else self.tree.schema_name
            )
            self.push_screen(
                ConfigScreen(group=self.tree.root, breadcrumb_parts=[short_name])
            )
            return

        # Legacy default — unchanged.
        from pydantic_studio.renderers.textual_.screens import EditorScreen

        self.push_screen(EditorScreen())

    async def action_quit(self) -> None:  # type: ignore[override]
        """Delegate quit to the active screen so the EditorScreen's
        unsaved-changes prompt runs before exit. Falls back to the
        framework default if the active screen has no quit handler.
        """
        screen = self.screen
        screen_quit = getattr(screen, "action_quit", None)
        if screen_quit is not None and not isinstance(screen, App):
            screen_quit()
            return
        self.exit()


def run_app(tree: FormTree, save_path: str | Path | None = None) -> None:
    """Launch the StudioApp synchronously. Blocks until the user quits."""
    app = StudioApp(tree=tree, save_path=save_path)
    app.run()
