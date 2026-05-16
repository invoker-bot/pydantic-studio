"""StudioApp — the Textual App entry point for pydantic-studio."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App
from textual.binding import Binding

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop
    from typing import ClassVar

    from textual.app import AutopilotCallbackType
    from textual.binding import BindingType

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

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+s", "save", "save", priority=True),
        Binding("ctrl+c", "quit", "quit", priority=True),
    ]

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
        from pydantic_studio.renderers.textual_.screens import ConfigScreen

        short_name = (
            self.tree.schema_name.split(":")[-1]
            if ":" in self.tree.schema_name
            else self.tree.schema_name
        )
        self.push_screen(
            ConfigScreen(
                group=self.tree.root,
                form_tree=self.tree,
                breadcrumb_parts=[short_name],
            )
        )

    def run(
        self,
        *,
        headless: bool = False,
        inline: bool = False,
        inline_no_clear: bool = False,
        mouse: bool = False,
        size: tuple[int, int] | None = None,
        auto_pilot: AutopilotCallbackType | None = None,
        loop: AbstractEventLoop | None = None,
    ):
        """Run with mouse reporting off so terminals keep native copy behavior."""
        return super().run(
            headless=headless,
            inline=inline,
            inline_no_clear=inline_no_clear,
            mouse=mouse,
            size=size,
            auto_pilot=auto_pilot,
            loop=loop,
        )

    async def action_quit(self) -> None:  # type: ignore[override]
        """Delegate quit to the active screen if it defines its own
        unsaved-changes prompt. Falls back to the framework default
        otherwise. M2's save flow on ConfigScreen will hook in here.
        """
        screen = self.screen
        screen_quit = getattr(screen, "action_quit", None)
        if screen_quit is not None and not isinstance(screen, App):
            screen_quit()
            return
        self.exit()

    def action_save(self) -> None:
        """Persist ``self.tree`` to ``self.save_path``.

        - No ``save_path`` configured: emit a warning notification.
        - Tree is invalid: emit an error notification with the count of
          validation errors and leave the on-disk file untouched.
        - Tree is valid: write the YAML and emit a confirmation.

        Splitting "valid" from "invalid" via :exc:`ValidationFailedError`
        keeps the contract that ``save_yaml`` is strict and never writes
        a partial tree (CLAUDE.md "core invariants" §5). Mid-edit drafts
        are a separate concern handled at quit time, not Ctrl+S time.
        """
        if self.save_path is None:
            self.notify(
                "No save path configured", severity="warning", title="Save"
            )
            return

        from pydantic_studio import save_yaml
        from pydantic_studio.exceptions import ValidationFailedError

        try:
            save_yaml(self.tree, self.save_path)
        except ValidationFailedError as exc:
            from pydantic_studio.renderers.textual_.screens import ErrorsScreen

            n = len(exc.errors)
            self.notify(
                f"{n} validation error{'s' if n != 1 else ''} — fix before saving",
                severity="error",
                title="Save failed",
            )
            self.push_screen(ErrorsScreen(errors=exc.errors))
            return
        except Exception as exc:
            self.notify(
                f"{type(exc).__name__}: {exc}",
                severity="error",
                title="Save failed",
            )
            return

        self.notify(
            f"Saved to {self.save_path}",
            severity="information",
            title="Save",
        )


def run_app(tree: FormTree, save_path: str | Path | None = None) -> None:
    """Launch the StudioApp synchronously. Blocks until the user quits."""
    app = StudioApp(tree=tree, save_path=save_path)
    app.run()
