"""Format-dispatch wrappers for load/save based on path extension."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pydantic import BaseModel

    from pydantic_studio.tree.nodes import FormTree


_Format = Literal["yaml", "toml", "json"]
_EXT_MAP: dict[str, _Format] = {
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
}


def _format_for_path(path: Path) -> _Format:
    ext = path.suffix.lower()
    fmt = _EXT_MAP.get(ext)
    if fmt is None:
        msg = (
            f"cannot infer format from extension {ext!r} on path {path}; "
            f"pass format= explicitly"
        )
        raise ValueError(msg)
    return fmt


def load_config(
    path: str | Path,
    schema: type[BaseModel],
    *,
    format: _Format | None = None,
) -> FormTree:
    """Load a config file into a FormTree, picking parser by extension.

    Args:
        path: file path
        schema: Pydantic BaseModel subclass
        format: optional explicit format override ("yaml"/"toml"/"json")
    """
    path = Path(path)
    fmt = format or _format_for_path(path)
    if fmt == "yaml":
        from pydantic_studio.io.yaml import load_yaml

        return load_yaml(path, schema)
    if fmt == "toml":
        from pydantic_studio.io.toml import load_toml

        return load_toml(path, schema)
    from pydantic_studio.io.json_ import load_json

    return load_json(path, schema)


def save_config(
    tree: FormTree,
    path: str | Path,
    *,
    format: _Format | None = None,
) -> None:
    """Save a FormTree to a config file, picking writer by extension."""
    path = Path(path)
    fmt = format or _format_for_path(path)
    if fmt == "yaml":
        from pydantic_studio.io.yaml import save_yaml

        save_yaml(tree, path)
        return
    if fmt == "toml":
        from pydantic_studio.io.toml import save_toml

        save_toml(tree, path)
        return
    from pydantic_studio.io.json_ import save_json

    save_json(tree, path)
