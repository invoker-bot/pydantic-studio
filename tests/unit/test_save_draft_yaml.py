"""Tests for save_draft_yaml — partial-tree YAML writer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from pydantic_studio import build_form_tree

if TYPE_CHECKING:
    from pathlib import Path


def test_save_draft_yaml_partial_tree(tmp_path: Path) -> None:
    """save_draft_yaml emits whatever to_python() returns; no validation."""
    from pydantic_studio.io.yaml_draft import save_draft_yaml

    class M(BaseModel):
        required_field: str
        optional_field: int = 42

    tree = build_form_tree(M)
    out = tmp_path / "draft.yaml"
    save_draft_yaml(tree, out)
    assert out.exists()


def test_save_draft_yaml_with_set_value(tmp_path: Path) -> None:
    from pydantic_studio.io.yaml_draft import save_draft_yaml

    class M(BaseModel):
        required_field: str
        optional_field: int = 42

    tree = build_form_tree(M)
    tree.set_value("optional_field", 99)
    out = tmp_path / "draft.yaml"
    save_draft_yaml(tree, out)
    content = out.read_text(encoding="utf-8")
    assert "99" in content


def test_save_draft_yaml_atomic(tmp_path: Path) -> None:
    """Verify no .tmp- leftover after success."""
    from pydantic_studio.io.yaml_draft import save_draft_yaml
    from tests.fixtures.schemas import Server

    tree = build_form_tree(Server)
    out = tmp_path / "draft.yaml"
    save_draft_yaml(tree, out)
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp-")]
    assert leftovers == []
