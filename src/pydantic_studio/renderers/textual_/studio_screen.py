"""Embeddable Textual screen for pydantic-studio."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding, BindingType
from textual.message import Message

from pydantic_studio.renderers.textual_.screens import (
    ConfigScreen,
    ConfirmExitScreen,
    ErrorsScreen,
)

if TYPE_CHECKING:
    from pydantic_studio.outcome import EditOutcome
    from pydantic_studio.session import EditSession, SubmitResult


def _submit_failure_message(result: SubmitResult) -> str:
    if result.errors and all(error.startswith("could not save") for error in result.errors):
        n = len(result.errors)
        return f"{n} save error{'s' if n != 1 else ''} — fix before saving"
    n = len(result.errors)
    return f"{n} validation error{'s' if n != 1 else ''} — fix before saving"


class StudioSessionEnded(Message):
    """Posted when an embedded StudioScreen reaches submit or cancel."""

    def __init__(self, outcome: EditOutcome) -> None:
        super().__init__()
        self.outcome = outcome


class StudioScreen(ConfigScreen):
    """Embeddable editor screen backed by an EditSession."""

    BINDINGS: ClassVar[list[BindingType]] = [
        *ConfigScreen.BINDINGS,
        Binding("ctrl+s", "save", "save", priority=True),
        Binding("ctrl+c", "quit", "quit", priority=True),
    ]

    def __init__(self, session: EditSession, *, dismiss_on_finish: bool = True) -> None:
        self.session = session
        self._dismiss_on_finish = dismiss_on_finish
        short_name = (
            session.tree.schema_name.split(":")[-1]
            if ":" in session.tree.schema_name
            else session.tree.schema_name
        )
        super().__init__(
            group=session.tree.root,
            form_tree=session.tree,
            breadcrumb_parts=[short_name],
        )

    @property
    def readonly_paths(self) -> frozenset[str]:
        return self.session.readonly_paths

    def _finish(self, outcome: EditOutcome) -> None:
        self.post_message(StudioSessionEnded(outcome))
        if self._dismiss_on_finish:
            self.dismiss(outcome)

    def _cancel_from_confirm(self) -> None:
        outcome = self.session.cancel()
        self._finish(outcome)

    async def action_quit(self) -> None:  # type: ignore[override]
        if isinstance(self.app.screen, ConfirmExitScreen):
            outcome = self.session.cancel()
            self._finish(outcome)
            return
        if not self.session.dirty:
            outcome = self.session.cancel()
            self._finish(outcome)
            return
        self.app.push_screen(ConfirmExitScreen())

    def action_cancel_session(self) -> None:
        self.call_next(self.action_quit)

    def action_save(self) -> None:
        self._submit()

    def _submit(self) -> bool:
        from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView

        try:
            view = self.query_one(FieldListView)
        except Exception:
            view = None
        if view is not None and not view._commit_gate():
            self.app.notify(
                "fix the highlighted field first",
                severity="error",
                title="Save",
            )
            return False

        result = self.session.submit()
        if not result.ok:
            if isinstance(self.app.screen, ConfirmExitScreen):
                self.app.pop_screen()
            self.app.notify(
                _submit_failure_message(result),
                severity="error",
                title="Save failed",
            )
            self.app.push_screen(
                ErrorsScreen(errors=list(result.errors), paths=list(result.paths))
            )
            return False

        if self.session.save_path is not None:
            self.app.notify(
                f"Saved to {self.session.save_path}",
                severity="information",
                title="Save",
            )
        assert result.outcome is not None
        self._finish(result.outcome)
        return True
