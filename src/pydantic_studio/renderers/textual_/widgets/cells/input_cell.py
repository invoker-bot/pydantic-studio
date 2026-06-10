"""InputCell — persistent-Input base for text-backed leaf cells.

Form mode: the focused field IS the editable field. The cell hosts one
Textual Input for its whole life — no Static↔Input swap, no modal
enter-edit/exit-edit lifecycle. The surrounding FieldListView drives
the form flow:

- ``commit_pending()`` before any cursor move (Tab/arrows/click-away);
  a parse/validation failure blocks the move and surfaces the error
- Enter inside the Input commits and posts :class:`AdvanceRequested`
- ``revert()`` restores the Input to the last committed value (Esc)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from textual.widgets import Input

from pydantic_studio.renderers.textual_.widgets.cells.base import (
    AdvanceRequested,
    Cell,
    CellValueChanged,
)

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from pydantic_studio.tree.validation import ValidationResult


class InputCell(Cell):
    """Base for TextCell / SecretCell / AnyCell in form mode."""

    DEFAULT_CSS = ""
    password: ClassVar[bool] = False

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_error: str | None = None

    # ----- subclass surface -----

    @property
    def display_value(self) -> str:
        """The committed node value rendered as input text."""
        v = getattr(self._node, "value", None)
        return "" if v is None else str(v)

    def parse(self, raw: str) -> tuple[bool, Any]:
        """Parse raw input text into a commit-ready value."""
        return True, raw

    # ----- chrome -----

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def value_text(self) -> str:
        return self.display_value

    def compose(self) -> ComposeResult:
        yield Input(
            value=self.display_value,
            password=self.password,
            classes="field-row--value",
        )

    @property
    def input(self) -> Input | None:
        try:
            return self.query_one(Input)
        except Exception:
            return None

    def focus_value(self) -> None:
        inp = self.input
        if inp is not None:
            inp.focus()

    # ----- form flow -----

    def is_dirty(self) -> bool:
        inp = self.input
        return inp is not None and inp.value != self.display_value

    def commit_pending(self) -> ValidationResult | None:
        """Commit the Input's text if it differs from the node value.

        Returns None when there was nothing to commit, otherwise the
        ValidationResult (failures leave the tree untouched and stash
        ``last_error`` for the row chrome).
        """
        from pydantic_studio.tree.validation import ValidationResult

        inp = self.input
        if inp is None or inp.value == self.display_value:
            return None
        ok, parsed = self.parse(inp.value)
        if not ok:
            self._last_error = f"cannot parse {inp.value!r} as {self._node.kind}"
            self.post_message(CellValueChanged(path=self._path, error=self._last_error))
            return ValidationResult.fail([self._last_error])
        result = self.commit(parsed)
        self._last_error = None if result.ok else ("; ".join(result.errors) or "invalid")
        self.post_message(CellValueChanged(path=self._path, error=self._last_error))
        return result

    def revert(self) -> None:
        """Esc — restore the Input to the last committed value."""
        inp = self.input
        if inp is None:
            return
        inp.value = self.display_value
        self._last_error = None
        self.post_message(CellValueChanged(path=self._path, error=None))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter — commit, then ask the form to advance."""
        event.stop()
        result = self.commit_pending()
        if result is None or result.ok:
            self.post_message(AdvanceRequested(path=self._path))
