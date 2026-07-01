"""Typer CLI for pydantic-studio.

The command surface covers schema introspection (``show``), version reporting
(``version``), config stub generation (``fill``), validation (``check`` and
``run``), and interactive editing (``edit``).
"""

from __future__ import annotations

import importlib
import io
import json
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import typer
from pydantic import BaseModel, TypeAdapter
from rich.console import Console
from rich.tree import Tree

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import (
    AnyValueNode,
    GroupNode,
    MappingNode,
    SequenceNode,
    UnionNode,
    _json_safe_any_value,
)

_JSON_VALUE_ADAPTER = TypeAdapter(object)


def _supported_extensions_help() -> str:
    from pydantic_studio.io.dispatch import supported_extensions

    return ", ".join(supported_extensions())


_CONFIG_EXTENSIONS_HELP = _supported_extensions_help()

app = typer.Typer(
    name="pydantic-studio",
    help="Interactive editor for Pydantic models. Run `pydantic-studio show` "
    "to introspect a schema's form-tree shape.",
    no_args_is_help=True,
)


def _load_schema(target: str) -> type[BaseModel]:
    """Resolve ``module:Class`` → BaseModel subclass.

    Raises typer.Exit with a friendly diagnostic on any failure.
    """
    if ":" not in target:
        typer.echo(
            f"Invalid target {target!r}: expected 'module:Class' format.",
        )
        raise typer.Exit(code=2)
    module_name, class_name = target.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        typer.echo(
            f"Could not import module {module_name!r}: {e}",
        )
        raise typer.Exit(code=2) from e
    cls = getattr(module, class_name, None)
    if cls is None:
        typer.echo(
            f"No such class {class_name!r} in module {module_name!r}.",
        )
        raise typer.Exit(code=2)
    if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
        typer.echo(
            f"{target!r} is not a Pydantic BaseModel subclass.",
        )
        raise typer.Exit(code=2)
    return cls


def _node_label(node: Any) -> str:
    """Compact one-line label for a node in the rich-rendered tree."""
    name = node.name or "?"
    kind = node.kind
    extra = ""
    value = getattr(node, "value", None)
    if value is not None:
        extra = f" = {value!r}"
        if len(extra) > 60:
            extra = extra[:57] + "...'"
    required = "" if node.required else " (optional)"
    return f"[bold]{name}[/bold] [dim]:: {kind}[/dim]{required}{extra}"


def _walk(node: Any, parent: Tree) -> None:
    """Recursively render a FormNode subtree under ``parent``."""
    branch = parent.add(_node_label(node))
    if isinstance(node, GroupNode):
        for child in node.fields:
            _walk(child, branch)
    elif isinstance(node, SequenceNode):
        for item in node.items:
            _walk(item, branch)
    elif isinstance(node, MappingNode):
        for k_node, v_node in node.entries:
            # MappingNode keys are always primitive nodes (StringNode/IntNode/etc.),
            # which all have a `.value` attribute. The discriminated union doesn't
            # narrow here, so suppress pyright with a getattr fallback.
            key_repr = repr(getattr(k_node, "value", k_node.name))
            entry_branch = branch.add(f"[cyan]entry[/cyan] :: {key_repr}")
            _walk(v_node, entry_branch)
    elif isinstance(node, UnionNode):
        if node.selected is not None:
            sel = branch.add(f"[magenta]selected[/magenta] (variant {node.selected_index})")
            _walk(node.selected, sel)
        else:
            branch.add("[dim]<no variant selected>[/dim]")
    # Leaf nodes have no children — _node_label already shows the value.


def _json_ready(value: Any) -> Any:
    """Convert node values to the JSON-friendly shape used by config writers."""
    _reject_non_finite_json_values(value)
    return _JSON_VALUE_ADAPTER.dump_python(value, mode="json", warnings=False)


def _reject_non_finite_json_values(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        msg = f"non-finite value {value!r} is not JSON compliant"
        raise ValueError(msg)
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_non_finite_json_values(item)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            _reject_non_finite_json_values(item)


def _stub_value(node: Any) -> Any:
    """Return a config-stub value, preserving defaults and marking missing required leaves."""
    if isinstance(node, GroupNode):
        if node.omitted and not node.required:
            return None
        return {child.name: _stub_value(child) for child in node.fields}
    if isinstance(node, SequenceNode):
        return [_stub_value(item) for item in node.items]
    if isinstance(node, MappingNode):
        return {_stub_value(key): _stub_value(value) for key, value in node.entries}
    if isinstance(node, UnionNode):
        if node.selected is not None:
            return _stub_value(node.selected)
        return "?" if node.required else None
    if getattr(node, "required", False) and hasattr(node, "value") and node.value is None:
        return "?"
    if isinstance(node, AnyValueNode):
        return _json_safe_any_value(node.to_python())
    return _json_ready(node.to_python())


def _fill_stub_data(tree: Any) -> dict[str, Any]:
    """Build root stub data without requiring a complete valid model instance."""
    data = _stub_value(tree.root)
    if not isinstance(data, dict):
        msg = f"expected root stub to be a dict, got {type(data).__name__}"
        raise ValueError(msg)
    return data


def _fill_yaml_payload(tree: Any) -> str:
    """Render a YAML config stub without requiring a complete valid instance."""
    from pydantic_studio.io.yaml import _build_commented_map, _yaml

    schema_class = tree.schema_class
    if schema_class is None:
        msg = "FormTree.schema_class is None; cannot render YAML"
        raise ValueError(msg)
    cm = _build_commented_map(_fill_stub_data(tree), schema_class, None)
    buf = io.StringIO()
    _yaml().dump(cm, buf)
    return buf.getvalue()


def _fill_toml_payload(tree: Any) -> str:
    """Render a TOML config stub without requiring a complete valid instance."""
    import tomlkit

    from pydantic_studio.io.toml import _build_document

    schema_class = tree.schema_class
    if schema_class is None:
        msg = "FormTree.schema_class is None; cannot render TOML"
        raise ValueError(msg)
    return tomlkit.dumps(_build_document(_fill_stub_data(tree), schema_class))


def _fill_json_payload(tree: Any) -> str:
    """Render a JSON config stub without requiring a complete valid instance."""
    return json.dumps(_fill_stub_data(tree), indent=2, allow_nan=False)


def _fill_payload_for_path(tree: Any, path: Path) -> str | None:
    from pydantic_studio.io.dispatch import format_for_path

    format_ = format_for_path(path)
    if format_ == "yaml":
        return _fill_yaml_payload(tree)
    if format_ == "toml":
        return _fill_toml_payload(tree)
    if format_ == "json":
        return _fill_json_payload(tree)
    return None


def _write_text_atomic(path: Path, payload: str) -> None:
    """Write text through a same-directory temp file, then atomically replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-fill-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _load_config_for_cli(file: Path, schema: type[BaseModel]) -> Any:
    """Load a config file for CLI commands, reporting parse/I/O errors cleanly."""
    from ruamel.yaml import YAMLError

    from pydantic_studio.io.dispatch import load_config

    try:
        return load_config(file, schema)
    except (OSError, ValueError, YAMLError) as e:
        typer.secho(f"{file}: could not load: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e


def _write_fill_output_for_cli(tree: Any, out: Path) -> None:
    """Write ``fill --out`` output, reporting format/I/O errors cleanly."""
    from pydantic_studio.io.dispatch import save_config

    try:
        payload = _fill_payload_for_path(tree, out)
        if payload is not None:
            _write_text_atomic(out, payload)
        else:
            save_config(tree, out)
    except (OSError, ValueError) as e:
        typer.secho(f"{out}: could not write: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e


def _validate_config_file_extension_for_cli(path: Path) -> None:
    from pydantic_studio.io.dispatch import supported_extensions

    supported = set(supported_extensions())
    suffix = path.suffix.lower()
    if suffix not in supported:
        expected = ", ".join(supported_extensions())
        msg = (
            f"unsupported config file extension {suffix!r} for {path}; "
            f"expected one of {expected}"
        )
        raise ValueError(msg)


def _validate_edit_save_path_or_exit(path: Path) -> None:
    try:
        _validate_config_file_extension_for_cli(path)
    except ValueError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e


def _validate_fill_output_path_or_exit(path: Path) -> None:
    try:
        _validate_config_file_extension_for_cli(path)
    except ValueError as e:
        typer.secho(f"fill failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e


def _validate_config_input_path_or_exit(path: Path) -> None:
    try:
        _validate_config_file_extension_for_cli(path)
    except ValueError as e:
        typer.secho(f"{path}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e


def _exit_if_cancelled_outcome(outcome: object) -> None:
    from pydantic_studio.outcome import EditOutcome

    if isinstance(outcome, EditOutcome) and outcome.cancelled:
        raise typer.Exit(code=1)


@app.command()
def show(target: str) -> None:
    """Introspect a Pydantic schema and print its form-tree shape.

    TARGET is of the form ``module.path:ClassName``, e.g.
    ``mypkg.config:AppSettings``.
    """
    schema = _load_schema(target)
    tree = build_form_tree(schema)
    console = Console()
    root = Tree(f"[bold green]{schema.__module__}.{schema.__name__}[/bold green]")
    for child in tree.root.fields:
        _walk(child, root)
    console.print(root)


@app.command()
def version() -> None:
    """Show the pydantic-studio version and exit."""
    from pydantic_studio import __version__

    typer.echo(f"pydantic-studio {__version__}")


@app.command()
def fill(
    target: str = typer.Argument(..., help="module:Class identifier."),
    out: Path | None = typer.Option(  # noqa: B008
        None,
        "--out",
        "-o",
        help=(
            f"Path to write the stub. Format inferred from extension "
            f"({_CONFIG_EXTENSIONS_HELP}). "
            "If omitted, writes YAML to stdout."
        ),
    ),
) -> None:
    """Emit a config stub populated with the schema's defaults."""
    if out is not None:
        _validate_fill_output_path_or_exit(out)
    schema = _load_schema(target)
    tree = build_form_tree(schema)
    if out is not None:
        _write_fill_output_for_cli(tree, out)
        typer.echo(f"Wrote {out}")
        return
    typer.echo(_fill_yaml_payload(tree), nl=False)


@app.command()
def run(
    target: str = typer.Argument(..., help="module:Class identifier."),
    file: Path = typer.Argument(  # noqa: B008
        ...,
        help=f"Path to a config file; extension picks format ({_CONFIG_EXTENSIONS_HELP}).",
    ),
) -> None:
    """Load a config file, validate against the schema, print the model dump."""
    from pydantic import ValidationError

    from pydantic_studio.exceptions import ValidationFailedError

    _validate_config_input_path_or_exit(file)
    schema = _load_schema(target)
    tree = _load_config_for_cli(file, schema)
    try:
        instance = tree.to_instance()
    except (ValidationError, ValidationFailedError) as e:
        typer.secho(f"Validation failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    typer.echo(repr(instance))


@app.command()
def check(
    target: str = typer.Argument(..., help="module:Class identifier."),
    file: Path = typer.Argument(  # noqa: B008
        ...,
        help=f"Path to a config file; extension picks format ({_CONFIG_EXTENSIONS_HELP}).",
    ),
) -> None:
    """Load + validate. Silent on success."""
    from pydantic import ValidationError

    from pydantic_studio.exceptions import ValidationFailedError

    _validate_config_input_path_or_exit(file)
    schema = _load_schema(target)
    tree = _load_config_for_cli(file, schema)
    try:
        tree.to_instance()
    except (ValidationError, ValidationFailedError) as e:
        typer.secho(f"{file}: validation failed", fg=typer.colors.RED, err=True)
        for line in str(e).splitlines():
            typer.echo(f"  {line}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo(f"{file}: OK")


@app.command()
def edit(
    target: str = typer.Argument(..., help="module:Class identifier."),
    file: Path | None = typer.Argument(  # noqa: B008
        None,
        help=(
            f"Path to a config file ({_CONFIG_EXTENSIONS_HELP}). If omitted, edits a fresh "
            "tree and saves to <Class>.yaml."
        ),
    ),
    frontend: Literal["console", "tui", "web"] = typer.Option(
        "console",
        "--frontend",
        "-f",
        help="UI to launch: 'console', 'tui' (Textual), or 'web' (FastAPI + React).",
    ),
) -> None:
    """Launch an editor for a Pydantic schema."""
    from pydantic_studio import build_form_tree
    from pydantic_studio.exceptions import CancelledByUser, ValidationFailedError

    if file is not None:
        _validate_edit_save_path_or_exit(file)
    schema = _load_schema(target)
    save_path = file if file is not None else Path(f"{schema.__name__}.yaml")
    if file is None:
        _validate_edit_save_path_or_exit(save_path)

    if file is not None and file.exists():
        tree = _load_config_for_cli(file, schema)
    else:
        tree = build_form_tree(schema)

    try:
        if frontend == "console":
            from pydantic_studio.renderers.console import run_console_app

            outcome = run_console_app(tree=tree, save_path=save_path)
        elif frontend == "tui":
            from pydantic_studio.renderers.textual_ import StudioApp

            outcome = StudioApp(tree=tree, save_path=save_path).run()
        elif frontend == "web":
            from pydantic_studio.renderers import html as html_module

            outcome = html_module.run_html_app(tree=tree, save_path=save_path)
        else:
            typer.secho(
                f"Unknown frontend {frontend!r}. Use 'console', 'tui', or 'web'.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)
        _exit_if_cancelled_outcome(outcome)
    except CancelledByUser as e:
        raise typer.Exit(code=1) from e
    except ValidationFailedError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except (OSError, ValueError) as e:
        typer.secho(f"edit failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
