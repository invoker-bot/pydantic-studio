"""Tests for the `pydantic-studio` CLI."""

from __future__ import annotations

import json
import tomllib

from ruamel.yaml import YAML
from typer.testing import CliRunner

import pydantic_studio.cli as cli_module
from pydantic_studio.cli import app

runner = CliRunner()
yaml = YAML(typ="safe")


def test_cli_module_docstring_describes_current_command_surface() -> None:
    docstring = cli_module.__doc__ or ""

    for command in ("fill", "run", "check", "edit", "show", "version"):
        assert command in docstring
    assert "v0.0.3" not in docstring
    assert "Plan 4" not in docstring
    assert "only the ``show`` subcommand" not in docstring


class TestShow:
    def test_show_renders_simple_schema(self) -> None:
        result = runner.invoke(app, ["show", "tests.fixtures.schemas:Simple"])
        assert result.exit_code == 0
        # Field names must appear somewhere in the rich-rendered output.
        assert "name" in result.output
        assert "age" in result.output
        assert "balance" in result.output

    def test_show_renders_temporal_fields(self) -> None:
        result = runner.invoke(app, ["show", "tests.fixtures.schemas:Phase3Sink"])
        assert result.exit_code == 0
        assert "when" in result.output
        assert "datetime" in result.output  # node kind appears

    def test_show_unknown_module(self) -> None:
        result = runner.invoke(app, ["show", "nosuch.module:Foo"])
        assert result.exit_code != 0
        assert "could not import" in result.output.lower()

    def test_show_unknown_class(self) -> None:
        result = runner.invoke(app, ["show", "tests.fixtures.schemas:Nonexistent"])
        assert result.exit_code != 0
        assert "no such class" in result.output.lower()

    def test_show_not_a_basemodel(self) -> None:
        # Use the built-in `int` to trigger the "not a BaseModel" error path.
        result = runner.invoke(app, ["show", "builtins:int"])
        assert result.exit_code != 0
        assert "basemodel" in result.output.lower()

    def test_show_invalid_format(self) -> None:
        """Bare names without 'module:Class' are rejected."""
        result = runner.invoke(app, ["show", "no_colon_here"])
        assert result.exit_code != 0
        assert "module:class" in result.output.lower()


class TestVersion:
    def test_version_subcommand_prints_version(self) -> None:
        from pydantic_studio import __version__

        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestFill:
    def test_fill_emits_stub_to_stdout(self) -> None:
        result = runner.invoke(app, ["fill", "tests.fixtures.schemas:Server"])
        assert result.exit_code == 0
        # Schema fields appear in the stdout YAML.
        assert "name:" in result.output
        assert "port:" in result.output
        # Description comments appear.
        assert "Service identifier" in result.output

    def test_fill_emits_required_placeholders_to_stdout(self) -> None:
        result = runner.invoke(app, ["fill", "tests.fixtures.schemas:Simple"])
        assert result.exit_code == 0
        assert "name: '?'" in result.output
        assert "# The thing's name" in result.output
        assert yaml.load(result.output)["name"] == "?"

    def test_fill_writes_to_out_file(self, tmp_path) -> None:
        out = tmp_path / "config.yaml"
        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Server", "--out", str(out)],
        )
        assert result.exit_code == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "name:" in content
        assert "Listening port" in content

    def test_fill_writes_required_placeholders_to_yaml_file(self, tmp_path) -> None:
        out = tmp_path / "config.yaml"
        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Simple", "--out", str(out)],
        )

        assert result.exit_code == 0
        content = out.read_text(encoding="utf-8")
        assert "name: '?'" in content
        assert yaml.load(content)["name"] == "?"

    def test_fill_unknown_schema_errors(self) -> None:
        result = runner.invoke(app, ["fill", "nosuch:Foo"])
        assert result.exit_code != 0


class TestRun:
    def test_run_prints_validated_model(self, tmp_path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "name: prod\n"
            "port: 8080\n"
            "debug: true\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["run", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code == 0
        # The model dump appears in stdout.
        assert "name='prod'" in result.output or "name: prod" in result.output
        assert "8080" in result.output
        assert "debug=True" in result.output or "debug: true" in result.output.lower()

    def test_run_validation_failure_exits_nonzero(self, tmp_path) -> None:
        cfg = tmp_path / "bad.yaml"
        cfg.write_text(
            "name: prod\n"
            "port: 99999\n"  # exceeds Server.port's le=65535
            "debug: false\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["run", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code != 0
        # Useful: surface the field that failed.
        assert "port" in result.output.lower()


class TestCheck:
    def test_check_silent_on_valid(self, tmp_path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "name: prod\n"
            "port: 8080\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["check", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code == 0
        # Output should be brief — just an OK marker, not the full model.
        # The exact text is up to the implementation; verify it's short.
        assert len(result.output) < 200

    def test_check_invalid_exits_nonzero(self, tmp_path) -> None:
        cfg = tmp_path / "bad.yaml"
        cfg.write_text(
            "name: prod\n"
            "port: -5\n",  # below Server.port's ge=1
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["check", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code != 0


class TestFillFormats:
    def test_fill_emits_toml(self, tmp_path) -> None:
        out = tmp_path / "out.toml"
        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Server", "--out", str(out)],
        )
        assert result.exit_code == 0
        content = out.read_text(encoding="utf-8")
        assert "name =" in content or 'name = "prod"' in content

    def test_fill_toml_writes_required_placeholders(self, tmp_path) -> None:
        out = tmp_path / "out.toml"
        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Simple", "--out", str(out)],
        )

        assert result.exit_code == 0
        data = tomllib.loads(out.read_text(encoding="utf-8"))
        assert data["name"] == "?"

    def test_fill_emits_json(self, tmp_path) -> None:
        out = tmp_path / "out.json"
        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Server", "--out", str(out)],
        )
        assert result.exit_code == 0
        content = out.read_text(encoding="utf-8")
        assert content.lstrip().startswith("{")
        assert '"name"' in content

    def test_fill_json_writes_required_placeholders(self, tmp_path) -> None:
        out = tmp_path / "out.json"
        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Simple", "--out", str(out)],
        )

        assert result.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["name"] == "?"


class TestRunFormats:
    def test_run_loads_toml(self, tmp_path) -> None:
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            'name = "prod"\nport = 8080\ndebug = true\n',
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["run", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code == 0
        assert "prod" in result.output

    def test_run_loads_json(self, tmp_path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(
            '{"name": "prod", "port": 8080, "debug": true}\n',
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["run", "tests.fixtures.schemas:Server", str(cfg)],
        )
        assert result.exit_code == 0
        assert "prod" in result.output
