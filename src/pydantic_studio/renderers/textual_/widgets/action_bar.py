"""ActionBar — visible, clickable Save / Cancel buttons.

Humans look for buttons; key chords are the accelerator, not the only
affordance. The bar sits between the HelpBar and the FooterHints and
mirrors Ctrl+S / Ctrl+C exactly (same submit / cancel session flows).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal
from textual.widgets import Button

if TYPE_CHECKING:
    from textual.app import ComposeResult


class ActionBar(Horizontal):
    """Two-button bar wired to the current screen's session actions."""

    DEFAULT_CSS = ""

    def compose(self) -> ComposeResult:
        yield Button("Save (Ctrl+S)", id="action-save", variant="primary")
        yield Button("Cancel (Ctrl+C)", id="action-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        screen = self.screen
        if event.button.id == "action-save":
            save = getattr(screen, "action_save", None)
            if save is not None:
                save()
            return
        if event.button.id == "action-cancel":
            cancel = getattr(screen, "action_cancel_session", None)
            if cancel is not None:
                cancel()
                return
            app_cancel = getattr(self.app, "action_cancel_session", None)
            if app_cancel is not None:
                app_cancel()
