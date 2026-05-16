"""AnyCell -- JSON-aware inline editor for ``typing.Any`` nodes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from textual.widgets import Input, Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell

if TYPE_CHECKING:
    from textual.app import ComposeResult


class AnyCell(Cell):
    """Edit arbitrary values as JSON when possible, plain text otherwise."""

    DEFAULT_CSS = ""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_error: str | None = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def value_text(self) -> str:
        value = getattr(self._node, "value", None)
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value", markup=False)

    def enter_edit(self) -> None:
        if self.editing:
            return
        super().enter_edit()
        self._last_error = None
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
        if not self.editing:
            return
        self._exit_to_idle()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        parsed = self._parse_any(event.value)
        result = self.commit(parsed)
        if not result.ok:
            self._last_error = "; ".join(result.errors) or "invalid"
            self._exit_to_idle()
            return
        self._last_error = None
        self._exit_to_idle()

    def _parse_any(self, raw: str) -> Any:
        stripped = raw.strip()
        if stripped == "":
            return None
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return raw

    def _exit_to_idle(self) -> None:
        try:
            input_widget = self.query_one(Input)
        except Exception:
            input_widget = None
        new_static = Static(self.value_text, classes="field-row--value", markup=False)
        self.mount(new_static)
        if input_widget is not None:
            input_widget.remove()
        super().exit_edit()
