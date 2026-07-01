"""Tests for the `pydantic-studio` CLI."""

from __future__ import annotations

import json
import tomllib
from typing import Any

from pydantic import BaseModel
from ruamel.yaml import YAML
from typer.testing import CliRunner

import pydantic_studio.cli as cli_module
from pydantic_studio.cli import app

runner = CliRunner()
yaml = YAML(typ="safe")


class NonFiniteFloatSchema(BaseModel):
    value: float = float("nan")


class NonFiniteAnySchema(BaseModel):
    value: Any = float("nan")


class RequiredAnySchema(BaseModel):
    value: Any


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

    def test_fill_unknown_output_extension_reports_file_path(self, tmp_path) -> None:
        out = tmp_path / "config.ini"

        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Server", "--out", str(out)],
        )

        assert result.exit_code == 1
        assert "could not write" in result.output.lower()
        assert "config.ini" in result.output

    def test_fill_output_extension_is_rejected_before_schema_import(self, tmp_path) -> None:
        out = tmp_path / "config.ini"

        result = runner.invoke(app, ["fill", "nosuch:Foo", "--out", str(out)])

        assert result.exit_code == 1
        assert "could not write" in result.output.lower()
        assert "config.ini" in result.output
        assert "nosuch" not in result.output.lower()

    def test_fill_output_directory_reports_file_path(self, tmp_path) -> None:
        out = tmp_path / "config.yaml"
        out.mkdir()

        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:Server", "--out", str(out)],
        )

        assert result.exit_code == 1
        assert "could not write" in result.output.lower()
        assert "config.yaml" in result.output


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

    def test_run_load_failure_reports_file_path(self, tmp_path) -> None:
        cfg = tmp_path / "bad.yaml"
        cfg.write_text("name: [unterminated\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["run", "tests.fixtures.schemas:Server", str(cfg)],
        )

        assert result.exit_code == 1
        assert "could not load" in result.output.lower()
        assert "bad.yaml" in result.output

    def test_run_input_extension_is_rejected_before_schema_import(self, tmp_path) -> None:
        cfg = tmp_path / "config.ini"

        result = runner.invoke(app, ["run", "nosuch:Foo", str(cfg)])

        assert result.exit_code == 1
        assert "could not load" in result.output.lower()
        assert "config.ini" in result.output
        assert "nosuch" not in result.output.lower()

    def test_run_input_extension_preflight_follows_dispatch_map(
        self, tmp_path, monkeypatch
    ) -> None:
        from pydantic_studio.io import dispatch as dispatch_module

        monkeypatch.setitem(dispatch_module._EXT_MAP, ".cfg", "yaml")
        cfg = tmp_path / "config.cfg"

        result = runner.invoke(app, ["run", "nosuch:Foo", str(cfg)])

        assert result.exit_code == 2
        assert "could not import module 'nosuch'" in result.output.lower()


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

    def test_check_missing_file_reports_file_path(self, tmp_path) -> None:
        cfg = tmp_path / "missing.yaml"

        result = runner.invoke(
            app,
            ["check", "tests.fixtures.schemas:Server", str(cfg)],
        )

        assert result.exit_code == 1
        assert "could not load" in result.output.lower()
        assert "missing.yaml" in result.output

    def test_check_input_extension_is_rejected_before_schema_import(self, tmp_path) -> None:
        cfg = tmp_path / "config.ini"

        result = runner.invoke(app, ["check", "nosuch:Foo", str(cfg)])

        assert result.exit_code == 1
        assert "could not load" in result.output.lower()
        assert "config.ini" in result.output
        assert "nosuch" not in result.output.lower()


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

    def test_fill_toml_omits_optional_none_values(self, tmp_path) -> None:
        out = tmp_path / "out.toml"
        result = runner.invoke(
            app,
            ["fill", "tests.fixtures.schemas:WithOptional", "--out", str(out)],
        )

        assert result.exit_code == 0
        content = out.read_text(encoding="utf-8")
        assert "nickname" not in content
        assert "age" not in content
        assert tomllib.loads(content) == {}

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

    def test_fill_json_writes_required_any_placeholders(self, tmp_path) -> None:
        out = tmp_path / "out.json"
        result = runner.invoke(
            app,
            ["fill", "tests.unit.test_cli:RequiredAnySchema", "--out", str(out)],
        )

        assert result.exit_code == 0
        assert json.loads(out.read_text(encoding="utf-8")) == {"value": "?"}

    def test_fill_yaml_writes_required_any_placeholders(self, tmp_path) -> None:
        out = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            ["fill", "tests.unit.test_cli:RequiredAnySchema", "--out", str(out)],
        )

        assert result.exit_code == 0
        assert yaml.load(out.read_text(encoding="utf-8")) == {"value": "?"}

    def test_fill_toml_writes_required_any_placeholders(self, tmp_path) -> None:
        out = tmp_path / "out.toml"
        result = runner.invoke(
            app,
            ["fill", "tests.unit.test_cli:RequiredAnySchema", "--out", str(out)],
        )

        assert result.exit_code == 0
        assert tomllib.loads(out.read_text(encoding="utf-8")) == {"value": "?"}

    def test_fill_json_rejects_non_finite_defaults(self, tmp_path) -> None:
        out = tmp_path / "out.json"
        result = runner.invoke(
            app,
            ["fill", "tests.unit.test_cli:NonFiniteFloatSchema", "--out", str(out)],
        )

        assert result.exit_code == 1
        assert "could not write" in result.output.lower()
        assert "JSON compliant" in result.output
        assert not out.exists()

    def test_fill_json_serializes_non_finite_any_default_as_text(self, tmp_path) -> None:
        out = tmp_path / "out.json"
        result = runner.invoke(
            app,
            ["fill", "tests.unit.test_cli:NonFiniteAnySchema", "--out", str(out)],
        )

        assert result.exit_code == 0
        assert json.loads(out.read_text(encoding="utf-8")) == {"value": "nan"}

    def test_fill_yaml_serializes_non_finite_any_default_as_text(self, tmp_path) -> None:
        out = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            ["fill", "tests.unit.test_cli:NonFiniteAnySchema", "--out", str(out)],
        )

        assert result.exit_code == 0
        assert yaml.load(out.read_text(encoding="utf-8")) == {"value": "nan"}

    def test_fill_toml_serializes_non_finite_any_default_as_text(self, tmp_path) -> None:
        out = tmp_path / "out.toml"
        result = runner.invoke(
            app,
            ["fill", "tests.unit.test_cli:NonFiniteAnySchema", "--out", str(out)],
        )

        assert result.exit_code == 0
        assert tomllib.loads(out.read_text(encoding="utf-8")) == {"value": "nan"}


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
