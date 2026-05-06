"""Container widgets: SequenceEditor, MappingEditor, UnionEditor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Select

from pydantic_studio.renderers.textual_.widgets.editor import NodeEditor
from pydantic_studio.renderers.textual_.widgets.scalars import TextInputEditor

if TYPE_CHECKING:
    from textual.app import ComposeResult


class SequenceEditor(NodeEditor):
    """Editor for SequenceNode (list/set/tuple).

    Layout:
        [field name]: [Add]
            row 0: <child editor> [Remove]
            row 1: <child editor> [Remove]
            ...
    """

    def compose(self) -> ComposeResult:
        sanitized = TextInputEditor._sanitize_id(self.field_path)
        with Vertical(id=f"seq-{sanitized}"):
            with Horizontal():
                yield Label(f"{self.node.name}: ", classes="field-label")
                yield Button("Add", id=f"add-{sanitized}", variant="primary")
            for i in range(len(self.node.items)):
                yield from self._compose_row(i)

    def _compose_row(self, index: int) -> ComposeResult:
        item = self.node.items[index]
        item_path = f"{self.field_path}[{index}]"
        item_editor = NodeEditor.dispatch(item, item_path, self.form_tree)
        sanitized = TextInputEditor._sanitize_id(self.field_path)
        with Horizontal(id=f"row-{sanitized}-{index}"):
            yield item_editor
            yield Button(
                "Remove",
                id=f"remove-{sanitized}-{index}",
                variant="warning",
            )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        sanitized = TextInputEditor._sanitize_id(self.field_path)
        bid = event.button.id or ""
        if bid == f"add-{sanitized}":
            await self._on_add()
        elif bid.startswith(f"remove-{sanitized}-"):
            try:
                idx = int(bid.rsplit("-", 1)[1])
            except ValueError:
                return
            await self._on_remove(idx)

    async def _on_add(self) -> None:
        result = self.form_tree.add_item(self.field_path)
        if not result.ok:
            return
        await self._rebuild()

    async def _on_remove(self, index: int) -> None:
        result = self.form_tree.remove_item(self.field_path, index)
        if not result.ok:
            return
        await self._rebuild()

    async def _rebuild(self) -> None:
        """Tear down and re-compose. Triggers screen.refresh_preview."""
        # ``recompose()`` awaits removal of existing children before
        # re-mounting fresh ones, so widget ids don't collide.
        await self.recompose()
        screen = self.screen
        if hasattr(screen, "refresh_preview"):
            screen.refresh_preview()


class MappingEditor(NodeEditor):
    """Editor for MappingNode (dict[K, V]).

    Layout:
        [field name]: [Add Entry]
            entry 0: [key label] [value editor] [Remove]
            entry 1: ...
    """

    def compose(self) -> ComposeResult:
        sanitized = TextInputEditor._sanitize_id(self.field_path)
        with Vertical(id=f"map-{sanitized}"):
            with Horizontal():
                yield Label(f"{self.node.name}: ", classes="field-label")
                yield Button(
                    "Add Entry",
                    id=f"add-{sanitized}",
                    variant="primary",
                )
            for i in range(len(self.node.entries)):
                yield from self._compose_entry(i)

    def _compose_entry(self, index: int) -> ComposeResult:
        k_node, v_node = self.node.entries[index]
        v_path = f"{self.field_path}[{index}]"
        v_editor = NodeEditor.dispatch(v_node, v_path, self.form_tree)
        sanitized = TextInputEditor._sanitize_id(self.field_path)
        key_repr = repr(getattr(k_node, "value", k_node.name))
        with Horizontal(id=f"entry-{sanitized}-{index}"):
            yield Label(f"key={key_repr}")
            yield v_editor
            yield Button(
                "Remove",
                id=f"remove-{sanitized}-{index}",
                variant="warning",
            )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        sanitized = TextInputEditor._sanitize_id(self.field_path)
        bid = event.button.id or ""
        if bid == f"add-{sanitized}":
            await self._on_add()
        elif bid.startswith(f"remove-{sanitized}-"):
            try:
                idx = int(bid.rsplit("-", 1)[1])
            except ValueError:
                return
            await self._on_remove(idx)

    async def _on_add(self) -> None:
        existing_keys = {
            getattr(k_node, "value", "") for k_node, _ in self.node.entries
        }
        i = 0
        while f"key{i}" in existing_keys:
            i += 1
        result = self.form_tree.add_entry(self.field_path, key=f"key{i}")
        if not result.ok:
            return
        await self._rebuild()

    async def _on_remove(self, index: int) -> None:
        result = self.form_tree.remove_entry(self.field_path, index)
        if not result.ok:
            return
        await self._rebuild()

    async def _rebuild(self) -> None:
        await self.recompose()
        screen = self.screen
        if hasattr(screen, "refresh_preview"):
            screen.refresh_preview()


class UnionEditor(NodeEditor):
    """Editor for UnionNode — variant picker + nested editor for the
    selected variant.

    Layout:
        [field name]: [variant Select]
            <selected variant's editor>
    """

    def compose(self) -> ComposeResult:
        sanitized = TextInputEditor._sanitize_id(self.field_path)
        options = [
            (name.rsplit(".", 1)[-1], name)
            for name in self.node.variant_type_names
        ]
        initial_value = (
            self.node.variant_type_names[self.node.selected_index]
            if self.node.selected_index is not None
            else Select.NULL
        )
        with Vertical(id=f"union-{sanitized}"):
            with Horizontal():
                yield Label(
                    f"{self.node.name} (variant): ", classes="field-label"
                )
                yield Select(
                    options=options,
                    value=initial_value,
                    id=f"variant-{sanitized}",
                )
            if self.node.selected is not None:
                inner_editor = NodeEditor.dispatch(
                    self.node.selected, self.field_path, self.form_tree
                )
                yield inner_editor

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.value == Select.NULL:
            return
        for i, name in enumerate(self.node.variant_type_names):
            if name == event.value:
                result = self.form_tree.select_variant(self.field_path, i)
                if result.ok:
                    await self._rebuild()
                return

    async def _rebuild(self) -> None:
        await self.recompose()
        screen = self.screen
        if hasattr(screen, "refresh_preview"):
            screen.refresh_preview()
