"""SecretCell — masked display + password Input on edit.

Idle always renders ``**********`` (never reveal in display mode).
Editing swaps to a Textual Input with ``password=True`` so the
keystrokes show as bullets while the user types. Empty value shows
as empty (no mask) so the user knows the field is unset.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Input, Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell

if TYPE_CHECKING:
    from textual.app import ComposeResult


_MASK = "**********"


class SecretCell(Cell):
    """Masked editor for SecretNode."""

    DEFAULT_CSS = ""

    @property
    def _underlying_value(self) -> str:
        """Read node.value, unwrapping SecretStr if needed.

        The form tree stores either a plain str/bytes or a Pydantic
        SecretStr/SecretBytes depending on schema annotation. We need
        the plaintext for pre-filling the edit Input.
        """
        v = getattr(self._node, "value", None)
        if v is None:
            return ""
        if hasattr(v, "get_secret_value"):
            inner = v.get_secret_value()
            if isinstance(inner, bytes):
                return inner.decode("utf-8", errors="replace")
            return str(inner)
        if isinstance(v, bytes):
            return v.decode("utf-8", errors="replace")
        return str(v)

    @property
    def value_text(self) -> str:
        # Never show the actual value at idle.
        return _MASK if self._underlying_value else ""

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value")

    def enter_edit(self) -> None:
        if self.editing:
            return
        super().enter_edit()
        try:
            static = self.query_one(Static)
        except Exception:
            static = None
        new_input = Input(
            value=self._underlying_value,
            password=True,
            classes="field-row--value",
        )
        self.mount(new_input)
        if static is not None:
            static.remove()
        new_input.focus()

    def cancel_edit(self) -> None:
        if not self.editing:
            return
        self._exit_to_idle()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.commit(event.value)
        self._exit_to_idle()

    def _exit_to_idle(self) -> None:
        try:
            input_widget = self.query_one(Input)
        except Exception:
            input_widget = None
        new_static = Static(self.value_text, classes="field-row--value")
        self.mount(new_static)
        if input_widget is not None:
            input_widget.remove()
        super().exit_edit()
