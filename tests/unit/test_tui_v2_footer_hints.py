"""Unit tests for the TUI v2 FooterHints widget."""

from __future__ import annotations

import pytest
from textual.app import App

from pydantic_studio.renderers.textual_.widgets.footer_hints import FooterHints


class _Host(App):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self._mode = mode

    def compose(self):
        yield FooterHints(mode=self._mode)


@pytest.mark.asyncio
async def test_footer_idle_mode_shows_navigation() -> None:
    app = _Host("idle")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "navigate" in fh.line1
        assert "Enter" in fh.line1
        assert "Esc" in fh.line1
        assert "Ctrl+S" in fh.line1
        assert "Ctrl+C" in fh.line1


@pytest.mark.asyncio
async def test_footer_editing_mode_shows_edit_keys() -> None:
    app = _Host("editing")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "Enter" in fh.line1
        assert "commit" in fh.line1
        assert "cancel" in fh.line1
        assert "Ctrl+C" in fh.line1


@pytest.mark.asyncio
async def test_footer_sequence_mode_shows_delete() -> None:
    app = _Host("sequence")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "D" in fh.line1
        assert "delete" in fh.line1


@pytest.mark.asyncio
async def test_footer_mapping_mode_shows_rename() -> None:
    app = _Host("mapping")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "R" in fh.line1
        assert "rename" in fh.line1
        assert "D" in fh.line1


@pytest.mark.asyncio
async def test_footer_errors_mode_shows_jump() -> None:
    app = _Host("errors")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        assert "Esc" in fh.line1
        assert "Enter" in fh.line1


@pytest.mark.asyncio
async def test_footer_unknown_mode_falls_back_to_idle() -> None:
    app = _Host("nonexistent-mode")
    async with app.run_test() as pilot:
        await pilot.pause()
        fh = app.screen.query_one(FooterHints)
        # Idle text on unknown modes — safe default, never crash.
        assert "navigate" in fh.line1
