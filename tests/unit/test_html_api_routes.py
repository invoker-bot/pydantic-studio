"""Tests for the JSON API routes added in shadcn redesign Phase 1."""

from __future__ import annotations

import time as _time

from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html import StudioServer
from pydantic_studio.session import SubmitResult
from pydantic_studio.variants import VariantRegistry, VariantSpec, build_variant_form_tree


class _Demo(BaseModel):
    name: str = Field(description="Service identifier")
    workers: int = 4


class _Profile(BaseModel):
    name: str = "alpha"
    role: str = "user"


class _WithProfile(BaseModel):
    profile: _Profile = Field(default_factory=_Profile)
    workers: int = 4


class _WithTags(BaseModel):
    tags: list[str] = Field(default_factory=list)


class _RootEmail(BaseModel):
    address: str = "ops@example.com"


class _RootSlack(BaseModel):
    channel: str = "#ops"


class _RootRequiredSlack(BaseModel):
    channel: str


class _WithNonFiniteFloat(BaseModel):
    value: float = float("nan")


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


def test_api_tree_returns_json_for_non_finite_float_defaults() -> None:
    tree = build_form_tree(_WithNonFiniteFloat)
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app, raise_server_exceptions=False)

    response = client.get("/api/tree")

    assert response.status_code == 200
    body = response.json()
    value = next(f for f in body["root"]["fields"] if f["name"] == "value")
    assert value["value"] == "NaN"
    assert value["default"] == "NaN"


def test_api_mutations_accept_non_finite_float_wire_strings() -> None:
    tree = build_form_tree(_WithNonFiniteFloat)
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app, raise_server_exceptions=False)

    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": "value", "value": "Infinity"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mutation_result"] == {"ok": True, "errors": []}
    value = next(f for f in body["tree"]["root"]["fields"] if f["name"] == "value")
    assert value["value"] == "Infinity"


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


def test_api_mutations_missing_op_returns_400() -> None:
    client = _client({"name": "alpha"})
    response = client.post(
        "/api/mutations", json={"path": "name", "value": "beta"}
    )
    assert response.status_code == 400
    assert "op is required" in response.json()["detail"]


def test_api_mutations_non_string_op_returns_400() -> None:
    client = _client({"name": "alpha"})
    response = client.post(
        "/api/mutations", json={"op": 123, "path": "name", "value": "beta"}
    )
    assert response.status_code == 400
    assert "op must be a string" in response.json()["detail"]


def test_api_mutations_non_object_request_returns_400() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app, raise_server_exceptions=False)

    response = client.post("/api/mutations", json=["set_value", "name"])

    assert response.status_code == 400
    assert "JSON object" in response.json()["detail"]


def test_api_mutations_invalid_json_returns_400() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app, raise_server_exceptions=False)

    response = client.post(
        "/api/mutations",
        content=b"{not-json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert "invalid JSON" in response.json()["detail"]


def test_api_mutations_missing_required_argument_returns_400() -> None:
    client = _client({"name": "alpha", "workers": 4})

    response = client.post(
        "/api/mutations",
        json={"op": "remove_item", "path": "name"},
    )

    assert response.status_code == 400
    assert "index is required" in response.json()["detail"]


def test_api_mutations_bad_numeric_argument_returns_400() -> None:
    client = _client({"name": "alpha", "workers": 4})

    response = client.post(
        "/api/mutations",
        json={"op": "remove_item", "path": "name", "index": "nan"},
    )

    assert response.status_code == 400
    assert "mutation failed" in response.json()["detail"]


def test_api_mutations_non_string_path_returns_400() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app, raise_server_exceptions=False)

    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": None, "value": "beta"},
    )

    assert response.status_code == 400
    assert "path must be a string" in response.json()["detail"]


def test_api_mutations_missing_path_returns_400() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app, raise_server_exceptions=False)

    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "value": "beta"},
    )

    assert response.status_code == 400
    assert "path is required" in response.json()["detail"]


def test_api_mutations_missing_set_value_payload_returns_400() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app, raise_server_exceptions=False)

    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": "name"},
    )

    assert response.status_code == 400
    assert "value is required" in response.json()["detail"]


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


def test_api_submit_preserves_errors_without_paths() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)

    def submit_pathless_error() -> SubmitResult:
        return SubmitResult(ok=False, errors=("model-level failure",), paths=())

    server.session.submit = submit_pathless_error
    response = TestClient(server.app).post("/api/submit")

    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "errors": [{"path": "", "message": "model-level failure"}],
    }


def test_api_submit_exception_returns_json_detail() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)

    def broken_submit() -> SubmitResult:
        raise RuntimeError("submit backend unavailable")

    server.session.submit = broken_submit
    response = TestClient(server.app, raise_server_exceptions=False).post("/api/submit")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "submit failed: submit backend unavailable"}
    assert server.submitted is False


def test_api_cancel_marks_server_cancelled() -> None:
    server, client = _server_and_client({"name": "x"})
    response = client.post("/api/cancel")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert server.cancelled is True


def test_api_cancel_exception_returns_json_detail() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)

    def broken_cancel() -> None:
        raise RuntimeError("cancel backend unavailable")

    server.session.cancel = broken_cancel
    response = TestClient(server.app, raise_server_exceptions=False).post("/api/cancel")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "cancel failed: cancel backend unavailable"}
    assert server.cancelled is False


def test_api_heartbeat_returns_ok_and_records_timestamp() -> None:
    server, client = _server_and_client({"name": "x"})
    before = _time.time()
    response = client.get("/api/heartbeat")
    after = _time.time()
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert before <= server.last_heartbeat_ts <= after


def test_studio_server_exposes_session_and_compat_flags() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)
    assert server.session.tree is tree
    assert server.submitted is False
    assert server.cancelled is False

    response = TestClient(server.app).post("/api/submit")
    assert response.status_code == 200
    assert server.session.submitted is True
    assert server.submitted is True
    assert server.cancelled is False


def test_api_cancel_uses_session_outcome() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)
    response = TestClient(server.app).post("/api/cancel")
    assert response.status_code == 200
    assert server.session.cancelled is True
    assert server.cancelled is True


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


def test_api_tree_disables_readonly_undo_when_next_snapshot_changes_readonly_path() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    assert tree.set_value("name", "beta").ok is True
    server = StudioServer(tree=tree, save_path=None, readonly_paths={"name"})
    client = TestClient(server.app)

    payload = client.get("/api/tree").json()

    assert payload["history"] == {"can_undo": False, "can_redo": False}


def test_api_tree_disables_readonly_redo_when_next_snapshot_changes_readonly_path() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    assert tree.set_value("name", "beta").ok is True
    assert tree.undo() is True
    server = StudioServer(tree=tree, save_path=None, readonly_paths={"name"})
    client = TestClient(server.app)

    payload = client.get("/api/tree").json()

    assert payload["history"] == {"can_undo": False, "can_redo": False}


def test_api_mutations_tree_includes_readonly_paths() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None, readonly_paths={"name"})
    client = TestClient(server.app)

    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": "workers", "value": 8},
    )

    assert response.status_code == 200
    assert response.json()["tree"]["readonly_paths"] == ["name"]


def test_api_mutations_reject_readonly_path_without_mutating() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None, readonly_paths={"name"})
    client = TestClient(server.app)

    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": "name", "value": "beta"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mutation_result"] == {
        "ok": False,
        "errors": ["name is read-only — value is managed by the caller"],
    }
    assert body["validation"]["errors"][0] == {
        "path": "name",
        "message": "name is read-only — value is managed by the caller",
    }
    assert server.tree.root.find("name").value == "alpha"
    name_field = next(f for f in body["tree"]["root"]["fields"] if f["name"] == "name")
    assert name_field["value"] == "alpha"


def test_api_mutations_reject_readonly_descendant_without_mutating() -> None:
    tree = build_form_tree(_WithProfile)
    server = StudioServer(tree=tree, save_path=None, readonly_paths={"profile"})
    client = TestClient(server.app)

    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": "profile.name", "value": "beta"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mutation_result"] == {
        "ok": False,
        "errors": ["profile.name is read-only — value is managed by the caller"],
    }
    assert server.tree.root.find("profile").find("name").value == "alpha"


def test_api_mutations_reject_bracket_form_readonly_path_without_mutating() -> None:
    tree = build_form_tree(_WithTags, existing={"tags": ["locked", "free"]})
    server = StudioServer(tree=tree, save_path=None, readonly_paths={"tags[0]"})
    client = TestClient(server.app)

    response = client.post(
        "/api/mutations",
        json={"op": "set_value", "path": "tags.0", "value": "edited"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mutation_result"] == {
        "ok": False,
        "errors": ["tags.0 is read-only — value is managed by the caller"],
    }
    assert server.tree.root.find("tags").items[0].value == "locked"


def test_api_mutations_reject_root_variant_switch_when_any_path_is_readonly() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_RootEmail),
                VariantSpec(id="slack", model=_RootSlack),
            ]
        ),
        selected_id="email",
    )
    server = StudioServer(tree=tree, save_path=None, readonly_paths={"address"})
    client = TestClient(server.app)

    response = client.post(
        "/api/mutations",
        json={"op": "select_root_variant", "variant_id": "slack"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mutation_result"] == {
        "ok": False,
        "errors": ["root variant is read-only — value is managed by the caller"],
    }
    assert body["validation"]["errors"][0] == {
        "path": "",
        "message": "root variant is read-only — value is managed by the caller",
    }
    assert server.tree.schema_class is _RootEmail
    assert server.tree.variant is not None
    assert server.tree.variant.selected_id == "email"
    assert server.tree.root.find("address").value == "ops@example.com"
    assert server.tree.root.find("channel") is None


def test_api_mutations_reject_readonly_undo_without_mutating() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    assert tree.set_value("name", "beta").ok is True
    server = StudioServer(tree=tree, save_path=None, readonly_paths={"name"})
    client = TestClient(server.app)

    response = client.post("/api/mutations", json={"op": "undo"})

    assert response.status_code == 200
    body = response.json()
    assert body["mutation_result"] == {
        "ok": False,
        "errors": ["undo would modify read-only path 'name'"],
    }
    assert body["validation"]["errors"][0] == {
        "path": "",
        "message": "undo would modify read-only path 'name'",
    }
    assert server.tree.root.find("name").value == "beta"
    name_field = next(f for f in body["tree"]["root"]["fields"] if f["name"] == "name")
    assert name_field["value"] == "beta"
    assert body["tree"]["history"] == {"can_undo": False, "can_redo": False}


def test_api_mutations_reject_readonly_redo_without_mutating() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    assert tree.set_value("name", "beta").ok is True
    assert tree.undo() is True
    server = StudioServer(tree=tree, save_path=None, readonly_paths={"name"})
    client = TestClient(server.app)

    response = client.post("/api/mutations", json={"op": "redo"})

    assert response.status_code == 200
    body = response.json()
    assert body["mutation_result"] == {
        "ok": False,
        "errors": ["redo would modify read-only path 'name'"],
    }
    assert server.tree.root.find("name").value == "alpha"
    name_field = next(f for f in body["tree"]["root"]["fields"] if f["name"] == "name")
    assert name_field["value"] == "alpha"
    assert body["tree"]["history"] == {"can_undo": False, "can_redo": False}


def test_api_mutations_allows_readonly_undo_when_path_is_unchanged() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    assert tree.set_value("workers", 8).ok is True
    server = StudioServer(tree=tree, save_path=None, readonly_paths={"name"})
    client = TestClient(server.app)

    response = client.post("/api/mutations", json={"op": "undo"})

    assert response.status_code == 200
    body = response.json()
    assert body["mutation_result"] == {"ok": True, "errors": []}
    assert server.tree.root.find("name").value == "alpha"
    assert server.tree.root.find("workers").value == 4


def test_api_mutations_root_variant_validation_error_uses_root_path() -> None:
    tree = build_variant_form_tree(
        VariantRegistry(
            [
                VariantSpec(id="email", model=_RootEmail),
                VariantSpec(id="slack", model=_RootRequiredSlack),
            ]
        ),
        selected_id="email",
    )
    client = TestClient(StudioServer(tree=tree, save_path=None).app)

    response = client.post(
        "/api/mutations",
        json={
            "op": "select_root_variant",
            "variant_id": "slack",
            "path": None,
            "seed": {"channel": None},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mutation_result"]["ok"] is False
    assert body["validation"]["errors"][0]["path"] == ""
    assert "channel: value is required" in body["validation"]["errors"][0]["message"]
    assert tree.schema_class is _RootEmail
    assert tree.root.find("address") is not None
    assert tree.root.find("channel") is None


def test_run_html_app_signature_matches_run_app_contract() -> None:
    """run_html_app mirrors the TUI session contract: readonly_paths in,
    EditOutcome out — `hft config gen/edit --web` depends on it."""
    import inspect

    from pydantic_studio.renderers.html.server import run_html_app

    signature = inspect.signature(run_html_app)
    assert "readonly_paths" in signature.parameters


def test_legacy_form_routes_are_not_registered() -> None:
    """The web renderer is now the React SPA plus JSON API only."""
    client = _client({"name": "alpha", "workers": 4})

    for method, path in (
        ("post", "/field/name"),
        ("post", "/seq/tags/add"),
        ("post", "/map/env/add"),
        ("post", "/union/notifier/select"),
        ("post", "/submit"),
        ("post", "/cancel"),
        ("get", "/heartbeat"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 404, path
