"""Tests for the minimal `pydantic-studio show` CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from pydantic_studio.cli import app

runner = CliRunner()


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
