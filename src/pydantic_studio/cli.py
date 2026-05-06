"""Minimal CLI for pydantic-studio.

v0.0.3 ships only the ``show`` subcommand — schema introspection without
any I/O dependencies. ``edit`` / ``check`` / ``render`` join in Plan 4
once YAML round-trip support lands.
"""

from __future__ import annotations

import importlib
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
            entry_branch = branch.add(f"[cyan]entry[/cyan] :: {k_node.value!r}")
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
