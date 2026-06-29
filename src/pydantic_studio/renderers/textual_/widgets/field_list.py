"""FieldListView — the scrollable vertical stack of FieldRows that
sits between the Breadcrumb and FooterHints inside a ConfigScreen.

Form mode: the focused row IS the editable row. Text-backed rows host
persistent Inputs; the view owns the cursor, commits pending values on
every move (Tab / arrows / Enter / click-away), reverts on Esc, and
keeps Textual focus in sync with the cursor. Scroll is delegated to
Textual's VerticalScroll container; we never set scroll_y manually.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow, RowClicked

if TYPE_CHECKING:
    from typing import ClassVar

    from textual import events
    from textual.app import ComposeResult

    from pydantic_studio.tree.nodes import AnyNode, FormTree


class AddRow(Static):
    """Clickable ``[ + add item ]`` row at the end of sequence/mapping
    screens — the discoverable replacement for the old invisible `a`."""

    DEFAULT_CSS = ""

    def __init__(self) -> None:
        super().__init__("[ + add item ]", classes="field-list--add-row", markup=False)

    def on_click(self, event: events.Click) -> None:
        event.stop()
        parent = self.parent
        add = getattr(parent, "action_add_item", None)
        if add is not None:
            add()


@dataclass(frozen=True)
class _RowSpec:
    node: Any
    path: str
    label: str | None = None


@dataclass(frozen=True)
class _RootVariantNode:
    selected_id: str
    options: tuple[Any, ...]
    kind: str = "root_variant"
    name: str = "variant"
    description: str | None = "Select which root model this configuration edits."
    required: bool = False
    error: str | None = None

    def to_python(self) -> str:
        return self.selected_id


@dataclass
class CursorMoved(Message):
    """Posted whenever the focused row changes (incl. the initial one).

    ConfigScreen routes it to the HelpBar so guidance always describes
    the row under the cursor.
    """

    path: str
    node: Any


class FieldListView(VerticalScroll):
    """Scrollable vertical stack of FieldRows for the active container."""

    DEFAULT_CSS = ""

    BINDINGS: ClassVar[list[BindingType]] = [
        # Form flow — commit pending value, then move.
        Binding("up", "cursor_up", "up", show=False),
        Binding("down", "cursor_down", "down", show=False),
        Binding("tab", "cursor_down", "next field", show=False, priority=True),
        Binding("shift+tab", "cursor_up", "previous field", show=False, priority=True),
        Binding("enter", "activate_focused", "open / next", show=False),
        # Value manipulation on non-text rows (text rows consume these
        # keys inside their Input, so there is no collision).
        Binding("space", "toggle_focused", "toggle", show=False),
        Binding("right", "cycle_next_focused", "cycle", show=False),
        Binding("left", "cycle_prev_focused", "cycle back", show=False),
        # Structure (container screens). Letter keys are gone — they
        # would type into the persistent Inputs; chords and the visible
        # AddRow / per-row ✕ replace them.
        Binding("delete", "delete_focused", "delete item", show=False),
        Binding("ctrl+up", "move_focused_up", "move up", show=False),
        Binding("ctrl+down", "move_focused_down", "move down", show=False),
        Binding("f2", "rename_focused_key", "rename key", show=False),
        Binding(
            "ctrl+n", "jump_next_required", "next required", show=False, priority=True
        ),
        Binding("escape", "cancel_focused", "revert / back", show=False),
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
        self._filter: str = ""

    def set_filter(self, value: str) -> None:
        """Substring-narrow the visible rows (group containers only).

        Filtering toggles row *visibility* instead of recomposing the
        list: rows (and their live Inputs) persist, so typing in the
        filter narrows instantly with zero rebuild flicker.
        """
        normalized = value.strip().lower()
        if normalized == self._filter:
            return
        self._filter = normalized
        self._apply_filter_visibility()

    def _filter_match(self, spec: _RowSpec) -> bool:
        if getattr(spec.node, "kind", None) == "root_variant":
            return True
        return not self._filter or self._filter in spec.node.name.lower()

    def _visible_indices(self) -> list[int]:
        specs = self._row_specs()
        return [i for i, spec in enumerate(specs) if self._filter_match(spec)]

    def _apply_filter_visibility(self) -> None:
        rows = list(self.query(FieldRow))
        specs = self._row_specs()
        visible: list[int] = []
        for idx, (row, spec) in enumerate(zip(rows, specs, strict=False)):
            shown = self._filter_match(spec)
            row.display = shown
            if shown:
                visible.append(idx)
        if visible and self._cursor not in visible:
            rows[self._cursor].set_focused(False)
            self._cursor = visible[0]
            rows[self._cursor].set_focused(True)
        self._post_cursor_moved()

    @property
    def cursor(self) -> int:
        return self._cursor

    def compose(self) -> ComposeResult:
        specs = self._row_specs()
        width = self._label_width_for(specs)
        readonly_paths = self._readonly_paths()
        deletable = self._group.kind in {"sequence", "mapping"}
        for idx, spec in enumerate(specs):
            yield FieldRow(
                node=spec.node,
                path=spec.path,
                form_tree=self._form_tree,
                focused=(idx == self._cursor),
                label_override=spec.label,
                readonly=spec.path in readonly_paths,
                label_width=width,
                deletable=deletable,
            )
        if deletable:
            yield AddRow()

    _LABEL_WIDTH_MIN = 10
    _LABEL_WIDTH_MAX = 48
    _READONLY_SUFFIX = "  🔒"

    def _readonly_paths(self) -> frozenset[str]:
        return getattr(self.app, "readonly_paths", frozenset())

    def _label_width_for(self, specs: list[_RowSpec]) -> int:
        """Column width fitting the longest label (clamped) so long field
        names stay distinguishable instead of hard-cutting at a fixed 22."""
        readonly_paths = self._readonly_paths()
        longest = 0
        for spec in specs:
            label = spec.label if spec.label is not None else spec.node.name
            extra = 0  # required state lives in its own badge column now
            if spec.path in readonly_paths:
                extra += len(self._READONLY_SUFFIX) + 1  # 🔒 is double-width
            longest = max(longest, len(label) + extra)
        return max(self._LABEL_WIDTH_MIN, min(longest, self._LABEL_WIDTH_MAX))

    def _row_specs(self) -> list[_RowSpec]:
        """Return child rows for the container this view is scoped to."""
        node = self._group
        if node.kind == "group":
            specs = [
                _RowSpec(
                    child,
                    self._join_path(self._base_path, child.name),
                )
                for child in node.fields
            ]
            if self._base_path == "" and self._form_tree.variant is not None:
                variant = self._form_tree.variant
                specs.insert(
                    0,
                    _RowSpec(
                        _RootVariantNode(
                            selected_id=variant.selected_id,
                            options=tuple(variant.options),
                        ),
                        "__variant__",
                        "Variant",
                    ),
                )
            return specs
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

    def _commit_gate(self) -> bool:
        """Commit the focused row's pending value before a move.

        Returns False (blocking the move) when the pending text fails
        parsing or tree validation — the error is already surfaced on
        the row by the cell.
        """
        cell = self._focused_cell()
        commit = getattr(cell, "commit_pending", None)
        if commit is None:
            return True
        result = commit()
        return result is None or result.ok

    def _focus_cursor_cell(self) -> None:
        """Give Textual focus to the cursor row's editor (text rows get
        their Input; everything else focuses the list for key bindings).

        Programmatic focus raises a one-shot flag so the resulting
        DescendantFocus event is not mistaken for a user click-away
        (the events arrive asynchronously and would race the cursor).
        """
        cell = self._focused_cell()
        focus_value = getattr(cell, "focus_value", None)
        if focus_value is not None and not getattr(
            self._focused_row(), "readonly", False
        ):
            self._programmatic_focus = getattr(self, "_programmatic_focus", 0) + 1
            focus_value()
            return
        self.focus()

    def _neighbor_visible(self, delta: int) -> int | None:
        """Nearest visible row index in ``delta`` direction, or None."""
        visible = self._visible_indices()
        if not visible:
            return None
        candidates = [i for i in visible if (i > self._cursor if delta > 0 else i < self._cursor)]
        if not candidates:
            return None
        return min(candidates) if delta > 0 else max(candidates)

    def action_cursor_up(self) -> None:
        # Commit even at the boundary — moving "off the edge" is still
        # a blur in form terms; the pending value must not stay limbo.
        if not self._commit_gate():
            return
        target = self._neighbor_visible(-1)
        if target is not None:
            self._move_cursor(target)

    def action_cursor_down(self) -> None:
        if not self._commit_gate():
            return
        target = self._neighbor_visible(+1)
        if target is not None:
            self._move_cursor(target)

    def on_mount(self) -> None:
        """Announce the initial focused row so the HelpBar starts populated,
        and put Textual focus on its editor (form mode: focus = edit)."""
        self._post_cursor_moved()
        self.call_after_refresh(self._focus_cursor_cell)

    def _post_cursor_moved(self) -> None:
        specs = self._row_specs()
        if not (0 <= self._cursor < len(specs)):
            return
        spec = specs[self._cursor]
        self.post_message(CursorMoved(path=spec.path, node=spec.node))

    def _move_cursor(self, new_idx: int) -> None:
        rows = list(self.query(FieldRow))
        if not rows:
            return
        rows[self._cursor].set_focused(False)
        self._cursor = new_idx
        rows[new_idx].set_focused(True)
        # Glide the newly focused row into view instead of jump-cutting.
        rows[new_idx].scroll_visible(animate=True, duration=0.15)
        self._post_cursor_moved()
        self._focus_cursor_cell()

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        """Sync the cursor when focus lands inside a different row —
        the mouse-click-on-an-Input path. Click-away commits (form
        habit); a failed commit bounces focus back to the dirty row."""
        pending = getattr(self, "_programmatic_focus", 0)
        if pending > 0:
            # Our own _focus_cursor_cell caused this event (a counter:
            # rapid programmatic moves queue several events before any
            # get processed); the cursor already points at the right row.
            self._programmatic_focus = pending - 1
            return
        widget: Any = event.widget
        row: FieldRow | None = None
        node = widget
        while node is not None:
            if isinstance(node, FieldRow):
                row = node
                break
            node = node.parent
        if row is None:
            return
        rows = list(self.query(FieldRow))
        try:
            idx = rows.index(row)
        except ValueError:
            return
        if idx == self._cursor:
            return
        if not self._commit_gate():
            previous = self._focused_cell()
            focus_value = getattr(previous, "focus_value", None)
            if focus_value is not None:
                self._programmatic_focus = getattr(self, "_programmatic_focus", 0) + 1
                focus_value()
            return
        rows[self._cursor].set_focused(False)
        self._cursor = idx
        rows[idx].set_focused(True)
        self._post_cursor_moved()

    def on_advance_requested(self, event) -> None:
        """Enter committed a value inside an Input — advance the form."""
        event.stop()
        target = self._neighbor_visible(+1)
        if target is not None:
            self._move_cursor(target)

    def action_jump_next_required(self) -> None:
        """`n` — cycle the cursor to the next row whose subtree still
        misses a required value. The fastest route from "opened the
        form" to "valid config" regardless of field declaration order.
        """
        missing = self._form_tree.missing_required_paths()
        if not missing:
            return
        specs = self._row_specs()
        visible = set(self._visible_indices())
        hits = [
            idx
            for idx, spec in enumerate(specs)
            if idx in visible
            and spec.path
            and any(
                m == spec.path or m.startswith(f"{spec.path}.") for m in missing
            )
        ]
        if not hits:
            return
        after = [idx for idx in hits if idx > self._cursor]
        target = after[0] if after else hits[0]
        if target != self._cursor:
            self._move_cursor(target)

    def focus_path(self, path: str) -> bool:
        """Move the cursor to the row addressing ``path``.

        Accepts exact row paths and *descendant* paths — a validation
        error at ``addresses.0.network`` focuses the ``addresses`` row
        on the root screen. Returns False when no row matches.
        """
        specs = self._row_specs()
        visible = set(self._visible_indices())
        target: int | None = None
        for idx, spec in enumerate(specs):
            if idx not in visible:
                continue
            if spec.path == path:
                target = idx
                break
            if spec.path and path.startswith(f"{spec.path}.") and target is None:
                target = idx
        if target is None or target == self._cursor:
            return target is not None
        self._move_cursor(target)
        return True

    def _refresh_rows(self) -> None:
        specs = self._row_specs()
        if specs:
            self._cursor = min(self._cursor, len(specs) - 1)
        else:
            self._cursor = 0
        self.refresh(recompose=True)
        self._post_cursor_moved()

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

    def _reject_readonly(self, row: FieldRow | None) -> bool:
        """Show the read-only helper and report True when ``row`` is locked."""
        if row is None or row.path not in self._readonly_paths():
            return False
        row.set_error("read-only — value is managed by the caller")
        return True

    def action_activate_focused(self) -> None:
        """Enter on the focused row.

        - Containers open (drill into a child screen).
        - Large choices open the chooser.
        - Everything else advances to the next row — the spreadsheet /
          form habit. (Text rows never reach this handler: their Input
          consumes Enter and posts AdvanceRequested after committing.)
        Values change via Space (bool) and Left/Right (bool/choice/union).
        """
        from pydantic_studio.renderers.textual_.widgets.cells import ChoiceCell

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
        if isinstance(cell, ChoiceCell) and cell.large_choice:
            if self._reject_readonly(row):
                return
            cell.open_chooser()
            return
        target = self._neighbor_visible(+1)
        if target is not None:
            self._move_cursor(target)

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

        if self._reject_readonly(self._focused_row()):
            return
        cell = self._focused_cell()
        if isinstance(cell, BoolCell):
            cell.toggle()

    def action_cycle_next_focused(self) -> None:
        """Right on the focused row -> cycle bool/small-choice/union values.

        Text rows never reach this: their Input consumes Left/Right for
        caret movement — exactly the disambiguation a form needs.
        """
        from pydantic_studio.renderers.textual_.widgets.cells import (
            BoolCell,
            ChoiceCell,
        )

        row = self._focused_row()
        if self._reject_readonly(row):
            return
        if row is not None and row.node.kind == "union":
            self._cycle_union(row.node, +1)
            row.refresh(recompose=True)
            return
        if row is not None and row.node.kind == "root_variant":
            self._cycle_root_variant(+1)
            return

        cell = self._focused_cell()
        if isinstance(cell, BoolCell):
            cell.toggle()
            return
        if isinstance(cell, ChoiceCell) and not cell.large_choice:
            cell.cycle_next()

    def action_cycle_prev_focused(self) -> None:
        """Left on the focused row -> reverse cycle where possible."""
        from pydantic_studio.renderers.textual_.widgets.cells import (
            BoolCell,
            ChoiceCell,
        )

        row = self._focused_row()
        if self._reject_readonly(row):
            return
        if row is not None and row.node.kind == "union":
            self._cycle_union(row.node, -1)
            row.refresh(recompose=True)
            return
        if row is not None and row.node.kind == "root_variant":
            self._cycle_root_variant(-1)
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

    def _cycle_root_variant(self, delta: int) -> None:
        variant = self._form_tree.variant
        if variant is None or not variant.options:
            return
        ids = [option.id for option in variant.options]
        try:
            idx = ids.index(variant.selected_id)
        except ValueError:
            idx = 0
        new_id = ids[(idx + delta) % len(ids)]
        result = self._form_tree.select_root_variant(new_id)
        if not result.ok:
            row = self._focused_row()
            if row is not None:
                row.set_error("; ".join(result.errors))
            return
        if self._base_path == "":
            self._group = self._form_tree.root
        self._cursor = 0
        self._refresh_rows()
        self.call_after_refresh(self._focus_cursor_cell)

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
        """Esc — layered: revert field > clear filter > pop screen > session.

        - If the focused field has uncommitted text → revert it.
        - Else if a filter is active → clear it (all rows return).
        - Else if the active screen is a drilled-in child (more than
          one ConfigScreen on the stack) → pop one level.
        - Else (root screen) → cancel the session (same flow as Ctrl+C:
          clean trees exit, dirty trees get the confirm screen). Esc
          means "undo what I'm in the middle of" at every level.
        """
        from pydantic_studio.renderers.textual_.screens import ConfigScreen

        cell = self._focused_cell()
        if cell is not None and getattr(cell, "is_dirty", lambda: False)():
            cell.revert()
            return
        if cell is not None and cell.editing:
            # Legacy modal cells (none in-tree since form mode, but
            # third-party cells may still use the lifecycle).
            cancel = getattr(cell, "cancel_edit", cell.exit_edit)
            cancel()
            return
        clear_filter = getattr(self.screen, "clear_filter", None)
        if clear_filter is not None and clear_filter():
            return
        config_screens = [
            s for s in self.app.screen_stack if isinstance(s, ConfigScreen)
        ]
        if len(config_screens) > 1:
            self.app.pop_screen()
            return
        cancel_session = getattr(self.app, "action_cancel_session", None)
        if cancel_session is not None:
            cancel_session()

    def on_row_clicked(self, event: RowClicked) -> None:
        """Mouse click on a row's chrome (label/marker/value statics)."""
        event.stop()
        rows = list(self.query(FieldRow))
        for idx, row in enumerate(rows):
            if row.path == event.path:
                if idx != self._cursor and self._commit_gate():
                    self._move_cursor(idx)
                elif idx == self._cursor:
                    self._focus_cursor_cell()
                return

    def on_row_delete_requested(self, event) -> None:
        """Click on a row's ✕ (container screens)."""
        event.stop()
        rows = list(self.query(FieldRow))
        for idx, row in enumerate(rows):
            if row.path == event.path:
                if idx != self._cursor:
                    self._move_cursor(idx)
                self.action_delete_focused()
                return
