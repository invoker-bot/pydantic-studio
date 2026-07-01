"""Session outcome protocol — submit vs cancel as first-class results.

Pre-v0.2, run_app() returned None and the only way out was Ctrl+C
("quit"); downstream callers had to *guess* intent after the fact (the
HFT wiring treated quit-after-valid as commit and quit-after-partial as
cancel — silently discarding user input). The fixed contract:

- Ctrl+S = submit: validate, write save_path if configured, exit with
  EditOutcome("submitted"). Works without save_path (caller persists).
- Ctrl+C / Esc-at-root = cancel: clean tree exits immediately with
  EditOutcome("cancelled"); a dirty tree gets a confirm screen
  (Save & exit / Discard / Keep editing).
- Validation failure on submit shows ErrorsScreen and, on dismiss,
  jumps the cursor to the first offending row.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.outcome import EditOutcome
from pydantic_studio.renderers.textual_ import StudioApp
from pydantic_studio.renderers.textual_.screens import (
    ConfirmExitScreen,
    ErrorsScreen,
)
from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView


class _Schema(BaseModel):
    name: str = "alpha"
    debug: bool = False


class _RequiredLast(BaseModel):
    timeout: int = 30
    retries: int = 3
    api_key: str = Field(...)


def test_edit_outcome_shape() -> None:
    ok = EditOutcome(status="submitted")
    cancelled = EditOutcome(status="cancelled")
    assert ok.submitted is True
    assert ok.cancelled is False
    assert cancelled.submitted is False
    assert cancelled.cancelled is True


def test_edit_outcome_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match=r"EditOutcome\.status"):
        EditOutcome(status="abandoned")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_ctrl_s_submits_and_exits_without_save_path() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert app.outcome.submitted is True


@pytest.mark.asyncio
async def test_ctrl_s_submits_and_exits_with_save_path(tmp_path) -> None:
    save = tmp_path / "config.yaml"
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=save)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert app.outcome.submitted is True
    assert save.exists()


@pytest.mark.asyncio
async def test_ctrl_c_on_clean_tree_cancels_immediately() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
    assert app.outcome.submitted is False


@pytest.mark.asyncio
async def test_ctrl_c_on_dirty_tree_asks_for_confirmation() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree.set_value("name", "edited")
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.is_running, "dirty tree must not exit without confirmation"
        assert isinstance(app.screen, ConfirmExitScreen)
        await pilot.press("escape")  # keep editing
        await pilot.pause()
        assert app.is_running
        assert not isinstance(app.screen, ConfirmExitScreen)


@pytest.mark.asyncio
async def test_confirm_discard_exits_cancelled() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree.set_value("name", "edited")
        await pilot.press("ctrl+c")
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
    assert app.outcome.submitted is False


@pytest.mark.asyncio
async def test_confirm_save_exits_submitted(tmp_path) -> None:
    save = tmp_path / "config.yaml"
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=save)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree.set_value("name", "edited")
        await pilot.press("ctrl+c")
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
    assert app.outcome.submitted is True
    assert save.exists()


@pytest.mark.asyncio
async def test_double_ctrl_c_force_discards() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree.set_value("name", "edited")
        await pilot.press("ctrl+c")
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
    assert app.outcome.submitted is False


@pytest.mark.asyncio
async def test_escape_at_root_clean_cancels() -> None:
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.outcome.submitted is False


@pytest.mark.asyncio
async def test_submit_with_invalid_tree_jumps_to_first_error() -> None:
    tree = build_form_tree(_RequiredLast)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.is_running
        assert isinstance(app.screen, ErrorsScreen)
        await pilot.press("escape")
        await pilot.pause()
        view = app.screen.query_one(FieldListView)
        rows = view._row_specs()
        assert rows[view.cursor].path == "api_key", (
            "after dismissing the errors screen the cursor must sit on "
            f"the first offending field, got {rows[view.cursor].path!r}"
        )


def test_run_app_returns_outcome(monkeypatch) -> None:
    from pydantic_studio.renderers.textual_ import app as app_mod

    def fake_run(self, **kwargs):
        self._outcome = EditOutcome(status="submitted")
        return None

    monkeypatch.setattr(StudioApp, "run", fake_run)
    tree = build_form_tree(_Schema)
    outcome = app_mod.run_app(tree)
    assert isinstance(outcome, EditOutcome)
    assert outcome.submitted is True


def test_studio_app_accepts_session_keyword() -> None:
    from pydantic_studio import EditSession

    tree = build_form_tree(_Schema)
    session = EditSession(tree=tree)
    app = StudioApp(session=session)
    assert app.session is session
    assert app.tree is tree


def test_studio_app_rejects_session_with_ignored_tree_arguments() -> None:
    from pydantic_studio import EditSession

    session = EditSession(tree=build_form_tree(_Schema))

    with pytest.raises(TypeError, match="session"):
        StudioApp(
            tree=build_form_tree(_Schema),
            readonly_paths={"name"},
            session=session,
        )
