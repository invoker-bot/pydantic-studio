"""Tests for the JSON API routes added in shadcn redesign Phase 1."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html import StudioServer


class _Demo(BaseModel):
    name: str = Field(description="Service identifier")
    workers: int = 4


def _client(existing: dict | None = None) -> TestClient:
    tree = build_form_tree(_Demo, existing=existing)
    server = StudioServer(tree=tree, save_path=None)
    return TestClient(server.app)


def test_api_tree_returns_json_with_schema_and_root() -> None:
    client = _client({"name": "alpha", "workers": 8})
    response = client.get("/api/tree")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["schema_name"].endswith("_Demo")
    assert body["root"]["kind"] == "group"
    names = {f["name"] for f in body["root"]["fields"]}
    assert {"name", "workers"} <= names


def test_api_tree_includes_unsaved_count() -> None:
    client = _client({"name": "alpha"})
    body = client.get("/api/tree").json()
    assert body["unsaved_count"] == 0
