"""End-to-end save/quit tests for the TUI v2 ConfigScreen.

Drives Ctrl+S and Ctrl+C via the Pilot harness and asserts the file
system + notification side-effects. These tests pin the contract that
``FooterHints`` advertises on every screen render: ``Ctrl+S save | Ctrl+C
quit``.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree, load_yaml
from pydantic_studio.renderers.textual_ import StudioApp


class _Schema(BaseModel):
    name: str = "alpha"
    debug: bool = False


class _RequiredSchema(BaseModel):
    """Has a required str with no default — to_instance() fails until set."""

    api_key: str = Field(...)
    timeout: int = 30


def _hook_notifications(app: StudioApp) -> list[tuple[str, str]]:
    """Wrap ``app.notify`` so tests can assert on emitted notifications."""
    captured: list[tuple[str, str]] = []
    original = app.notify

    def tracked(message: str, *args, severity: str = "information", **kwargs):
        captured.append((message, severity))
        return original(message, *args, severity=severity, **kwargs)

    app.notify = tracked  # type: ignore[method-assign]
    return captured


@pytest.mark.asyncio
async def test_ctrl_s_writes_save_path(tmp_path):
    """With ``save_path`` configured and the tree valid, Ctrl+S persists."""
    save = tmp_path / "config.yaml"
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=save)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.pause()
    assert save.exists()
    reloaded = load_yaml(save, _Schema)
    assert reloaded.to_instance().name == "alpha"
    assert reloaded.to_instance().debug is False


@pytest.mark.asyncio
async def test_ctrl_s_without_save_path_submits_without_warning():
    """Ctrl+S with no ``save_path`` is a real submit, not a dead end.

    Pre-v0.2 this warned "No save path configured" — the natural save
    gesture did nothing in exactly the flow downstream CLIs use (they
    persist the tree themselves after the session ends).
    """
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    notifications = _hook_notifications(app)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert app.outcome.submitted is True
    severities = {sev for _, sev in notifications}
    assert "warning" not in severities, f"unexpected warning: {notifications}"


@pytest.mark.asyncio
async def test_ctrl_s_with_validation_failure_does_not_write(tmp_path):
    """When the tree is invalid (required field unset), Ctrl+S surfaces an
    error and the file is NOT written (no half-baked partial save).
    """
    save = tmp_path / "config.yaml"
    tree = build_form_tree(_RequiredSchema)
    app = StudioApp(tree=tree, save_path=save)
    notifications = _hook_notifications(app)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert not save.exists(), (
        "Save should not write when required fields are unset; got file with "
        f"content: {save.read_text(encoding='utf-8') if save.exists() else '<n/a>'}"
    )
    severities = {sev for _, sev in notifications}
    assert "error" in severities, (
        f"Expected an error notification for validation failure, got: {notifications}"
    )


@pytest.mark.asyncio
async def test_ctrl_s_with_save_failure_reports_save_error(tmp_path):
    """A write/format failure is a save error, not a validation error."""
    save = tmp_path / "config.ini"
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=save)
    notifications = _hook_notifications(app)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert not save.exists()
    error_messages = [message for message, severity in notifications if severity == "error"]
    assert any("save error" in message for message in error_messages), notifications
    assert not any("validation error" in message for message in error_messages), notifications


@pytest.mark.asyncio
async def test_footer_save_and_quit_promises_have_real_bindings():
    """Static cross-check that advertised Ctrl+S/Ctrl+C have real bindings."""
    tree = build_form_tree(_Schema)
    app = StudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()

        bound_keys: set[str] = set()
        nodes = [app, app.screen, *app.screen.walk_children()]
        for node in nodes:
            for binding in getattr(type(node), "BINDINGS", []):
                key = getattr(binding, "key", None) or (
                    binding[0] if isinstance(binding, tuple) else None
                )
                if key:
                    bound_keys.add(key.lower())

    assert "ctrl+s" in bound_keys, (
        f"'ctrl+s' missing from bindings: {sorted(bound_keys)}"
    )
    assert "ctrl+c" in bound_keys, (
        f"'ctrl+c' missing from bindings: {sorted(bound_keys)}"
    )


@pytest.mark.asyncio
async def test_ctrl_c_routes_to_quit_action():
    """Ctrl+C is the advertised quit shortcut."""

    class _TrackingStudioApp(StudioApp):
        quit_called = False

        async def action_quit(self) -> None:  # type: ignore[override]
            self.quit_called = True
            self.exit()

    tree = build_form_tree(_Schema)
    app = _TrackingStudioApp(tree=tree, save_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()

    assert app.quit_called is True


def test_studio_app_run_enables_mouse_by_default(monkeypatch):
    """Form mode is mouse-first: click rows, toggles, buttons. Copy-heavy
    workflows opt out via run(mouse=False) / Shift+drag selection."""
    captured: dict[str, object] = {}

    def fake_run(self, **kwargs):
        captured.update(kwargs)
        return None

    from textual.app import App

    monkeypatch.setattr(App, "run", fake_run)

    tree = build_form_tree(_Schema)
    StudioApp(tree=tree, save_path=None).run()

    assert captured["mouse"] is True
