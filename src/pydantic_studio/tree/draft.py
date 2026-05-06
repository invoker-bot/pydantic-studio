"""Draft persistence + recovery utilities.

Draft format: tree.model_dump_json() (full FormTree state). Recovery
loads via FormTree.model_validate_json + a context dict re-binding the
schema_class.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel

    from pydantic_studio.tree.nodes import FormTree

DRAFT_FILENAME = ".pydantic-studio.draft.json"


def save_draft(tree: FormTree, path: str | Path) -> None:
    """Save the full FormTree state as JSON to ``path``.

    Atomic via temp file + rename. Excludes schema_class (re-bound on load).
    """
    import os
    import tempfile

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = tree.model_dump_json(exclude={"schema_class"}).encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=".tmp-draft-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_draft(path: str | Path, schema: type[BaseModel]) -> FormTree:
    """Load a previously saved draft, re-binding ``schema_class``."""
    from pydantic_studio.tree.nodes import FormTree

    raw = Path(path).read_bytes()
    return FormTree.model_validate_json(raw, context={"schema_class": schema})


def delete_draft(path: str | Path) -> None:
    """Remove a draft file. Idempotent."""
    Path(path).unlink(missing_ok=True)


def find_draft(directory: str | Path) -> Path | None:
    """Return the conventional draft path in ``directory`` if it exists."""
    p = Path(directory) / DRAFT_FILENAME
    return p if p.exists() else None


def draft_newer_than(draft: str | Path, source: str | Path) -> bool:
    """Return True if ``draft``'s mtime is later than ``source``'s.

    Useful for the recovery prompt: only resume if the draft has unsaved
    state newer than the on-disk source file.
    """
    draft_p = Path(draft)
    source_p = Path(source)
    if not draft_p.exists():
        return False
    if not source_p.exists():
        return True
    return draft_p.stat().st_mtime > source_p.stat().st_mtime
