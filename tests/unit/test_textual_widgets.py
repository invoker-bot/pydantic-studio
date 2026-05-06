"""Per-widget Pilot tests for the Textual renderer."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.textual_ import StudioApp


@pytest.mark.asyncio
async def test_text_input_editor_for_string() -> None:
    class M(BaseModel):
        name: str = "alpha"

    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Input

        inputs = list(app.screen.query(Input))
        assert len(inputs) == 1
        # Initial value matches the default.
        assert inputs[0].value == "alpha"
        # Set value directly + dispatch the submit message.
        inputs[0].value = "beta"
        await inputs[0].action_submit()
        await pilot.pause()

        # The tree's root should reflect the new value.
        name_node = tree.root.find("name")
        assert name_node is not None
        assert name_node.value == "beta"


@pytest.mark.asyncio
async def test_text_input_editor_for_int_parses() -> None:
    class M(BaseModel):
        age: int = 0

    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Input

        inputs = list(app.screen.query(Input))
        assert len(inputs) == 1
        inputs[0].value = "42"
        await inputs[0].action_submit()
        await pilot.pause()
        age = tree.root.find("age")
        assert age is not None
        assert age.value == 42


@pytest.mark.asyncio
async def test_text_input_editor_validation_error_keeps_old_value() -> None:
    class M(BaseModel):
        age: int = 5

    tree = build_form_tree(M)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Input

        inputs = list(app.screen.query(Input))
        inputs[0].value = "not a number"
        await inputs[0].action_submit()
        await pilot.pause()
        age = tree.root.find("age")
        assert age is not None
        assert age.value == 5
