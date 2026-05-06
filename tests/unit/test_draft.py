"""Tests for the draft persistence + recovery API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import Server

if TYPE_CHECKING:
    from pathlib import Path


def test_save_and_load_draft(tmp_path: Path) -> None:
    from pydantic_studio.tree.draft import load_draft, save_draft

    out = tmp_path / "draft.json"
    tree = build_form_tree(Server)
    tree.set_value("port", 9090)
    save_draft(tree, out)
    assert out.exists()

    reloaded = load_draft(out, Server)
    port = reloaded.root.find("port")
    assert port is not None
    assert port.value == 9090


def test_delete_draft(tmp_path: Path) -> None:
    from pydantic_studio.tree.draft import delete_draft, save_draft

    out = tmp_path / "draft.json"
    tree = build_form_tree(Server)
    save_draft(tree, out)
    assert out.exists()
    delete_draft(out)
    assert not out.exists()
    delete_draft(out)  # idempotent


def test_find_draft_returns_none_when_missing(tmp_path: Path) -> None:
    from pydantic_studio.tree.draft import find_draft

    assert find_draft(tmp_path) is None


def test_find_draft_returns_path_when_present(tmp_path: Path) -> None:
    from pydantic_studio.tree.draft import find_draft

    draft_path = tmp_path / ".pydantic-studio.draft.json"
    draft_path.write_text("{}", encoding="utf-8")
    found = find_draft(tmp_path)
    assert found == draft_path


def test_draft_newer_than(tmp_path: Path) -> None:
    """draft_newer_than returns True if draft mtime > source mtime."""
    import time

    from pydantic_studio.tree.draft import draft_newer_than

    source = tmp_path / "source.yaml"
    source.write_text("name: prod", encoding="utf-8")
    time.sleep(0.05)
    draft = tmp_path / ".pydantic-studio.draft.json"
    draft.write_text("{}", encoding="utf-8")
    assert draft_newer_than(draft, source) is True

    # Reverse case.
    time.sleep(0.05)
    source.touch()
    assert draft_newer_than(draft, source) is False
