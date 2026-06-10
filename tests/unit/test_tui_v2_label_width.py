"""Label column sizing — long field names must stay distinguishable.

The fixed width:22 in theme.tcss hard-cut ``auto_tracking_orders_after``
and ``auto_tracking_orders_before`` to the same visible string with no
ellipsis. The column now fits the longest label on screen (clamped),
and anything still longer gets an honest ``…``.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow


class _LongNames(BaseModel):
    auto_tracking_orders_after: float = 300.0
    auto_tracking_orders_before: float = 7200.0
    x: int = 1


class _Absurd(BaseModel):
    this_field_name_is_far_too_long_to_display_in_any_reasonable_column_at_all: int = 1
    y: int = 1


@pytest.mark.asyncio
async def test_long_labels_render_in_full() -> None:
    tree = build_form_tree(_LongNames)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        labels = [row.label_text for row in app.screen.query(FieldRow)]
        assert "auto_tracking_orders_after" in labels
        assert "auto_tracking_orders_before" in labels


@pytest.mark.asyncio
async def test_absurd_labels_get_ellipsis_not_silent_cut() -> None:
    tree = build_form_tree(_Absurd)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        first = app.screen.query(FieldRow).first()
        assert first.label_text.endswith("…")
        assert len(first.label_text) <= 48
