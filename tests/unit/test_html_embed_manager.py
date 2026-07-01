"""StudioEmbedManager — multi-session embed layer on top of StudioServer."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from pydantic_studio import EditSession, build_form_tree
from pydantic_studio.renderers.html import StudioEmbedManager, mount_embed_app


class _Schema(BaseModel):
    name: str = "alpha"
    workers: int = 4


def test_create_session_isolates_two_concurrent_sessions() -> None:
    manager = StudioEmbedManager("/config-studio")
    sid_a = manager.create_session(tree=build_form_tree(_Schema))
    sid_b = manager.create_session(tree=build_form_tree(_Schema))
    client = TestClient(manager.app)

    resp_a = client.post(
        f"/s/{sid_a}/api/mutations",
        json={"op": "set_value", "path": "name", "value": "from-a"},
    )
    assert resp_a.status_code == 200

    tree_a = client.get(f"/s/{sid_a}/api/tree").json()
    tree_b = client.get(f"/s/{sid_b}/api/tree").json()
    name_field_a = next(f for f in tree_a["root"]["fields"] if f["name"] == "name")
    name_field_b = next(f for f in tree_b["root"]["fields"] if f["name"] == "name")
    assert name_field_a["value"] == "from-a"
    assert name_field_b["value"] == "alpha"


def test_session_base_path_carries_full_external_prefix() -> None:
    manager = StudioEmbedManager("/config-studio")
    sid = manager.create_session(tree=build_form_tree(_Schema))
    client = TestClient(manager.app)

    index = client.get(f"/s/{sid}/")
    assert index.status_code == 200
    assert f'"basePath": "/config-studio/s/{sid}"' in index.text


def test_mount_embed_app_mounts_manager_onto_host_at_prefix() -> None:
    host = FastAPI()
    manager = mount_embed_app(host, "/config-studio")
    sid = manager.create_session(tree=build_form_tree(_Schema))
    client = TestClient(host)

    resp = client.get(f"/config-studio/s/{sid}/api/tree")
    assert resp.status_code == 200
    assert resp.json()["root"]["kind"] == "group"


def test_mount_embed_app_rejects_host_without_mount() -> None:
    class _NoMount:
        pass

    with pytest.raises(TypeError, match="mount"):
        mount_embed_app(_NoMount(), "/config-studio")


def test_get_session_returns_edit_session_usable_while_active() -> None:
    manager = StudioEmbedManager("/config-studio")
    sid = manager.create_session(tree=build_form_tree(_Schema))

    session = manager.get_session(sid)
    assert isinstance(session, EditSession)
    assert session.outcome is None
    instance = session.tree.to_instance()
    assert instance.name == "alpha"


def test_close_session_removes_route_and_404s() -> None:
    manager = StudioEmbedManager("/config-studio")
    sid = manager.create_session(tree=build_form_tree(_Schema))
    client = TestClient(manager.app)

    assert client.get(f"/s/{sid}/api/tree").status_code == 200
    manager.close_session(sid)
    assert client.get(f"/s/{sid}/api/tree").status_code == 404


def test_get_outcome_is_none_until_submit_then_reopen_resets_it() -> None:
    manager = StudioEmbedManager("/config-studio")
    sid = manager.create_session(tree=build_form_tree(_Schema))
    client = TestClient(manager.app)

    assert manager.get_outcome(sid) is None

    submit_resp = client.post(f"/s/{sid}/api/submit")
    assert submit_resp.status_code == 200
    outcome = manager.get_outcome(sid)
    assert outcome is not None
    assert outcome.submitted

    # Terminal outcome -> mutations 409 (host business validation failed,
    # host must reopen to let the user keep editing).
    mutation_resp = client.post(
        f"/s/{sid}/api/mutations",
        json={"op": "set_value", "path": "name", "value": "still-editing"},
    )
    assert mutation_resp.status_code == 409

    manager.reopen_session(sid)
    assert manager.get_outcome(sid) is None

    mutation_resp = client.post(
        f"/s/{sid}/api/mutations",
        json={"op": "set_value", "path": "name", "value": "still-editing"},
    )
    assert mutation_resp.status_code == 200


def test_idle_ttl_sweep_closes_abandoned_sessions() -> None:
    manager = StudioEmbedManager("/config-studio", idle_ttl_seconds=1.0)
    sid = manager.create_session(tree=build_form_tree(_Schema))
    client = TestClient(manager.app)
    client.get(f"/s/{sid}/api/heartbeat")

    # Fresh heartbeat -> sweep is a no-op.
    manager.sweep_idle_sessions()
    assert client.get(f"/s/{sid}/api/tree").status_code == 200

    # Force the recorded heartbeat into the past so the TTL has elapsed.
    server, _route = manager._sessions[sid]
    server.last_heartbeat_ts -= 10.0
    manager.sweep_idle_sessions()
    assert client.get(f"/s/{sid}/api/tree").status_code == 404


def test_idle_ttl_sweep_disabled_when_none() -> None:
    manager = StudioEmbedManager("/config-studio", idle_ttl_seconds=None)
    sid = manager.create_session(tree=build_form_tree(_Schema))
    client = TestClient(manager.app)
    client.get(f"/s/{sid}/api/heartbeat")

    server, _route = manager._sessions[sid]
    server.last_heartbeat_ts -= 10_000.0
    manager.sweep_idle_sessions()
    assert client.get(f"/s/{sid}/api/tree").status_code == 200


def test_manager_app_has_no_catch_all_so_runtime_mounts_are_reachable() -> None:
    manager = StudioEmbedManager("/config-studio")
    sid_first = manager.create_session(tree=build_form_tree(_Schema))
    client = TestClient(manager.app)
    assert client.get(f"/s/{sid_first}/api/tree").status_code == 200

    # A session created *after* the client already exists (simulating a
    # runtime-added mount happening after other routes were registered)
    # must still be reachable — nothing upstream should shadow it.
    sid_second = manager.create_session(tree=build_form_tree(_Schema))
    assert client.get(f"/s/{sid_second}/api/tree").status_code == 200
    assert client.get("/does-not-exist").status_code == 404


def test_create_session_supports_readonly_paths() -> None:
    manager = StudioEmbedManager("/config-studio")
    sid = manager.create_session(
        tree=build_form_tree(_Schema), readonly_paths=("name",)
    )
    client = TestClient(manager.app)

    resp = client.post(
        f"/s/{sid}/api/mutations",
        json={"op": "set_value", "path": "name", "value": "blocked"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mutation_result"]["ok"] is False
