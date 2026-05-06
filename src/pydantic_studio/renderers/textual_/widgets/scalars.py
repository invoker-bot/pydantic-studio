"""Scalar widgets: TextInputEditor + BoolEditor + ChoiceEditor.

TextInputEditor is the most-used class — it covers 17 of 24 node kinds
via parse-on-blur dispatch. BoolEditor and ChoiceEditor are stubs in
this task; full implementations land in T7 (Bool) and T8 (Choice).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.containers import Horizontal
from textual.widgets import Checkbox, Input, Label, Static

from pydantic_studio.renderers.textual_.widgets.editor import NodeEditor

if TYPE_CHECKING:
    from textual.app import ComposeResult


def _parse_for_kind(kind: str, raw: str) -> tuple[bool, Any]:
    """Convert a raw string to the type the node expects.

    Returns ``(ok, value)``. On failure, ``ok=False`` and ``value`` is None.
    """
    raw = raw.strip()
    if raw == "":
        return True, None  # let validate_value decide if None is accepted

    try:
        if kind == "string":
            return True, raw
        if kind == "int":
            return True, int(raw)
        if kind == "float":
            return True, float(raw)
        if kind == "decimal":
            from decimal import Decimal

            return True, Decimal(raw)
        if kind == "datetime":
            from datetime import datetime

            return True, datetime.fromisoformat(raw)
        if kind == "date":
            from datetime import date

            return True, date.fromisoformat(raw)
        if kind == "time":
            from datetime import time

            return True, time.fromisoformat(raw)
        if kind == "timedelta":
            from datetime import timedelta

            from pydantic import TypeAdapter

            return True, TypeAdapter(timedelta).validate_python(raw)
        if kind in ("ip_address", "ip_network"):
            return True, raw  # node stores as string; validate_value parses
        if kind in ("url", "email", "path", "pattern"):
            return True, raw  # node stores as string
        if kind == "uuid":
            from uuid import UUID

            return True, UUID(raw)
        if kind == "secret":
            return True, raw  # node stores plaintext str/bytes
        if kind == "bytes":
            # Accept hex by default (matches BytesNode.field_serializer convention).
            return True, bytes.fromhex(raw)
    except (ValueError, TypeError):
        return False, None
    return False, None


class TextInputEditor(NodeEditor):
    """Single-line input + label + inline error display.

    Dispatches the raw string through ``_parse_for_kind`` to get the
    typed value, then routes to ``self.commit(value)``.

    For ``secret`` kind, the input is rendered with ``password=True`` so
    the typed text appears masked.
    """

    def compose(self) -> ComposeResult:
        # Seed ``node.value`` from ``node.default`` so a failed parse on the
        # first edit doesn't blow away the schema-default value (the displayed
        # value the user sees on initial render).
        if (
            getattr(self.node, "value", None) is None
            and getattr(self.node, "default", None) is not None
        ):
            self.node.value = self.node.default

        with Horizontal():
            yield Label(f"{self.node.name}: ", classes="field-label")
            yield Input(
                value=self._initial_value(),
                password=(self.node.kind == "secret"),
                id=f"input-{self._sanitize_id(self.field_path)}",
            )
        yield Static(
            "",
            id=f"error-{self._sanitize_id(self.field_path)}",
            classes="field-error",
        )

    @staticmethod
    def _sanitize_id(path: str) -> str:
        """Textual widget ids must be valid Python identifiers — strip dots/brackets."""
        return (
            path.replace(".", "_")
            .replace("[", "_")
            .replace("]", "")
            or "root"
        )

    def _initial_value(self) -> str:
        """Stringify the node's current value (falling back to default) for display."""
        v = getattr(self.node, "value", None)
        if v is None:
            v = getattr(self.node, "default", None)
        if v is None:
            return ""
        if self.node.kind == "bytes" and isinstance(v, (bytes, bytearray)):
            return bytes(v).hex()
        return str(v)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Triggered on Enter key in the input."""
        self._commit_from_input(event.value)

    def _commit_from_input(self, raw: str) -> None:
        ok, value = _parse_for_kind(self.node.kind, raw)
        try:
            error_widget = self.query_one(
                f"#error-{self._sanitize_id(self.field_path)}", Static
            )
        except Exception:
            error_widget = None
        if not ok:
            if error_widget is not None:
                error_widget.update(f"cannot parse {raw!r} as {self.node.kind}")
            return
        success, msg = self.commit(value)
        if error_widget is not None:
            error_widget.update("" if success else (msg or "invalid"))


class BoolEditor(NodeEditor):
    """Checkbox bound to a BoolNode."""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(f"{self.node.name}: ", classes="field-label")
            initial = bool(getattr(self.node, "value", False) or False)
            yield Checkbox(
                value=initial,
                id=f"checkbox-{TextInputEditor._sanitize_id(self.field_path)}",
            )
        yield Static(
            "",
            id=f"error-{TextInputEditor._sanitize_id(self.field_path)}",
            classes="field-error",
        )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        ok, msg = self.commit(event.value)
        try:
            error_widget = self.query_one(
                f"#error-{TextInputEditor._sanitize_id(self.field_path)}",
                Static,
            )
        except Exception:
            return
        error_widget.update("" if ok else (msg or "invalid"))


class ChoiceEditor(NodeEditor):
    """Stub — full impl in Task 8."""

    def compose(self) -> ComposeResult:
        yield Static(f"{self.node.name}: <choice stub>")
