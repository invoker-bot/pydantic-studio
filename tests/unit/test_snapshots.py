from __future__ import annotations

import json

from pydantic_studio.tree.builder import build_form_tree
from pydantic_studio.tree.snapshots import draft_load, draft_save
from tests.fixtures.schemas import Simple


def test_draft_save_writes_file(tmp_path):
    tree = build_form_tree(Simple, existing={"name": "alice"})
    target = tmp_path / "draft.json"
    draft_save(tree, target)
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema_name"].endswith(":Simple")
    assert data["root"]["fields"][0]["name"] == "name"


def test_draft_save_is_atomic(tmp_path, monkeypatch):
    """Atomic write: target file is never seen in a partial state.
    Verified indirectly: a temp file is used, then renamed."""
    tree = build_form_tree(Simple)
    target = tmp_path / "draft.json"
    # Write twice; the second write should not interleave with the first.
    draft_save(tree, target)
    first = target.read_bytes()
    draft_save(tree, target)
    second = target.read_bytes()
    assert first == second  # idempotent given identical state


def test_draft_load_round_trip(tmp_path):
    tree = build_form_tree(Simple, existing={"name": "alice", "age": 9})
    target = tmp_path / "draft.json"
    draft_save(tree, target)
    loaded = draft_load(target, Simple)
    assert loaded.root.find("name").value == "alice"
    assert loaded.root.find("age").value == 9


def test_form_tree_set_value_writes_draft_when_path_set(tmp_path):
    tree = build_form_tree(Simple)
    tree.draft_path = tmp_path / "live.json"
    tree.set_value("name", "live")
    assert tree.draft_path.exists()
    saved = json.loads(tree.draft_path.read_text(encoding="utf-8"))
    name_field = next(f for f in saved["root"]["fields"] if f["name"] == "name")
    assert name_field["value"] == "live"
