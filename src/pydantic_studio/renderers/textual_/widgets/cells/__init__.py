"""Per-kind editor cells for the TUI v2 FieldRow.

Each cell handles one logical group of node kinds (text/numeric leaves,
bool, enum/literal choice, secret). FieldRow dispatches to the right
cell via ``make_cell(node, path, form_tree)`` from this package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_studio.renderers.textual_.widgets.cells.any_cell import AnyCell
from pydantic_studio.renderers.textual_.widgets.cells.base import (
    AdvanceRequested,
    Cell,
    CellValueChanged,
    EditModeEntered,
    EditModeExited,
)
from pydantic_studio.renderers.textual_.widgets.cells.bool_cell import BoolCell
from pydantic_studio.renderers.textual_.widgets.cells.choice_cell import ChoiceCell
from pydantic_studio.renderers.textual_.widgets.cells.container_cell import ContainerCell
from pydantic_studio.renderers.textual_.widgets.cells.input_cell import InputCell
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

    Containers render a non-editing summary cell and FieldListView owns
    their drill-down and structural mutations.
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
    if kind == "any":
        return AnyCell(node=node, path=path, form_tree=form_tree)
    if kind in ("group", "sequence", "mapping", "union"):
        return ContainerCell(node=node, path=path, form_tree=form_tree)
    return TextCell(node=node, path=path, form_tree=form_tree)


__all__ = [
    "AdvanceRequested",
    "AnyCell",
    "BoolCell",
    "Cell",
    "CellValueChanged",
    "ChoiceCell",
    "ContainerCell",
    "EditModeEntered",
    "EditModeExited",
    "InputCell",
    "SecretCell",
    "TextCell",
    "make_cell",
]
