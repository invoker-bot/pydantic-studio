"""TextCell — covers 16 leaf node kinds via parse_for_kind.

Idle: renders ``str(node.value)`` (with hex encoding for bytes).
Editing: replaces the Static with a Textual Input pre-filled with the
current value. Enter commits via parse_for_kind -> Cell.commit;
Esc cancels without mutating. Parse failures and validate-first
rejections both stash a message on ``last_error`` for FieldRow to
read after the round-trip.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Input, Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell
from pydantic_studio.renderers.textual_.widgets.cells.parse import parse_for_kind

if TYPE_CHECKING:
    from textual.app import ComposeResult


class TextCell(Cell):
    """Single-line editor for textual leaf kinds."""

    DEFAULT_CSS = ""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_error: str | None = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def value_text(self) -> str:
        v = getattr(self._node, "value", None)
        if v is None:
            return ""
        if self._node.kind == "bytes" and isinstance(v, (bytes, bytearray)):
            return bytes(v).hex()
        return str(v)

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value", markup=False)

    def enter_edit(self) -> None:
        if self.editing:
            return
        super().enter_edit()
        self._last_error = None
        # Swap the Static for an Input. Order: mount the Input, remove
        # the Static, focus the Input.
        try:
            static = self.query_one(Static)
        except Exception:
            static = None
        new_input = Input(value=self.value_text, classes="field-row--value")
        self.mount(new_input)
        if static is not None:
            static.remove()
        new_input.focus()

    def cancel_edit(self) -> None:
        """Esc handler — exit edit without mutating."""
        if not self.editing:
            return
        self._exit_to_idle()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter on the Input widget."""
        raw = event.value
        ok, parsed = parse_for_kind(self._node.kind, raw)
        if not ok:
            self._last_error = f"cannot parse {raw!r} as {self._node.kind}"
            self._exit_to_idle()
            return
        result = self.commit(parsed)
        if not result.ok:
            self._last_error = "; ".join(result.errors) or "invalid"
            self._exit_to_idle()
            return
        self._last_error = None
        self._exit_to_idle()

    def _exit_to_idle(self) -> None:
        """Tear down the Input and re-mount the Static (idle view)."""
        try:
            input_widget = self.query_one(Input)
        except Exception:
            input_widget = None
        new_static = Static(self.value_text, classes="field-row--value", markup=False)
        self.mount(new_static)
        if input_widget is not None:
            input_widget.remove()
        super().exit_edit()
