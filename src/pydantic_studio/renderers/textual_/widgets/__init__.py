"""Textual widgets for pydantic-studio.

After the legacy cutover, the package surfaces the M1 chrome widgets.
Editor cells (M2), screens for sequence/mapping/union (M3-M5), and the
errors screen (M5) land here as they're built.
"""

from __future__ import annotations

from pydantic_studio.renderers.textual_.widgets.breadcrumb import Breadcrumb
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow
from pydantic_studio.renderers.textual_.widgets.footer_hints import FooterHints

__all__ = [
    "Breadcrumb",
    "FieldListView",
    "FieldRow",
    "FooterHints",
]
