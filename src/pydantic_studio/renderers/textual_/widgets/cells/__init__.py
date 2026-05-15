"""Per-kind editor cells for the TUI v2 FieldRow.

Each cell handles one logical group of node kinds (text/numeric leaves,
bool, enum/literal choice, secret). FieldRow dispatches to the right
cell via ``make_cell(node, path, form_tree)`` from this package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_studio.renderers.textual_.widgets.cells.base import (
    Cell,
    EditModeEntered,
    EditModeExited,
)
from pydantic_studio.renderers.textual_.widgets.cells.bool_cell import BoolCell
from pydantic_studio.renderers.textual_.widgets.cells.choice_cell import ChoiceCell
from pydantic_studio.renderers.textual_.widgets.cells.secret_cell import SecretCell
from pydantic_studio.renderers.textual_.widgets.cells.text_cell import TextCell

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree


_TEXT_KINDS = {
    "string", "int", "float", "decimal",
    "datetime", "date", "time", "timedelta",
    "ip_address", "ip_network", "url", "email",
    "path", "uuid", "pattern", "bytes",
}


def make_cell(node: AnyNode, path: str, form_tree: FormTree) -> Cell:
    """Dispatch a node to its concrete Cell subclass.

    Containers (group/sequence/mapping/union) are not handled here yet —
    they get a ContainerCell stub in M3. For M2, they fall through to a
    TextCell rendering ``str(node.value)`` which approximates the legacy
    PlaceholderCell behavior.
    """
    kind = node.kind
    if kind in _TEXT_KINDS:
        return TextCell(node=node, path=path, form_tree=form_tree)
    if kind == "bool":
        return BoolCell(node=node, path=path, form_tree=form_tree)
    if kind in ("enum", "literal"):
        return ChoiceCell(node=node, path=path, form_tree=form_tree)
    if kind == "secret":
        return SecretCell(node=node, path=path, form_tree=form_tree)
    # group / sequence / mapping / union / any: M3+ adds ContainerCell.
    return TextCell(node=node, path=path, form_tree=form_tree)


__all__ = [
    "BoolCell",
    "Cell",
    "ChoiceCell",
    "EditModeEntered",
    "EditModeExited",
    "SecretCell",
    "TextCell",
    "make_cell",
]
