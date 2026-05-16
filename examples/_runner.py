"""Shared launcher for the example schemas.

Each example imports ``run_demo`` and calls it with the schema class plus
any seed data. The launcher parses ``sys.argv`` for one of ``console``,
``tui``, ``web``, ``show``, or ``fill`` (default: ``console``) and dispatches.

Keeping this in one place means every example file is just *schema +
data* — no argparse boilerplate.
"""

from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING, Any

from pydantic_studio import build_form_tree

if TYPE_CHECKING:
    from pydantic import BaseModel

_USAGE = "usage: python examples/<file>.py [console|tui|web|show|fill]"


def _show(schema: type[BaseModel], existing: dict[str, Any] | None) -> None:
    from rich.console import Console
    from rich.tree import Tree

    from pydantic_studio.cli import _walk

    tree = build_form_tree(schema, existing=existing or None)
    console = Console()
    root = Tree(f"[bold green]{schema.__module__}.{schema.__name__}[/bold green]")
    for child in tree.root.fields:
        _walk(child, root)
    console.print(root)


def _fill(schema: type[BaseModel], existing: dict[str, Any] | None) -> None:
    from pydantic_studio.io.yaml import _build_commented_map, _yaml

    tree = build_form_tree(schema, existing=existing or None)
    instance = tree.to_instance()
    cm = _build_commented_map(instance.model_dump(mode="json"), schema, None)
    buf = io.StringIO()
    _yaml().dump(cm, buf)
    sys.stdout.write(buf.getvalue())


def _console(schema: type[BaseModel], existing: dict[str, Any] | None) -> None:
    from pathlib import Path

    from pydantic_studio import run_console_app

    tree = build_form_tree(schema, existing=existing or None)
    run_console_app(tree, Path(f"{schema.__name__}.yaml"))


def _tui(schema: type[BaseModel], existing: dict[str, Any] | None) -> None:
    from pydantic_studio import run_app

    tree = build_form_tree(schema, existing=existing or None)
    run_app(tree)


def _web(schema: type[BaseModel], existing: dict[str, Any] | None) -> None:
    from pydantic_studio import run_html_app

    tree = build_form_tree(schema, existing=existing or None)
    run_html_app(tree)


def run_demo(
    schema: type[BaseModel],
    existing: dict[str, Any] | None = None,
) -> None:
    """Entry point each example calls from its ``__main__`` block."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "console"
    dispatch = {
        "console": _console,
        "tui": _tui,
        "web": _web,
        "show": _show,
        "fill": _fill,
    }
    handler = dispatch.get(mode)
    if handler is None:
        sys.stderr.write(f"{_USAGE}\nunknown mode: {mode!r}\n")
        sys.exit(2)
    handler(schema, existing)
