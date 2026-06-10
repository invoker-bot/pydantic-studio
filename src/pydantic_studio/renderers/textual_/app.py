"""StudioApp — the Textual App entry point for pydantic-studio."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App
from textual.binding import Binding

from pydantic_studio.outcome import EditOutcome

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop
    from collections.abc import Iterable
    from typing import ClassVar

    from textual.app import AutopilotCallbackType
    from textual.binding import BindingType

    from pydantic_studio.tree.nodes import FormTree


class StudioApp(App):
    """Textual application that hosts the form-tree editor.

    Args:
        tree: the FormTree to edit (typically built via
            ``build_form_tree`` or ``load_yaml``).
        save_path: optional path to write to on submit (Ctrl+S). When
            None the session still submits — persisting is then the
            caller's job, branching on :attr:`outcome`.
        readonly_paths: dotted paths the user may inspect but not edit
            (the caller owns their values — e.g. a config name that the
            CLI overrides on save).

    The session ends in one of two explicit ways (see
    :class:`~pydantic_studio.outcome.EditOutcome`):

    - **submit** (Ctrl+S): validate; on success write ``save_path`` if
      configured and exit with ``submitted``. On failure show the
      errors screen and jump the cursor to the first offending field.
    - **cancel** (Ctrl+C, or Esc on the root screen): exit immediately
      when the tree is untouched; otherwise ask — Save & exit /
      Discard / Keep editing.

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
        readonly_paths: Iterable[str] = (),
    ) -> None:
        super().__init__()
        self._tree = tree
        self.save_path = Path(save_path) if save_path is not None else None
        self.readonly_paths = frozenset(readonly_paths)
        self._outcome = EditOutcome(status="cancelled")
        self._initial_state = copy.deepcopy(tree.to_python())

    @property
    def outcome(self) -> EditOutcome:
        """How the session ended. Meaningful after :meth:`run` returns."""
        return self._outcome

    @property
    def dirty(self) -> bool:
        """True iff the tree's data differs from the session start."""
        return self._tree.to_python() != self._initial_state

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

    def _finish(self, status: str) -> None:
        """Record the session outcome and tear the app down."""
        self._outcome = EditOutcome(status=status)  # type: ignore[arg-type]
        self.exit()

    async def action_quit(self) -> None:  # type: ignore[override]
        """Ctrl+C — cancel the session.

        A clean tree exits immediately. A dirty tree gets the
        ConfirmExitScreen (Save & exit / Discard / Keep editing); a
        second Ctrl+C while that screen is up force-discards, so the
        muscle-memory double Ctrl+C still quits.
        """
        from pydantic_studio.renderers.textual_.screens import ConfirmExitScreen

        if isinstance(self.screen, ConfirmExitScreen):
            self._finish("cancelled")
            return
        if not self.dirty:
            self._finish("cancelled")
            return
        self.push_screen(ConfirmExitScreen())

    def action_cancel_session(self) -> None:
        """Cancel requested from a screen (Esc on the root ConfigScreen)."""
        self.call_next(self.action_quit)

    def action_save(self) -> None:
        """Ctrl+S — submit the session.

        Validates via ``to_instance``; on success writes ``save_path``
        (when configured) and exits with a ``submitted`` outcome — the
        caller persists trees edited without a ``save_path``. On
        validation failure the ErrorsScreen lists every problem and,
        once dismissed, the cursor jumps to the first offending field.

        ``save_yaml`` stays strict (core invariant §5): a partial tree
        never reaches the disk.
        """
        self._submit()

    def _submit(self) -> bool:
        """Shared submit path for Ctrl+S and ConfirmExitScreen's Save.

        Returns True when the session ended (valid tree); False when
        validation failed and the user was sent back to fix things.
        """
        from pydantic_studio import save_yaml
        from pydantic_studio.exceptions import ValidationFailedError
        from pydantic_studio.renderers.textual_.screens import (
            ConfirmExitScreen,
            ErrorsScreen,
        )

        try:
            if self.save_path is not None:
                save_yaml(self.tree, self.save_path)
            else:
                self.tree.to_instance()
        except ValidationFailedError as exc:
            if isinstance(self.screen, ConfirmExitScreen):
                self.pop_screen()
            n = len(exc.errors)
            self.notify(
                f"{n} validation error{'s' if n != 1 else ''} — fix before saving",
                severity="error",
                title="Save failed",
            )
            self.push_screen(ErrorsScreen(errors=exc.errors, paths=exc.paths))
            return False
        except Exception as exc:
            self.notify(
                f"{type(exc).__name__}: {exc}",
                severity="error",
                title="Save failed",
            )
            return False

        if self.save_path is not None:
            self.notify(
                f"Saved to {self.save_path}",
                severity="information",
                title="Save",
            )
        self._finish("submitted")
        return True


def run_app(
    tree: FormTree,
    save_path: str | Path | None = None,
    readonly_paths: Iterable[str] = (),
) -> EditOutcome:
    """Launch the StudioApp synchronously; blocks until the session ends.

    Returns the session's :class:`EditOutcome` — callers persist the
    tree only when ``outcome.submitted`` is true.
    """
    app = StudioApp(tree=tree, save_path=save_path, readonly_paths=readonly_paths)
    app.run()
    return app.outcome
