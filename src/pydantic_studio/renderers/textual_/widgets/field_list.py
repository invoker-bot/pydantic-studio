"""FieldListView — the scrollable vertical stack of FieldRows that
sits between the Breadcrumb and FooterHints inside a ConfigScreen.

Owns the focused-row cursor and translates up/down key events into
cursor moves. Scroll is delegated to Textual's VerticalScroll
container; we never set scroll_y manually.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll

from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow

if TYPE_CHECKING:
    from typing import ClassVar

    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import AnyNode, FormTree


@dataclass(frozen=True)
class _RowSpec:
    node: Any
    path: str
    label: str | None = None


class FieldListView(VerticalScroll):
    """Scrollable vertical stack of FieldRows for the active container."""

    DEFAULT_CSS = ""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor_up", "up", show=False),
        Binding("down", "cursor_down", "down", show=False),
        Binding("enter", "activate_focused", "edit", show=False),
        Binding("space", "toggle_focused", "toggle", show=False),
        Binding("tab", "cycle_next_focused", "next", show=False, priority=True),
        Binding(
            "shift+tab", "cycle_prev_focused", "prev", show=False, priority=True
        ),
        Binding("a", "add_item", "add", show=False),
        Binding("d", "delete_focused", "delete", show=False),
        Binding("ctrl+up", "move_focused_up", "move up", show=False),
        Binding("ctrl+down", "move_focused_down", "move down", show=False),
        Binding("r", "rename_focused_key", "rename", show=False),
        Binding("escape", "cancel_focused", "cancel", show=False),
    ]

    def __init__(
        self,
        group: AnyNode,
        form_tree: FormTree,
        base_path: str = "",
    ) -> None:
        super().__init__()
        self._group = group
        self._form_tree = form_tree
        self._base_path = base_path
        self._cursor: int = 0

    @property
    def cursor(self) -> int:
        return self._cursor

    def compose(self) -> ComposeResult:
        for idx, spec in enumerate(self._row_specs()):
            yield FieldRow(
                node=spec.node,
                path=spec.path,
                form_tree=self._form_tree,
                focused=(idx == self._cursor),
                label_override=spec.label,
            )

    def _row_specs(self) -> list[_RowSpec]:
        """Return child rows for the container this view is scoped to."""
        node = self._group
        if node.kind == "group":
            return [
                _RowSpec(
                    child,
                    self._join_path(self._base_path, child.name),
                )
                for child in node.fields
            ]
        if node.kind == "sequence":
            return [
                _RowSpec(child, self._join_path(self._base_path, idx))
                for idx, child in enumerate(node.items)
            ]
        if node.kind == "mapping":
            return [
                _RowSpec(
                    value_node,
                    self._join_path(self._base_path, idx),
                    self._label_for_key(key_node, idx),
                )
                for idx, (key_node, value_node) in enumerate(node.entries)
            ]
        if node.kind == "union" and node.selected is not None:
            return [
                _RowSpec(
                    node.selected,
                    self._base_path,
                    self._selected_union_label(node),
                )
            ]
        return []

    def _join_path(self, base: str, segment: str | int) -> str:
        segment_text = str(segment)
        return f"{base}.{segment_text}" if base else segment_text

    def _label_for_key(self, key_node: Any, index: int) -> str:
        value = key_node.to_python()
        if value is None:
            return f"entry {index}"
        return str(value)

    def _selected_union_label(self, node: Any) -> str:
        idx = getattr(node, "selected_index", None)
        names = getattr(node, "variant_type_names", [])
        if idx is None or not (0 <= idx < len(names)):
            return "selected"
        return names[idx].rsplit(".", 1)[-1]

    def action_cursor_up(self) -> None:
        if self._cursor <= 0:
            return
        self._move_cursor(self._cursor - 1)

    def action_cursor_down(self) -> None:
        if self._cursor >= len(self._row_specs()) - 1:
            return
        self._move_cursor(self._cursor + 1)

    def _move_cursor(self, new_idx: int) -> None:
        rows = list(self.query(FieldRow))
        if not rows:
            return
        rows[self._cursor].set_focused(False)
        self._cursor = new_idx
        rows[new_idx].set_focused(True)
        # Let VerticalScroll bring the newly focused row into view.
        rows[new_idx].scroll_visible()

    def _refresh_rows(self) -> None:
        specs = self._row_specs()
        if specs:
            self._cursor = min(self._cursor, len(specs) - 1)
        else:
            self._cursor = 0
        self.refresh(recompose=True)

    def _focused_cell(self):
        """Return the Cell mounted inside the cursor-focused row, or None."""
        from pydantic_studio.renderers.textual_.widgets.cells import Cell

        rows = list(self.query(FieldRow))
        if not (0 <= self._cursor < len(rows)):
            return None
        try:
            return rows[self._cursor].query_one(Cell)
        except Exception:
            return None

    def _focused_row(self) -> FieldRow | None:
        """Return the cursor-focused FieldRow, or None."""
        rows = list(self.query(FieldRow))
        if not (0 <= self._cursor < len(rows)):
            return None
        return rows[self._cursor]

    def action_activate_focused(self) -> None:
        """Enter on the focused row -> drill-down (container) or edit (leaf).

        Drill-down takes priority over cell editing: Enter on a
        container row pushes a child ConfigScreen scoped to that node.
        """
        from pydantic_studio.renderers.textual_.widgets.cells import (
            BoolCell,
            ChoiceCell,
        )

        row = self._focused_row()
        if row is not None and row.node.kind in {
            "group",
            "sequence",
            "mapping",
            "union",
        }:
            self._push_child_screen(row.node, row.path)
            return

        cell = self._focused_cell()
        if cell is None:
            return
        if isinstance(cell, BoolCell):
            cell.toggle()
            return
        if isinstance(cell, ChoiceCell) and cell.large_choice:
            cell.open_chooser()
            return
        cell.enter_edit()

    def _push_child_screen(self, group, base_path: str) -> None:
        """Push a child ConfigScreen scoped to ``group``.

        Inherits the parent screen's breadcrumb parts and appends the
        group's name. Uses late imports to break the screens <-> widgets
        cycle (screens.py imports FieldListView; FieldListView pushing
        a screen needs ConfigScreen).
        """
        from pydantic_studio.renderers.textual_.screens import ConfigScreen

        parent = self.screen
        parent_parts = list(getattr(parent, "_breadcrumb_parts", []))
        parts = [*parent_parts, group.name]
        self.app.push_screen(
            ConfigScreen(
                group=group,
                form_tree=self._form_tree,
                breadcrumb_parts=parts,
                base_path=base_path,
            )
        )

    def action_toggle_focused(self) -> None:
        """Space on the focused row -> toggle (BoolCell only)."""
        from pydantic_studio.renderers.textual_.widgets.cells import BoolCell

        cell = self._focused_cell()
        if isinstance(cell, BoolCell):
            cell.toggle()

    def action_cycle_next_focused(self) -> None:
        """Tab on the focused row -> cycle binary/small-choice/union cells."""
        from pydantic_studio.renderers.textual_.widgets.cells import (
            BoolCell,
            ChoiceCell,
        )

        row = self._focused_row()
        if row is not None and row.node.kind == "union":
            self._cycle_union(row.node, +1)
            row.refresh(recompose=True)
            return

        cell = self._focused_cell()
        if isinstance(cell, BoolCell):
            cell.toggle()
            return
        if isinstance(cell, ChoiceCell) and not cell.large_choice:
            cell.cycle_next()

    def action_cycle_prev_focused(self) -> None:
        """Shift+Tab on the focused row -> reverse cycle where possible."""
        from pydantic_studio.renderers.textual_.widgets.cells import (
            BoolCell,
            ChoiceCell,
        )

        row = self._focused_row()
        if row is not None and row.node.kind == "union":
            self._cycle_union(row.node, -1)
            row.refresh(recompose=True)
            return

        cell = self._focused_cell()
        if isinstance(cell, BoolCell):
            cell.toggle()
            return
        if isinstance(cell, ChoiceCell) and not cell.large_choice:
            cell.cycle_prev()

    def _cycle_union(self, node: Any, delta: int) -> None:
        names = getattr(node, "variant_type_names", [])
        if not names:
            return
        current = getattr(node, "selected_index", None)
        idx = 0 if current is None else current
        new_idx = (idx + delta) % len(names)
        self._form_tree.select_variant(self._base_path_for_node(node), new_idx)

    def _base_path_for_node(self, node: Any) -> str:
        if self._group is node:
            return self._base_path
        row = self._focused_row()
        return "" if row is None else row.path

    def action_add_item(self) -> None:
        """A on sequence/mapping screens appends a child entry."""
        if self._group.kind == "sequence":
            result = self._form_tree.add_item(self._base_path)
            if result.ok:
                self._refresh_rows()
            return
        if self._group.kind == "mapping":
            self.action_add_entry()

    def action_add_entry(self) -> None:
        """Append a generated-key mapping entry."""
        if self._group.kind != "mapping":
            return
        result = self._form_tree.add_entry(
            self._base_path,
            key=self._next_mapping_key(),
        )
        if result.ok:
            self._refresh_rows()

    def _next_mapping_key(self) -> Any:
        existing = {key.to_python() for key, _ in self._group.entries}
        key_type = getattr(self._group, "key_type_name", "")
        if key_type == "builtins.int":
            index = 0
            while index in existing:
                index += 1
            return index
        if key_type == "builtins.float":
            index = 0
            while float(index) in existing:
                index += 1
            return float(index)
        if key_type == "builtins.bool":
            for candidate in (False, True):
                if candidate not in existing:
                    return candidate
            return False

        existing_text = {str(value) for value in existing}
        index = 0
        while f"key{index}" in existing_text:
            index += 1
        return f"key{index}"

    def action_delete_focused(self) -> None:
        """D removes the focused sequence item or mapping entry."""
        if self._group.kind == "sequence":
            result = self._form_tree.remove_item(self._base_path, self._cursor)
            if result.ok:
                self._refresh_rows()
            return
        if self._group.kind == "mapping":
            result = self._form_tree.remove_entry(self._base_path, self._cursor)
            if result.ok:
                self._refresh_rows()

    def action_move_focused_up(self) -> None:
        """Move the focused sequence item one slot up."""
        if self._group.kind != "sequence" or self._cursor <= 0:
            return
        result = self._form_tree.move_item(
            self._base_path,
            self._cursor,
            self._cursor - 1,
        )
        if result.ok:
            self._cursor -= 1
            self._refresh_rows()

    def action_move_focused_down(self) -> None:
        """Move the focused sequence item one slot down."""
        if self._group.kind != "sequence":
            return
        if self._cursor >= len(self._group.items) - 1:
            return
        result = self._form_tree.move_item(
            self._base_path,
            self._cursor,
            self._cursor + 1,
        )
        if result.ok:
            self._cursor += 1
            self._refresh_rows()

    def action_rename_focused_key(self, new_key: str | None = None) -> None:
        """Rename the focused mapping key.

        Textual key bindings call this without ``new_key``; tests and
        future prompt screens can pass a concrete value directly.
        """
        if self._group.kind != "mapping":
            return
        if new_key is None:
            if not (0 <= self._cursor < len(self._group.entries)):
                return
            key_node, _ = self._group.entries[self._cursor]
            initial = "" if key_node.to_python() is None else str(key_node.to_python())
            from pydantic_studio.renderers.textual_.screens import RenameKeyScreen

            self.app.push_screen(
                RenameKeyScreen(
                    form_tree=self._form_tree,
                    mapping_path=self._base_path,
                    index=self._cursor,
                    initial=initial,
                    field_list=self,
                )
            )
            return
        self.rename_key_at(self._cursor, new_key)

    def rename_key_at(self, index: int, raw_key: str):
        """Parse and rename a mapping key at ``index``."""
        from pydantic_studio.renderers.textual_.widgets.cells.parse import (
            parse_for_kind,
        )
        from pydantic_studio.tree.validation import ValidationResult

        if self._group.kind != "mapping":
            return ValidationResult.fail(["not a mapping"])
        if not (0 <= index < len(self._group.entries)):
            return ValidationResult.fail([f"index {index} out of range"])

        key_node, _ = self._group.entries[index]
        if key_node.kind == "bool":
            parsed_bool = self._parse_bool(raw_key)
            if parsed_bool is None:
                return ValidationResult.fail(
                    [f"cannot parse {raw_key!r} as bool"]
                )
            parsed_key: Any = parsed_bool
        elif key_node.kind in {"enum", "literal"}:
            ok, parsed_key = self._parse_choice_key(key_node, raw_key)
            if not ok:
                return ValidationResult.fail(
                    [f"cannot parse {raw_key!r} as {key_node.kind}"]
                )
        else:
            ok, parsed_key = parse_for_kind(key_node.kind, raw_key)
            if not ok:
                return ValidationResult.fail(
                    [f"cannot parse {raw_key!r} as {key_node.kind}"]
                )

        result = self._form_tree.rename_key(self._base_path, index, parsed_key)
        if result.ok:
            self._refresh_rows()
        return result

    def _parse_bool(self, raw: str) -> bool | None:
        normalized = raw.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        return None

    def _parse_choice_key(self, key_node: Any, raw: str) -> tuple[bool, Any]:
        if key_node.kind == "enum":
            from pydantic_studio.renderers.textual_.widgets.cells.labels import (
                enum_label,
            )

            for name, member in key_node.choices:
                if raw in {name, enum_label(member), str(member)}:
                    return True, member
            return False, None
        for choice in key_node.choices:
            if raw == str(choice):
                return True, choice
        return False, None

    def action_cancel_focused(self) -> None:
        """Esc on the focused row.

        - If a cell is in edit mode → cancel the edit (in-place).
        - Else if the active screen is a drilled-in child (more than
          one ConfigScreen on the stack) → pop one level.
        - Else (root screen, no edit) → no-op.
        """
        from pydantic_studio.renderers.textual_.screens import ConfigScreen

        cell = self._focused_cell()
        if cell is not None and cell.editing:
            cell.cancel_edit()
            return
        config_screens = [
            s for s in self.app.screen_stack if isinstance(s, ConfigScreen)
        ]
        if len(config_screens) > 1:
            self.app.pop_screen()
