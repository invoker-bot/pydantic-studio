"""Unit tests for FieldListView — row mount, cursor nav, scroll."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App
from textual.widgets import Static

from pydantic_studio import (
    VariantRegistry,
    VariantSpec,
    build_form_tree,
    build_variant_form_tree,
)
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow


class _Schema(BaseModel):
    name: str = "alpha"
    count: int = 1
    enabled: bool = False


class _Big(BaseModel):
    """30 fields to exercise scroll behavior."""
    f00: str = ""
    f01: str = ""
    f02: str = ""
    f03: str = ""
    f04: str = ""
    f05: str = ""
    f06: str = ""
    f07: str = ""
    f08: str = ""
    f09: str = ""
    f10: str = ""
    f11: str = ""
    f12: str = ""
    f13: str = ""
    f14: str = ""
    f15: str = ""
    f16: str = ""
    f17: str = ""
    f18: str = ""
    f19: str = ""
    f20: str = ""
    f21: str = ""
    f22: str = ""
    f23: str = ""
    f24: str = ""
    f25: str = ""
    f26: str = ""
    f27: str = ""
    f28: str = ""
    f29: str = ""


class _Host(App):
    def __init__(
        self, view: FieldListView, readonly_paths: frozenset[str] = frozenset()
    ) -> None:
        super().__init__()
        self._view = view
        self.readonly_paths = readonly_paths

    def compose(self):
        yield self._view


class _EmailConfig(BaseModel):
    address: str = "ops@example.com"


class _SlackConfig(BaseModel):
    channel: str = "#ops"


class _OptionalInner(BaseModel):
    host: str | None = None
    port: int = 5432


class _OptionalHost(BaseModel):
    primary: _OptionalInner | None = None


def _value_text(row: FieldRow) -> str:
    return str(row.query_one(".field-row--value", Static).render())


@pytest.mark.asyncio
async def test_field_list_mounts_one_row_per_child() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        rows = list(view.query(FieldRow))
        assert len(rows) == 3
        names = [r.label_text for r in rows]
        assert names == ["name", "count", "enabled"]


@pytest.mark.asyncio
async def test_field_list_root_variant_row_cycles_root_model() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_EmailConfig, label="Email"),
                VariantSpec(id="slack", model=_SlackConfig, label="Slack"),
            ]
        ),
        selected_id="email",
    )
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        assert [row.label_text for row in view.query(FieldRow)] == ["Variant", "address"]

        await pilot.press("right")
        await pilot.pause()

        assert tree.variant is not None
        assert tree.variant.selected_id == "slack"
        assert [row.label_text for row in view.query(FieldRow)] == ["Variant", "channel"]


@pytest.mark.asyncio
async def test_field_list_initial_cursor_is_zero() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        assert view.cursor == 0
        rows = list(view.query(FieldRow))
        assert rows[0].marker_text == "▎"
        assert rows[1].marker_text == " "


@pytest.mark.asyncio
async def test_field_list_down_advances_cursor() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert view.cursor == 1
        rows = list(view.query(FieldRow))
        assert rows[0].marker_text == " "
        assert rows[1].marker_text == "▎"


@pytest.mark.asyncio
async def test_field_list_up_at_top_clamps_to_zero() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        assert view.cursor == 0


@pytest.mark.asyncio
async def test_field_list_down_at_bottom_clamps() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("down")
        await pilot.press("down")  # one past the end
        await pilot.press("down")  # extra
        await pilot.pause()
        assert view.cursor == 2  # last index for 3 rows


@pytest.mark.asyncio
async def test_field_list_empty_group_mounts_zero_rows() -> None:
    class _Empty(BaseModel):
        pass

    tree = build_form_tree(_Empty)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        assert list(view.query(FieldRow)) == []
        # Cursor stays at 0 (no clamp underflow).
        assert view.cursor == 0


@pytest.mark.asyncio
async def test_field_list_focused_row_path_is_dotted() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="root")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        rows = list(view.query(FieldRow))
        # Each row's path is `<base>.<name>`; base="root" -> "root.name".
        assert rows[0].path == "root.name"
        assert rows[1].path == "root.count"
        # At base_path="" the dot is omitted -> just the name (Task 6 covers).


@pytest.mark.asyncio
async def test_field_list_blank_base_path_uses_name_only() -> None:
    tree = build_form_tree(_Schema)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        rows = list(view.query(FieldRow))
        assert rows[0].path == "name"


@pytest.mark.asyncio
async def test_field_list_thirty_rows_mount_without_crash() -> None:
    """Smoke: scroll container handles 30 rows. Detail visual check is manual."""
    tree = build_form_tree(_Big)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        rows = list(view.query(FieldRow))
        assert len(rows) == 30


@pytest.mark.asyncio
async def test_field_list_enter_on_bool_row_advances_not_toggles() -> None:
    """Form mode: Enter is the flow key (commit+next); Space toggles."""
    from pydantic import BaseModel

    class _BoolOnly(BaseModel):
        debug: bool = False

    tree = build_form_tree(_BoolOnly)
    tree.set_value("debug", False)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert tree.root.find("debug").value is False


@pytest.mark.asyncio
async def test_field_list_space_on_bool_row_toggles() -> None:
    from pydantic import BaseModel

    class _BoolOnly(BaseModel):
        debug: bool = False

    tree = build_form_tree(_BoolOnly)
    tree.set_value("debug", False)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert tree.root.find("debug").value is True


@pytest.mark.asyncio
async def test_field_list_delete_clears_optional_group_row() -> None:
    tree = build_form_tree(
        _OptionalHost,
        existing={"primary": {"host": "db.internal", "port": 15432}},
    )
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        row = next(iter(view.query(FieldRow)))
        assert _value_text(row) == "2 fields"

        await pilot.press("delete")
        await pilot.pause()

        primary = tree.root.find("primary")
        assert primary is not None
        assert primary.omitted is True
        assert tree.to_instance().primary is None
        row = next(iter(view.query(FieldRow)))
        assert _value_text(row) == "not set"


@pytest.mark.asyncio
async def test_field_list_delete_rejects_readonly_optional_group_row() -> None:
    tree = build_form_tree(
        _OptionalHost,
        existing={"primary": {"host": "db.internal", "port": 15432}},
    )
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view, readonly_paths=frozenset({"primary"})).run_test() as pilot:
        await pilot.pause()

        await pilot.press("delete")
        await pilot.pause()

        assert tree.to_instance().primary == _OptionalInner(
            host="db.internal",
            port=15432,
        )
        row = next(iter(view.query(FieldRow)))
        assert "read-only" in row.helper_text


@pytest.mark.asyncio
async def test_field_list_right_on_small_choice_cycles() -> None:
    from enum import StrEnum

    from pydantic import BaseModel

    class _Lvl(StrEnum):
        DEBUG = "debug"
        INFO = "info"
        WARN = "warn"

    class _S(BaseModel):
        level: _Lvl = _Lvl.INFO

    tree = build_form_tree(_S)
    tree.set_value("level", _Lvl.INFO)
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        # info -> warn
        assert tree.root.find("level").value == _Lvl.WARN


@pytest.mark.asyncio
async def test_field_list_string_row_is_directly_editable() -> None:
    """Form mode: no edit mode to enter — the row hosts a live Input."""
    from textual.widgets import Input

    from pydantic_studio.renderers.textual_.widgets.cells import TextCell

    tree = build_form_tree(_Schema)
    tree.set_value("name", "alpha")
    view = FieldListView(group=tree.root, form_tree=tree, base_path="")
    async with _Host(view).run_test() as pilot:
        await pilot.pause()
        rows = list(view.query(FieldRow))
        cell = rows[0].query_one(TextCell)
        assert cell.query_one(Input).value == "alpha"
        assert cell.editing is False
