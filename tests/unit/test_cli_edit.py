"""Tests for the `pydantic-studio edit` CLI subcommand.

Interactive renderers block under CliRunner, so these tests patch each
renderer's run function and verify routing plus tree/save-path setup.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pydantic_studio.cli import app

runner = CliRunner()


def test_edit_with_existing_file(tmp_path: Path, monkeypatch) -> None:
    """edit loads an existing YAML and launches the default console renderer."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("name: prod\nport: 9090\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_run(tree, save_path=None) -> None:
        captured["tree"] = tree
        captured["save_path"] = save_path

    import pydantic_studio.renderers.console as console_module

    monkeypatch.setattr(console_module, "run_console_app", fake_run)

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
    assert captured["save_path"] == cfg


def test_edit_without_file_builds_fresh_tree(tmp_path: Path, monkeypatch) -> None:
    """edit without a path argument launches with a fresh tree and default output."""
    captured: dict[str, object] = {}

    def fake_run(tree, save_path=None) -> None:
        captured["tree"] = tree
        captured["save_path"] = save_path

    import pydantic_studio.renderers.console as console_module

    monkeypatch.setattr(console_module, "run_console_app", fake_run)

    result = runner.invoke(app, ["edit", "tests.fixtures.schemas:Server"])
    assert result.exit_code == 0
    assert captured["save_path"] == Path("Server.yaml")
    tree = captured["tree"]
    port_node = tree.root.find("port")
    assert port_node is not None
    # A freshly-built tree should expose schema defaults as editable values.
    assert port_node.value == 8080
    assert port_node.default == 8080


def test_edit_new_file_with_unknown_extension_errors_before_renderer(
    tmp_path: Path, monkeypatch
) -> None:
    called = False
    cfg = tmp_path / "config.ini"

    def fake_run(tree, save_path=None) -> None:
        nonlocal called
        called = True

    import pydantic_studio.renderers.console as console_module

    monkeypatch.setattr(console_module, "run_console_app", fake_run)

    result = runner.invoke(
        app,
        ["edit", "tests.fixtures.schemas:Server", str(cfg)],
    )

    assert result.exit_code == 1
    assert "unsupported config file extension" in result.output
    assert called is False


def test_edit_console_failure_reports_clean_error(monkeypatch) -> None:
    def fake_run(tree, save_path=None) -> None:
        raise OSError("disk full")

    import pydantic_studio.renderers.console as console_module

    monkeypatch.setattr(console_module, "run_console_app", fake_run)

    result = runner.invoke(app, ["edit", "tests.fixtures.schemas:Server"])

    assert result.exit_code == 1
    assert "edit failed" in result.output.lower()
    assert "disk full" in result.output


def test_edit_console_cancel_exits_without_failure_message(monkeypatch) -> None:
    from pydantic_studio.exceptions import CancelledByUser

    def fake_run(tree, save_path=None) -> None:
        raise CancelledByUser()

    import pydantic_studio.renderers.console as console_module

    monkeypatch.setattr(console_module, "run_console_app", fake_run)

    result = runner.invoke(app, ["edit", "tests.fixtures.schemas:Server"])

    assert result.exit_code == 1
    assert not isinstance(result.exception, CancelledByUser)
    assert "edit failed" not in result.output.lower()


def test_edit_tui_frontend_routes_to_studio_app(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(self) -> None:
        captured["tree"] = self.tree
        captured["save_path"] = self.save_path

    from pydantic_studio.renderers.textual_ import StudioApp

    monkeypatch.setattr(StudioApp, "run", fake_run)

    result = runner.invoke(
        app,
        ["edit", "--frontend", "tui", "tests.fixtures.schemas:Server"],
    )

    assert result.exit_code == 0
    assert captured["save_path"] == Path("Server.yaml")
    assert captured["tree"].root.find("port").value == 8080


def test_edit_tui_cancelled_outcome_exits_without_failure_message(monkeypatch) -> None:
    from pydantic_studio.outcome import EditOutcome

    def fake_run(self) -> EditOutcome:
        return EditOutcome("cancelled")

    from pydantic_studio.renderers.textual_ import StudioApp

    monkeypatch.setattr(StudioApp, "run", fake_run)

    result = runner.invoke(
        app,
        ["edit", "--frontend", "tui", "tests.fixtures.schemas:Server"],
    )

    assert result.exit_code == 1
    assert "edit failed" not in result.output.lower()


def test_edit_unknown_schema_errors() -> None:
    result = runner.invoke(app, ["edit", "nosuch:Foo"])
    assert result.exit_code != 0


def test_edit_web_frontend(tmp_path, monkeypatch) -> None:
    """edit --frontend web routes to run_html_app."""
    captured: dict[str, object] = {}

    def fake_run(tree, save_path=None) -> None:
        captured["tree"] = tree
        captured["save_path"] = save_path

    import pydantic_studio.renderers.html as html_module

    monkeypatch.setattr(html_module, "run_html_app", fake_run)

    result = runner.invoke(
        app,
        ["edit", "--frontend", "web", "tests.fixtures.schemas:Server"],
    )
    assert result.exit_code == 0
    assert "tree" in captured


def test_edit_web_cancelled_outcome_exits_without_failure_message(monkeypatch) -> None:
    from pydantic_studio.outcome import EditOutcome

    def fake_run(tree, save_path=None) -> EditOutcome:
        return EditOutcome("cancelled")

    import pydantic_studio.renderers.html as html_module

    monkeypatch.setattr(html_module, "run_html_app", fake_run)

    result = runner.invoke(
        app,
        ["edit", "--frontend", "web", "tests.fixtures.schemas:Server"],
    )

    assert result.exit_code == 1
    assert "edit failed" not in result.output.lower()


def test_edit_unknown_frontend_errors() -> None:
    result = runner.invoke(
        app,
        ["edit", "--frontend", "vr", "tests.fixtures.schemas:Server"],
    )
    assert result.exit_code != 0


def test_edit_unknown_frontend_is_rejected_before_schema_import() -> None:
    result = runner.invoke(app, ["edit", "--frontend", "vr", "nosuch:Foo"])

    assert result.exit_code != 0
    assert "frontend" in result.output.lower()
    assert "nosuch" not in result.output.lower()


def test_edit_help_names_supported_file_formats() -> None:
    result = runner.invoke(app, ["edit", "--help"])

    assert result.exit_code == 0
    assert "YAML, TOML, or JSON" in result.output
