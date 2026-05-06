"""Server-side render helpers for FormTree → HTML widgets."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import AnyNode, FormTree, GroupNode


def render_yaml_preview(tree: FormTree) -> str:
    """Render the FormTree as YAML for preview display."""
    from pydantic_studio.io.yaml import _build_commented_map, _yaml

    schema = tree.schema_class
    if schema is None:
        return "<no schema>"
    try:
        instance = tree.to_instance()
        data = instance.model_dump(mode="json")
    except Exception:
        data = tree.to_python()
    if not data:
        return "<empty>"
    try:
        cm = _build_commented_map(data, schema, source=None)
    except Exception as e:
        return f"<preview error: {e}>"
    buf = io.StringIO()
    _yaml().dump(cm, buf)
    return buf.getvalue()


def list_root_fields(tree: FormTree) -> list[tuple[str, AnyNode]]:
    """Return [(path, node)] for non-group children of the root group."""
    from pydantic_studio.tree.nodes import GroupNode

    out: list[tuple[str, AnyNode]] = []
    for child in tree.root.fields:
        if isinstance(child, GroupNode):
            continue
        out.append((child.name, child))
    return out


def list_groups(tree: FormTree) -> list[tuple[str, str]]:
    """Return [(path, label)] for all GroupNodes (sidebar nav)."""
    from pydantic_studio.tree.nodes import GroupNode

    out: list[tuple[str, str]] = [("", "<root>")]

    def walk(group: GroupNode, base_path: str) -> None:
        for child in group.fields:
            if isinstance(child, GroupNode):
                child_path = f"{base_path}.{child.name}".lstrip(".")
                out.append((child_path, child.name or "?"))
                walk(child, child_path)

    walk(tree.root, "")
    return out


def initial_value_str(node: AnyNode) -> str:
    """Stringify the node's current value for HTML input default.

    Falls back to ``node.default`` when value is None.
    """
    v = getattr(node, "value", None)
    if v is None:
        v = getattr(node, "default", None)
    if v is None:
        return ""
    if node.kind == "bytes" and isinstance(v, (bytes, bytearray)):
        return bytes(v).hex()
    return str(v)
