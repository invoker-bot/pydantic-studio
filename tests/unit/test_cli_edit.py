"""Tests for the `pydantic-studio edit` CLI subcommand.

Note: edit launches a Textual TUI which can't be driven through CliRunner
the same way as `fill`/`run`/`check` (it blocks on App.run()). Instead we
patch the StudioApp.run() to be a no-op and verify the load/build flow
worked correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from pydantic_studio.cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


def test_edit_with_existing_file(tmp_path: Path, monkeypatch) -> None:
    """edit loads an existing YAML and launches the app."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("name: prod\nport: 9090\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_run(self) -> None:
        captured["tree"] = self.tree
        captured["save_path"] = self.save_path

    from pydantic_studio.renderers.textual_ import StudioApp

    monkeypatch.setattr(StudioApp, "run", fake_run)

    result = runner.invoke(
        app,
        ["edit", "tests.fixtures.schemas:Server", str(cfg)],
    )
    assert result.exit_code == 0
    tree = captured["tree"]
    assert tree is not None
    # The loaded port is 9090, not the default 8080.
    port_node = tree.root.find("port")
    assert port_node is not None
    assert port_node.value == 9090


def test_edit_without_file_builds_fresh_tree(tmp_path: Path, monkeypatch) -> None:
    """edit without a path argument launches with a fresh tree (defaults)."""
    captured: dict[str, object] = {}

    def fake_run(self) -> None:
        captured["tree"] = self.tree
        captured["save_path"] = self.save_path

    from pydantic_studio.renderers.textual_ import StudioApp

    monkeypatch.setattr(StudioApp, "run", fake_run)

    result = runner.invoke(app, ["edit", "tests.fixtures.schemas:Server"])
    assert result.exit_code == 0
    assert captured["save_path"] is None
    tree = captured["tree"]
    port_node = tree.root.find("port")
    assert port_node is not None
    # A freshly-built tree carries the schema default on the node; the
    # ``value`` attribute is filled in lazily by the editor widgets when
    # they mount (see scalars.TextInputEditor.on_mount).
    assert port_node.default == 8080


def test_edit_unknown_schema_errors() -> None:
    result = runner.invoke(app, ["edit", "nosuch:Foo"])
    assert result.exit_code != 0
