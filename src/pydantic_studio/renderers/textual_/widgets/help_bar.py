"""HelpBar — one-line guidance for the focused field.

Sits between the FieldListView and the FooterHints. Shows the focused
field's name, type, constraints, and — most importantly — its
``FieldInfo.description``, which config authors already write and which
the TUI previously never surfaced. When required fields are still
missing, a counter nudges the user toward `n` (jump to next required).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.widgets import Static

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode

_CONSTRAINT_ATTRS = (
    "ge",
    "le",
    "gt",
    "lt",
    "multiple_of",
    "max_digits",
    "decimal_places",
    "min_length",
    "max_length",
    "pattern",
)

_CONTAINER_HINTS = {
    "group": "Enter to open",
    "sequence": "Enter to open",
    "mapping": "Enter to open",
    "union": "Tab to switch variant, Enter to open",
    "root_variant": "Left/Right to switch root model",
}


def describe_node(node: AnyNode, *, readonly: bool = False) -> str:
    """Render the per-field half of the bar: ``name (kind, facts) — description``."""
    facts: list[str] = [str(getattr(node, "kind", "?"))]
    if readonly:
        facts.append("read-only")
    if getattr(node, "required", False) and getattr(node, "value", object()) is None:
        facts.append("required")
    for attr in _CONSTRAINT_ATTRS:
        value = getattr(node, attr, None)
        if value is not None:
            facts.append(f"{attr}={value}")
    if getattr(node, "allow_inf_nan", True) is False:
        facts.append("finite")
    hint = _CONTAINER_HINTS.get(getattr(node, "kind", ""))
    if hint is not None:
        facts.append(hint)
    text = f"{node.name} ({', '.join(facts)})"
    description = getattr(node, "description", None)
    if description:
        text += f" — {description}"
    return text


class HelpBar(Static):
    """Single-line Static; ConfigScreen drives it via :meth:`show_node`."""

    DEFAULT_CSS = ""  # styled via theme.tcss

    def __init__(self) -> None:
        super().__init__("")
        self._text = ""

    @property
    def text(self) -> str:
        """Current bar content as plain text — the testable contract.
        Rendering adds color (amber counter, accent field name)."""
        return self._text

    def show_node(
        self,
        node: Any,
        *,
        missing_count: int = 0,
        readonly: bool = False,
    ) -> None:
        plain: list[str] = []
        rich: list[str] = []
        if missing_count > 0:
            noun = "field" if missing_count == 1 else "fields"
            counter = f"⚠ {missing_count} required {noun} missing (Ctrl+N jumps)"
            plain.append(counter)
            rich.append(f"[#e0af68]{counter}[/]")
        if node is not None:
            described = describe_node(node, readonly=readonly)
            plain.append(described)
            name = str(node.name)
            if described.startswith(name):
                rich.append(
                    f"[bold #d18b40]{name}[/][dim]{described[len(name):]}[/]"
                )
            else:
                rich.append(f"[dim]{described}[/]")
        self._text = "   ".join(plain)
        self.update("   ".join(rich))
