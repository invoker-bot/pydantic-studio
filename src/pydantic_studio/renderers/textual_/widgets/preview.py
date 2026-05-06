"""PreviewPane — live YAML render of the current FormTree state."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from textual.widgets import RichLog

if TYPE_CHECKING:
    from pydantic_studio.tree.nodes import FormTree


class PreviewPane(RichLog):
    """Read-only live YAML view of the FormTree.

    Subscribes to no events directly — the EditorScreen calls
    ``refresh_preview()`` after every successful mutation.
    """

    def __init__(self, tree: FormTree) -> None:
        super().__init__(id="preview", wrap=False, markup=False, highlight=False)
        self.form_tree = tree

    def on_mount(self) -> None:
        self.refresh_preview()

    def refresh_preview(self) -> None:
        """Re-render the FormTree as YAML and update the log."""
        self.clear()
        text = self._render_yaml()
        for line in text.splitlines():
            self.write(line)

    def _render_yaml(self) -> str:
        """Render the current tree state as a YAML string.

        Prefers ``to_instance().model_dump()`` so schema defaults appear
        in the preview even for a freshly-built tree. Falls back to
        ``tree.to_python()`` when validation fails — that path keeps
        partially-edited trees previewable even when ``save_yaml`` would
        refuse them.
        """
        from pydantic_studio.exceptions import ValidationFailedError
        from pydantic_studio.io.yaml import _build_commented_map, _yaml

        schema = self.form_tree.schema_class
        if schema is None:
            return "<no schema bound>"
        try:
            # mode="json" coerces Enum members, datetime/date/time, Decimal, UUID, etc.
            # into YAML-representable scalars (strings/numbers/bools).
            data = self.form_tree.to_instance().model_dump(mode="json")
        except ValidationFailedError:
            data = self.form_tree.to_python()
        if not data:
            return "<empty>"
        try:
            cm = _build_commented_map(data, schema, source=None)
        except Exception as e:
            return f"<preview error: {e}>"
        buf = io.StringIO()
        _yaml().dump(cm, buf)
        return buf.getvalue()
