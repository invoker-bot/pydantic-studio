from __future__ import annotations

import pytest
from pydantic import BaseModel, Field
from textual.app import App

from pydantic_studio import EditSession, build_form_tree
from pydantic_studio.renderers.textual_ import StudioScreen
from pydantic_studio.renderers.textual_.screens import ConfirmExitScreen, ErrorsScreen


class _Schema(BaseModel):
    name: str = "alpha"
    debug: bool = False


class _RequiredSchema(BaseModel):
    api_key: str = Field(...)
    timeout: int = 30


class _Host(App):
    def __init__(self, session: EditSession) -> None:
        super().__init__()
        self.session = session
        self.ended = None

    def on_mount(self) -> None:
        self.push_screen(StudioScreen(self.session))

    def on_studio_session_ended(self, event) -> None:
        self.ended = event.outcome


@pytest.mark.asyncio
async def test_studio_screen_ctrl_s_submits_without_exiting_host() -> None:
    session = EditSession(tree=build_form_tree(_Schema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.is_running is True
    assert session.submitted is True
    assert app.ended is not None
    assert app.ended.submitted is True


@pytest.mark.asyncio
async def test_studio_screen_ctrl_c_clean_cancels_without_exiting_host() -> None:
    session = EditSession(tree=build_form_tree(_Schema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.is_running is True
    assert session.cancelled is True
    assert app.ended is not None
    assert app.ended.submitted is False


@pytest.mark.asyncio
async def test_studio_screen_dirty_cancel_opens_confirm() -> None:
    session = EditSession(tree=build_form_tree(_Schema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        session.tree.set_value("name", "changed")
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmExitScreen)


@pytest.mark.asyncio
async def test_studio_screen_invalid_submit_shows_errors() -> None:
    session = EditSession(tree=build_form_tree(_RequiredSchema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, ErrorsScreen)
    assert session.outcome is None


@pytest.mark.asyncio
async def test_action_bar_buttons_work_inside_embedded_screen() -> None:
    session = EditSession(tree=build_form_tree(_Schema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#action-save")
        await pilot.pause()
    assert session.submitted is True


@pytest.mark.asyncio
async def test_confirm_discard_finishes_embedded_screen_cancelled() -> None:
    session = EditSession(tree=build_form_tree(_Schema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        session.tree.set_value("name", "changed")
        await pilot.press("ctrl+c")
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
    assert session.cancelled is True
