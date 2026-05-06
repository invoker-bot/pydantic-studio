"""Sidebar widget — renders the FormTree's GroupNode hierarchy as a Tree."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Tree

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree, GroupNode


class Sidebar(Tree):
    """Navigation tree showing all GroupNodes in the FormTree.

    The widget's root.data carries the path string ("" for root,
    "subsection.subsubsection" for nested). EditorScreen listens for the
    `Tree.NodeSelected` message and updates the EditorPane to focus that
    group.

    For the MVP, leaf nodes (non-group) are NOT shown in the sidebar —
    only the structure of nested BaseModel containers. Leaves appear in
    the EditorPane when their parent group is focused.
    """

    def __init__(self, tree: FormTree) -> None:
        # The Tree's root label = the schema's class name.
        root_label = (
            tree.schema_name.split(":")[-1]
            if ":" in tree.schema_name
            else tree.schema_name
        )
        super().__init__(label=root_label, id="sidebar")
        self.form_tree = tree
        self._populate(self.root, tree.root)
        # Bind the GroupNode itself to the root for path resolution.
        self.root.data = ""  # empty path = root group
        self.root.expand()

    def _populate(self, parent_node, group: GroupNode) -> None:
        """Recursively add child GroupNodes under ``parent_node``."""
        from pydantic_studio.tree.nodes import GroupNode

        for child in group.fields:
            if isinstance(child, GroupNode):
                # Use the child's name as the label.
                label = child.name or "?"
                t_node = parent_node.add(label)
                # data carries the path string for set_value lookups.
                base = parent_node.data or ""
                t_node.data = f"{base}.{label}".lstrip(".")
                self._populate(t_node, child)
                t_node.expand()
