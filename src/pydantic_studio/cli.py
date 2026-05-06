"""Minimal CLI for pydantic-studio.

v0.0.3 ships only the ``show`` subcommand — schema introspection without
any I/O dependencies. ``edit`` / ``check`` / ``render`` join in Plan 4
once YAML round-trip support lands.
"""

from __future__ import annotations

import importlib
from pathlib import Path  # noqa: TC003 — typer reads at runtime
from typing import Any

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.tree import Tree

from pydantic_studio import build_form_tree
from pydantic_studio.tree.nodes import (
    GroupNode,
    MappingNode,
    SequenceNode,
    UnionNode,
)

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
    target: str = typer.Argument(
        ..., help="module:Class identifier of the Pydantic schema."
    ),
    out: Path | None = typer.Option(  # noqa: B008
        None,
        "--out",
        "-o",
        help="Path to write the YAML stub. If omitted, write to stdout.",
    ),
) -> None:
    """Emit a YAML stub populated with the schema's defaults.

    With ``--out FILE``, writes to that path with description comments.
    Without ``--out``, writes to stdout.
    """
    import io

    from pydantic_studio import build_form_tree, save_yaml

    schema = _load_schema(target)
    tree = build_form_tree(schema)
    if out is not None:
        save_yaml(tree, out)
        typer.echo(f"Wrote {out}")
        return
    # Stdout path: write to a temp file then echo its contents (avoids
    # duplicating save_yaml's CommentedMap-building logic). Use io.StringIO
    # via the YAML object directly.
    from pydantic_studio.io.yaml import _build_commented_map, _yaml

    schema_class = tree.schema_class
    if schema_class is None:
        typer.secho(
            "FormTree.schema_class is None — cannot render YAML",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    # Materialize to instance to resolve defaults (matches save_yaml semantics).
    instance = tree.to_instance()
    data = instance.model_dump(mode="python")
    cm = _build_commented_map(data, schema_class, None)
    buf = io.StringIO()
    _yaml().dump(cm, buf)
    typer.echo(buf.getvalue(), nl=False)


@app.command()
def run(
    target: str = typer.Argument(..., help="module:Class identifier."),
    file: Path = typer.Argument(..., help="Path to a YAML config file."),  # noqa: B008
) -> None:
    """Load a YAML file, validate against the schema, print the model dump."""
    from pydantic import ValidationError

    from pydantic_studio import load_yaml
    from pydantic_studio.exceptions import ValidationFailedError

    schema = _load_schema(target)
    try:
        tree = load_yaml(file, schema)
        instance = tree.to_instance()
    except (ValidationError, ValidationFailedError) as e:
        typer.secho(f"Validation failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    typer.echo(repr(instance))


@app.command()
def check(
    target: str = typer.Argument(..., help="module:Class identifier."),
    file: Path = typer.Argument(..., help="Path to a YAML config file."),  # noqa: B008
) -> None:
    """Load a YAML file and validate it against the schema. Silent on success."""
    from pydantic import ValidationError

    from pydantic_studio import load_yaml
    from pydantic_studio.exceptions import ValidationFailedError

    schema = _load_schema(target)
    try:
        tree = load_yaml(file, schema)
        tree.to_instance()
    except (ValidationError, ValidationFailedError) as e:
        typer.secho(f"{file}: validation failed", fg=typer.colors.RED, err=True)
        for line in str(e).splitlines():
            typer.echo(f"  {line}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo(f"{file}: OK")
