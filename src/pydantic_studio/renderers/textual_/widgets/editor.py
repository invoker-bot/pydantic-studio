"""EditorPane — scrollable VBox of NodeEditor widgets for a focused group."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.containers import VerticalScroll
from textual.widget import Widget

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree, GroupNode


class EditorPane(VerticalScroll):
    """Scrollable container of NodeEditor widgets for the focused group.

    The pane's content is regenerated whenever the user picks a different
    group in the sidebar. EditorScreen owns the focused-group state and
    calls ``set_group(group, path)``.
    """

    def __init__(self, tree: FormTree) -> None:
        super().__init__(id="editor")
        self.form_tree = tree
        self._current_group_path = ""

    def on_mount(self) -> None:
        # Default to the root group on first mount.
        self.set_group(self.form_tree.root, path="")

    def set_group(self, group: GroupNode, path: str) -> None:
        """Mount one NodeEditor per non-group child."""
        from pydantic_studio.tree.nodes import GroupNode

        self._current_group_path = path
        # Clear existing editors.
        self.remove_children()
        for child in group.fields:
            if isinstance(child, GroupNode):
                # GroupNodes appear in the sidebar — skip in the editor pane.
                continue
            child_path = f"{path}.{child.name}".lstrip(".") if path else child.name
            try:
                editor = NodeEditor.dispatch(child, child_path, self.form_tree)
            except ImportError:
                # Editors land in Tasks 6-9; tolerate missing classes during
                # incremental development. Skip the field rather than crash.
                continue
            self.mount(editor)


class NodeEditor(Widget):
    """Base class — concrete subclasses dispatch on node.kind.

    Subclasses set ``self.field_path`` (the path used for set_value calls)
    and implement their own ``compose()`` + event handlers.
    """

    def __init__(
        self,
        node: AnyNode,
        path: str,
        tree: FormTree,
    ) -> None:
        super().__init__()
        self.node = node
        self.field_path = path
        self.form_tree = tree

    @classmethod
    def dispatch(
        cls,
        node: AnyNode,
        path: str,
        tree: FormTree,
    ) -> NodeEditor:
        """Return a concrete NodeEditor subclass instance for ``node.kind``.

        Falls back to TextInputEditor for any "stringy" or numeric kind.
        Concrete editor implementations land in Tasks 6-9.
        """
        # Late imports avoid circular dependencies during widget bootstrap
        # AND tolerate missing editor classes during incremental dev.
        from pydantic_studio.renderers.textual_.widgets.containers import (
            MappingEditor,
            SequenceEditor,
            UnionEditor,
        )
        from pydantic_studio.renderers.textual_.widgets.scalars import (
            BoolEditor,
            ChoiceEditor,
            TextInputEditor,
        )

        kind = node.kind
        if kind == "bool":
            return BoolEditor(node, path, tree)
        if kind in ("enum", "literal"):
            return ChoiceEditor(node, path, tree)
        if kind == "sequence":
            return SequenceEditor(node, path, tree)
        if kind == "mapping":
            return MappingEditor(node, path, tree)
        if kind == "union":
            return UnionEditor(node, path, tree)
        # All other kinds use the generic text input — string / int / float /
        # decimal / date* / ip* / url / email / path / uuid / secret / pattern / bytes.
        return TextInputEditor(node, path, tree)

    def commit(self, value: Any) -> tuple[bool, str | None]:
        """Validate ``value`` against the node and apply via tree.set_value.

        Returns ``(ok, error_message)``. On success, also triggers a
        preview refresh on the parent screen.
        """
        result = self.form_tree.set_value(self.field_path, value)
        if not result.ok:
            return False, result.errors[0] if result.errors else "invalid"
        # Tell the screen to refresh the preview pane.
        screen = self.screen
        if hasattr(screen, "refresh_preview"):
            screen.refresh_preview()
        return True, None
