"""Per-kind editor cells for the TUI v2 FieldRow.

Each cell handles one logical group of node kinds (text/numeric leaves,
bool, enum/literal choice, secret). FieldRow dispatches to the right
cell via ``make_cell(node, path)`` from this package.
"""

from __future__ import annotations
