"""Cell base class + edit-lifecycle messages.

Subclasses override ``compose()`` to render their idle UI and call
``enter_edit()`` / ``exit_edit()`` to drive the lifecycle. The base
posts ``EditModeEntered`` / ``EditModeExited`` messages so the
surrounding screen (ConfigScreen) can flip the footer mode without
needing a parent reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from textual.message import Message
from textual.widget import Widget

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree
    from pydantic_studio.tree.validation import ValidationResult


@dataclass
class EditModeEntered(Message):
    """Posted by a Cell when it enters edit mode."""

    path: str


@dataclass
class EditModeExited(Message):
    """Posted by a Cell when it exits edit mode (commit OR cancel)."""

    path: str


class Cell(Widget):
    """Base class for per-kind editor cells.

    Subclasses are responsible for:
    - overriding ``compose()`` to render their idle UI
    - calling ``enter_edit()`` / ``exit_edit()`` at the right moments
    - implementing ``value_text`` property for tests + chrome proxies

    The base provides:
    - ``commit(value)`` -- routes a typed value through
      ``form_tree.set_value(path, value)`` and returns the result
    - ``editing`` -- bool flag that's True between enter_edit/exit_edit
    """

    DEFAULT_CSS = ""

    def __init__(self, node: AnyNode, path: str, form_tree: FormTree) -> None:
        super().__init__()
        self._node = node
        self._path = path
        self._form_tree = form_tree
        self._editing = False

    @property
    def node(self) -> AnyNode:
        return self._node

    @property
    def path(self) -> str:
        return self._path

    @property
    def editing(self) -> bool:
        return self._editing

    @property
    def value_text(self) -> str:
        """Subclasses override for kind-specific display formatting.

        Default reads ``node.value`` with str() and empty for None.
        """
        v = getattr(self._node, "value", None)
        return "" if v is None else str(v)

    def enter_edit(self) -> None:
        if self._editing:
            return
        self._editing = True
        self.post_message(EditModeEntered(path=self._path))

    def exit_edit(self) -> None:
        if not self._editing:
            return
        self._editing = False
        self.post_message(EditModeExited(path=self._path))

    def cancel_edit(self) -> None:
        """Esc handler — leave edit mode without mutating.

        Cells with a real edit UI (TextCell, SecretCell, AnyCell)
        override this to also tear down their Input widget. The base
        implementation only clears the flag, so Esc is *always* safe
        even if a cell ends up in edit mode without a custom UI.
        """
        self.exit_edit()

    def commit(self, value: Any) -> ValidationResult:
        """Route a typed value through FormTree.set_value and return
        the result. The tree owns validation; the cell just dispatches.
        """
        return self._form_tree.set_value(self._path, value)
