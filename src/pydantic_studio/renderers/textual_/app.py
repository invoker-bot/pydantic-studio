"""StudioApp — the Textual App entry point for pydantic-studio."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App
from textual.binding import Binding

from pydantic_studio.outcome import EditOutcome
from pydantic_studio.session import EditSession

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop
    from collections.abc import Iterable
    from pathlib import Path
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
        tree: FormTree | None = None,
        save_path: str | Path | None = None,
        readonly_paths: Iterable[str] = (),
        session: EditSession | None = None,
    ) -> None:
        super().__init__()
        if session is None:
            if tree is None:
                raise TypeError("StudioApp requires either tree or session")
            session = EditSession(
                tree=tree,
                save_path=save_path,
                readonly_paths=readonly_paths,
            )
        self.session = session
        self._outcome = EditOutcome(status="cancelled")

    @property
    def outcome(self) -> EditOutcome:
        """How the session ended. Meaningful after :meth:`run` returns."""
        return self.session.outcome or self._outcome

    @property
    def dirty(self) -> bool:
        """True iff the tree's data differs from the session start."""
        return self.session.dirty

    @property
    def readonly_paths(self) -> frozenset[str]:
        return self.session.readonly_paths

    @property
    def save_path(self) -> Path | None:
        return self.session.save_path

    @property
    def tree(self) -> FormTree:  # type: ignore[override]
        """The :class:`FormTree` being edited.

        Overrides Textual's read-only ``App.tree`` (a Rich DOM
        renderable) with our editable form tree.
        """
        return self.session.tree

    @tree.setter
    def tree(self, value: FormTree) -> None:
        self.session.tree = value

    def on_mount(self) -> None:
        from pydantic_studio.renderers.textual_.studio_screen import StudioScreen

        self.push_screen(StudioScreen(self.session, dismiss_on_finish=False))

    def run(
        self,
        *,
        headless: bool = False,
        inline: bool = False,
        inline_no_clear: bool = False,
        mouse: bool = True,
        size: tuple[int, int] | None = None,
        auto_pilot: AutopilotCallbackType | None = None,
        loop: AbstractEventLoop | None = None,
    ):
        """Run with mouse reporting ON: clicking a row focuses it, clicking
        toggles/choices changes them, the ActionBar buttons work, the wheel
        scrolls. Pass ``mouse=False`` for copy-heavy terminal workflows
        (most terminals also bypass reporting via Shift+drag)."""
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

    def _studio_screen(self):
        from pydantic_studio.renderers.textual_.studio_screen import StudioScreen

        for screen in reversed(self.screen_stack):
            if isinstance(screen, StudioScreen):
                return screen
        return None

    def on_studio_session_ended(self, event) -> None:
        self._outcome = event.outcome
        self.exit()

    async def action_quit(self) -> None:  # type: ignore[override]
        """Ctrl+C — cancel the session.

        A clean tree exits immediately. A dirty tree gets the
        ConfirmExitScreen (Save & exit / Discard / Keep editing); a
        second Ctrl+C while that screen is up force-discards, so the
        muscle-memory double Ctrl+C still quits.
        """
        screen = self._studio_screen()
        if screen is not None:
            await screen.action_quit()

    def action_cancel_session(self) -> None:
        """Cancel requested from a screen (Esc on the root ConfigScreen)."""
        screen = self._studio_screen()
        if screen is not None:
            screen.action_cancel_session()

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
        screen = self._studio_screen()
        if screen is not None:
            screen.action_save()

    def _submit(self) -> bool:
        """Shared submit path for Ctrl+S and ConfirmExitScreen's Save.

        Returns True when the session ended (valid tree); False when
        validation failed and the user was sent back to fix things.
        """
        screen = self._studio_screen()
        return False if screen is None else screen._submit()


def run_app(
    tree: FormTree,
    save_path: str | Path | None = None,
    readonly_paths: Iterable[str] = (),
) -> EditOutcome:
    """Launch the StudioApp synchronously; blocks until the session ends.

    Returns the session's :class:`EditOutcome` — callers persist the
    tree only when ``outcome.submitted`` is true.
    """
    session = EditSession(tree=tree, save_path=save_path, readonly_paths=readonly_paths)
    app = StudioApp(session=session)
    app.run()
    return session.outcome or app.outcome
