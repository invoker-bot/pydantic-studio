"""Tests for the JSON API routes added in shadcn redesign Phase 1."""

from __future__ import annotations

import time as _time

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


def _server_and_client(
    existing: dict | None = None,
) -> tuple[StudioServer, TestClient]:
    """Like ``_client``, but also returns the StudioServer so tests can
    assert side-effects on ``server.submitted`` / ``server.cancelled`` /
    ``server.last_heartbeat_ts``.
    """
    tree = build_form_tree(_Demo, existing=existing)
    server = StudioServer(tree=tree, save_path=None)
    return server, TestClient(server.app)


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


def test_api_mutations_set_value_returns_updated_tree() -> None:
    client = _client({"name": "before", "workers": 4})
    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": "name", "value": "after"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["validation"] == {"ok": True, "errors": []}
    name_field = next(f for f in body["tree"]["root"]["fields"] if f["name"] == "name")
    assert name_field["value"] == "after"


def test_api_mutations_validation_failure_returns_unchanged_tree() -> None:
    client = _client({"name": "alpha", "workers": 4})
    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": "workers", "value": "not-an-int"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["ok"] is False
    workers_field = next(
        f for f in body["tree"]["root"]["fields"] if f["name"] == "workers"
    )
    assert workers_field["value"] == 4


def test_api_mutations_unknown_op_returns_400() -> None:
    client = _client({"name": "alpha"})
    response = client.post(
        "/api/mutations", json={"op": "nuke", "path": "name"}
    )
    assert response.status_code == 400
    body = response.json()
    assert "nuke" in body["detail"]


def test_api_submit_marks_server_submitted_and_returns_ok() -> None:
    server, client = _server_and_client({"name": "alpha", "workers": 4})
    response = client.post("/api/submit")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert server.submitted is True


def test_api_submit_validation_failure_returns_400_with_errors() -> None:
    # Required field 'name' deliberately unset
    server, client = _server_and_client()
    response = client.post("/api/submit")
    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["errors"]
    assert server.submitted is False


def test_api_cancel_marks_server_cancelled() -> None:
    server, client = _server_and_client({"name": "x"})
    response = client.post("/api/cancel")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert server.cancelled is True


def test_api_heartbeat_returns_ok_and_records_timestamp() -> None:
    server, client = _server_and_client({"name": "x"})
    before = _time.time()
    response = client.get("/api/heartbeat")
    after = _time.time()
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert before <= server.last_heartbeat_ts <= after


def test_api_tree_includes_readonly_paths() -> None:
    """The server's readonly_paths reach the SPA via /api/tree — the
    frontend renders those fields inside a disabled fieldset."""
    from fastapi.testclient import TestClient
    from pydantic import BaseModel

    from pydantic_studio import build_form_tree
    from pydantic_studio.renderers.html.server import StudioServer

    class _S(BaseModel):
        path: str = "x"
        name: str = "y"

    server = StudioServer(
        tree=build_form_tree(_S), save_path=None, readonly_paths={"path"}
    )
    client = TestClient(server.app)
    payload = client.get("/api/tree").json()
    assert payload["readonly_paths"] == ["path"]


def test_run_html_app_signature_matches_run_app_contract() -> None:
    """run_html_app mirrors the TUI session contract: readonly_paths in,
    EditOutcome out — `hft config gen/edit --web` depends on it."""
    import inspect

    from pydantic_studio.renderers.html.server import run_html_app

    signature = inspect.signature(run_html_app)
    assert "readonly_paths" in signature.parameters
