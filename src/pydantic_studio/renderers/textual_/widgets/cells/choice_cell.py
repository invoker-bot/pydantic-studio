"""ChoiceCell -- covers enum + literal node kinds.

Up to 7 choices renders ``< value >`` and cycles in place on Tab /
left / right. More than 7 renders just the value (the FieldRow's
drill marker tells the user to press Enter); Enter pushes ChooserScreen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.widgets import Static

from pydantic_studio.renderers.textual_.widgets.cells.base import Cell
from pydantic_studio.renderers.textual_.widgets.cells.labels import enum_label

if TYPE_CHECKING:
    from textual.app import ComposeResult


_SMALL_THRESHOLD = 7


class ChoiceCell(Cell):
    """Inline cycle (small) or drill-to-screen (large) for enum + literal."""

    DEFAULT_CSS = ""

    @property
    def _choices(self) -> list[tuple[str, Any]]:
        """Return [(label, value)] for the node's choices.

        EnumNode.choices stores ``(member.name, member)`` but for user-
        facing display we prefer the member's ``.value`` (e.g. ``"info"``
        not ``"INFO"``) when it stringifies cleanly. LiteralNode.choices
        is list[Any]. Normalize to (label_str, raw_value).
        """
        node = self._node
        if node.kind == "enum":
            return [(enum_label(member), member) for _, member in node.choices]
        # literal: each choice is the literal value itself.
        return [(str(c), c) for c in node.choices]

    @property
    def large_choice(self) -> bool:
        return len(self._choices) > _SMALL_THRESHOLD

    @property
    def value_text(self) -> str:
        v = getattr(self._node, "value", None)
        label = self._label_for(v)
        if self.large_choice:
            return label
        return f"‹ {label} ›"  # noqa: RUF001

    def _label_for(self, value: Any) -> str:
        if value is None:
            return ""
        for label, raw in self._choices:
            if raw == value:
                return label
        return str(value)

    def compose(self) -> ComposeResult:
        yield Static(self.value_text, classes="field-row--value")

    def cycle_next(self) -> None:
        self._cycle(+1)

    def cycle_prev(self) -> None:
        self._cycle(-1)

    def _cycle(self, delta: int) -> None:
        if self.large_choice:
            return
        choices = self._choices
        if not choices:
            return
        current = getattr(self._node, "value", None)
        idx = 0
        for i, (_, raw) in enumerate(choices):
            if raw == current:
                idx = i
                break
        new_idx = (idx + delta) % len(choices)
        new_value = choices[new_idx][1]
        result = self.commit(new_value)
        if not result.ok:
            return
        try:
            static = self.query_one(Static)
        except Exception:
            return
        static.update(self.value_text)

    def open_chooser(self) -> None:
        """Push the ChooserScreen for large-choice fields."""
        from pydantic_studio.renderers.textual_.screens import ChooserScreen

        if not self.large_choice:
            return
        self.app.push_screen(
            ChooserScreen(node=self._node, path=self._path, form_tree=self._form_tree)
        )
