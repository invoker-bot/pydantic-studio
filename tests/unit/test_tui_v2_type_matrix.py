"""TUI v2 type matrix tests for leaf, Pydantic, and composite nodes."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel, EmailStr, HttpUrl, SecretBytes
from textual.widgets import Input

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.screens import ConfigScreen, RenameKeyScreen
from pydantic_studio.renderers.textual_.widgets.cells import SecretCell, TextCell
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView
from pydantic_studio.renderers.textual_.widgets.field_row import FieldRow


class _PydanticLeafSchema(BaseModel):
    amount: Decimal = Decimal("1.00")
    when: datetime = datetime(2026, 5, 16, 9, 30)
    on: date = date(2026, 5, 16)
    at: time = time(9, 30)
    interval: timedelta = timedelta(minutes=5)
    host: IPv4Address = IPv4Address("127.0.0.1")
    network: IPv4Network = IPv4Network("10.0.0.0/24")
    api: HttpUrl = HttpUrl("https://example.com")
    contact: EmailStr = "ops@example.com"
    home: Path = Path("/tmp")
    request_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    matcher: re.Pattern[str] = re.compile(r"^[a-z]+$")
    blob: bytes = b"\xde\xad"


class _SecretBytesSchema(BaseModel):
    token: SecretBytes = SecretBytes(b"old-token")


class _AnySchema(BaseModel):
    payload: Any = "initial"


class _CompositeSchema(BaseModel):
    tags: list[str] = ["a", "b"]
    settings: dict[str, int] = {"timeout": 30}
    value: int | str = 0


class _IntKeyMappingSchema(BaseModel):
    settings: dict[int, int] = {1: 10}


def _config_screen_depth(app: StudioApp) -> int:
    return sum(1 for screen in app.screen_stack if isinstance(screen, ConfigScreen))


@pytest.mark.parametrize(
    ("field", "raw", "expected"),
    [
        ("amount", "19.99", Decimal("19.99")),
        ("when", "2026-05-16T10:30:00", datetime(2026, 5, 16, 10, 30)),
        ("on", "2026-05-17", date(2026, 5, 17)),
        ("at", "11:45:30", time(11, 45, 30)),
        ("interval", "PT1H", timedelta(hours=1)),
        ("host", "192.168.1.5", "192.168.1.5"),
        ("network", "192.168.0.0/24", "192.168.0.0/24"),
        ("api", "https://api.example.com/v2", "https://api.example.com/v2"),
        ("contact", "dev@example.com", "dev@example.com"),
        ("home", "/var/lib/app", "/var/lib/app"),
        ("request_id", "00000000-0000-0000-0000-000000000002", UUID(int=2)),
        ("matcher", "^[0-9]+$", "^[0-9]+$"),
        ("blob", "beef", b"\xbe\xef"),
    ],
)
@pytest.mark.asyncio
async def test_pydantic_leaf_text_cells_commit_valid_input(field, raw, expected) -> None:
    tree = build_form_tree(_PydanticLeafSchema)
    node = tree.root.find(field)
    assert node is not None
    cell = TextCell(node=node, path=field, form_tree=tree)

    class _Host(StudioApp):
        def compose(self):
            yield cell

        def on_mount(self) -> None:
            pass

    async with _Host(tree=tree, save_path=None).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        input_widget = cell.query_one(Input)
        input_widget.value = raw
        await input_widget.action_submit()
        await pilot.pause()

    assert tree.root.find(field).value == expected
    assert cell.last_error is None


@pytest.mark.asyncio
async def test_pydantic_leaf_validation_error_stays_visible_on_row() -> None:
    tree = build_form_tree(_PydanticLeafSchema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        field_list = app.screen.query_one(FieldListView)
        while app.screen.query(FieldRow)[field_list.cursor].node.name != "contact":
            field_list.action_cursor_down()
        await pilot.press("enter")
        await pilot.pause()
        input_widget = app.screen.query_one(Input)
        input_widget.value = "not-an-email"
        await input_widget.action_submit()
        await pilot.pause()
        row = app.screen.query(FieldRow)[field_list.cursor]
        assert tree.root.find("contact").value != "not-an-email"
        assert "email" in row.helper_text.lower() or "valid" in row.helper_text.lower()


@pytest.mark.asyncio
async def test_secret_bytes_cell_commits_utf8_input_as_bytes() -> None:
    tree = build_form_tree(_SecretBytesSchema)
    node = tree.root.find("token")
    assert node is not None
    cell = SecretCell(node=node, path="token", form_tree=tree)

    class _Host(StudioApp):
        def compose(self):
            yield cell

        def on_mount(self) -> None:
            pass

    async with _Host(tree=tree, save_path=None).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        input_widget = cell.query_one(Input)
        input_widget.value = "new-token"
        await input_widget.action_submit()
        await pilot.pause()

    assert tree.root.find("token").value == b"new-token"
    assert cell.last_error is None


@pytest.mark.asyncio
async def test_any_field_accepts_json_and_plain_text_input() -> None:
    tree = build_form_tree(_AnySchema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        input_widget = app.screen.query_one(Input)
        input_widget.value = '{"k": [1, true]}'
        await input_widget.action_submit()
        await pilot.pause()
        assert tree.root.find("payload").value == {"k": [1, True]}

        await pilot.press("enter")
        await pilot.pause()
        input_widget = app.screen.query_one(Input)
        input_widget.value = "plain text"
        await input_widget.action_submit()
        await pilot.pause()
        assert tree.root.find("payload").value == "plain text"


@pytest.mark.asyncio
async def test_sequence_drill_add_move_delete_and_edit_item() -> None:
    tree = build_form_tree(
        _CompositeSchema,
        existing={"tags": ["a", "b"], "settings": {"timeout": 30}, "value": 0},
    )
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert _config_screen_depth(app) == 1
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        assert _config_screen_depth(app) == 2

        field_list = app.screen.query_one(FieldListView)
        assert [row.label_text for row in app.screen.query(FieldRow)] == ["0", "1"]

        field_list.action_add_item()
        await pilot.pause()
        assert len(tree.root.find("tags").items) == 3

        field_list.action_move_focused_down()
        await pilot.pause()
        assert [item.value for item in tree.root.find("tags").items] == ["b", "a", None]

        await pilot.press("enter")
        await pilot.pause()
        input_widget = app.screen.query_one(Input)
        input_widget.value = "edited"
        await input_widget.action_submit()
        await pilot.pause()
        assert tree.root.find("tags").items[1].value == "edited"

        field_list.action_delete_focused()
        await pilot.pause()
        assert [item.value for item in tree.root.find("tags").items] == ["b", None]


@pytest.mark.asyncio
async def test_mapping_drill_edit_value_add_delete_and_rename_key() -> None:
    tree = build_form_tree(
        _CompositeSchema,
        existing={"tags": ["a", "b"], "settings": {"timeout": 30}, "value": 0},
    )
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        field_list = app.screen.query_one(FieldListView)
        assert app.screen.query(FieldRow)[0].label_text == "timeout"

        await pilot.press("enter")
        await pilot.pause()
        input_widget = app.screen.query_one(Input)
        input_widget.value = "60"
        await input_widget.action_submit()
        await pilot.pause()
        settings = tree.root.find("settings")
        assert settings.entries[0][1].value == 60

        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, RenameKeyScreen)
        rename_input = app.screen.query_one(Input)
        rename_input.value = "retries"
        await rename_input.action_submit()
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen)
        assert settings.entries[0][0].value == "retries"

        field_list.action_add_entry()
        await pilot.pause()
        assert len(settings.entries) == 2

        field_list.action_delete_focused()
        await pilot.pause()
        assert len(settings.entries) == 1


@pytest.mark.asyncio
async def test_mapping_rename_parses_typed_key_and_reports_parse_error() -> None:
    tree = build_form_tree(
        _IntKeyMappingSchema,
        existing={"settings": {1: 10}},
    )
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, RenameKeyScreen)
        rename_input = app.screen.query_one(Input)
        rename_input.value = "2"
        await rename_input.action_submit()
        await pilot.pause()
        settings = tree.root.find("settings")
        assert settings.entries[0][0].value == 2

        await pilot.press("r")
        await pilot.pause()
        rename_input = app.screen.query_one(Input)
        rename_input.value = "not-an-int"
        await rename_input.action_submit()
        await pilot.pause()
        assert isinstance(app.screen, RenameKeyScreen)
        assert "int" in app.screen.error_text
        assert settings.entries[0][0].value == 2


@pytest.mark.asyncio
async def test_mapping_add_entry_generates_typed_int_key() -> None:
    tree = build_form_tree(
        _IntKeyMappingSchema,
        existing={"settings": {0: 10}},
    )
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        field_list = app.screen.query_one(FieldListView)
        field_list.action_add_entry()
        await pilot.pause()

    settings = tree.root.find("settings")
    assert [key.value for key, _ in settings.entries] == [0, 1]


@pytest.mark.asyncio
async def test_union_cycle_variant_drill_and_edit_selected_value() -> None:
    tree = build_form_tree(
        _CompositeSchema,
        existing={"tags": ["a", "b"], "settings": {"timeout": 30}, "value": 0},
    )
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("down")
        await pilot.press("tab")
        await pilot.pause()
        union = tree.root.find("value")
        assert union.selected_index == 1

        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        assert _config_screen_depth(app) == 2
        await pilot.press("enter")
        await pilot.pause()
        input_widget = app.screen.query_one(Input)
        input_widget.value = "from-union"
        await input_widget.action_submit()
        await pilot.pause()

    assert tree.to_instance().value == "from-union"
