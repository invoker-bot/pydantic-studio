"""Unit tests for SecretCell — masked display + password Input on edit."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, SecretStr
from textual.app import App
from textual.widgets import Input

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_.widgets.cells.secret_cell import SecretCell


class _Schema(BaseModel):
    api_key: SecretStr = SecretStr("")


class _Host(App):
    def __init__(self, cell: SecretCell) -> None:
        super().__init__()
        self._cell = cell

    def compose(self):
        yield self._cell


def _make_cell(initial):
    tree = build_form_tree(_Schema)
    if initial is not None:
        tree.set_value("api_key", initial)
    node = tree.root.find("api_key")
    assert node is not None
    return tree, SecretCell(node=node, path="api_key", form_tree=tree)


@pytest.mark.asyncio
async def test_secret_cell_idle_renders_mask_even_with_value() -> None:
    _, cell = _make_cell("super-secret-value")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == "**********"


@pytest.mark.asyncio
async def test_secret_cell_idle_renders_empty_for_none() -> None:
    _, cell = _make_cell(None)
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        assert cell.value_text == ""


@pytest.mark.asyncio
async def test_secret_cell_enter_edit_uses_password_input() -> None:
    _, cell = _make_cell("hunter2")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        input_widget = cell.query_one(Input)
        assert input_widget.password is True
        # Pre-fills with the actual value (NOT the mask).
        assert input_widget.value == "hunter2"


@pytest.mark.asyncio
async def test_secret_cell_commit_via_enter() -> None:
    tree, cell = _make_cell("old")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        input_widget = cell.query_one(Input)
        input_widget.value = "new-secret"
        await input_widget.action_submit()
        await pilot.pause()
        node = tree.root.find("api_key")
        # SecretStr's underlying value is the committed string.
        assert node.value == "new-secret" or (
            hasattr(node.value, "get_secret_value")
            and node.value.get_secret_value() == "new-secret"
        )
        assert cell.editing is False
        # Idle back to mask.
        assert cell.value_text == "**********"


@pytest.mark.asyncio
async def test_secret_cell_esc_cancels() -> None:
    tree, cell = _make_cell("hunter2")
    async with _Host(cell).run_test() as pilot:
        await pilot.pause()
        cell.enter_edit()
        await pilot.pause()
        cell.cancel_edit()
        await pilot.pause()
        assert cell.editing is False
        # Value unchanged.
        node = tree.root.find("api_key")
        assert (
            node.value == "hunter2"
            or (
                hasattr(node.value, "get_secret_value")
                and node.value.get_secret_value() == "hunter2"
            )
        )
