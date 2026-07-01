from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.applications import Starlette

from pydantic_studio import EditSession, build_form_tree
from pydantic_studio.renderers.html import StudioServer, mount_html_app


class _Schema(BaseModel):
    name: str = "alpha"
    workers: int = 4


def test_studio_server_app_mounts_under_starlette_prefix() -> None:
    host = Starlette()
    server = StudioServer(tree=build_form_tree(_Schema), base_path="/studio")
    host.mount("/studio", server.app)
    client = TestClient(host)

    index = client.get("/studio/")
    assert index.status_code == 200
    assert 'window.__PYDANTIC_STUDIO__ = {"basePath": "/studio"};' in index.text

    tree = client.get("/studio/api/tree")
    assert tree.status_code == 200
    assert tree.json()["root"]["kind"] == "group"


def test_studio_server_rejects_session_with_ignored_tree_arguments() -> None:
    session = EditSession(tree=build_form_tree(_Schema))

    with pytest.raises(TypeError, match="session"):
        StudioServer(
            tree=build_form_tree(_Schema),
            readonly_paths={"name"},
            session=session,
        )


def test_mount_html_app_mounts_under_starlette_prefix() -> None:
    host = Starlette()
    server = mount_html_app(host, "/studio", tree=build_form_tree(_Schema))
    client = TestClient(host)

    assert client.get("/studio/api/tree").status_code == 200
    assert server.session.tree.schema_name.endswith("_Schema")
    assert server.base_path == "/studio"


def test_mount_html_app_mounts_under_fastapi_prefix() -> None:
    host = FastAPI()
    server = mount_html_app(host, "/studio", tree=build_form_tree(_Schema))
    client = TestClient(host)

    assert client.get("/studio/api/tree").status_code == 200
    response = client.post(
        "/studio/api/mutations",
        json={"op": "set_value", "path": "name", "value": "beta"},
    )
    assert response.status_code == 200
    assert server.tree.root.find("name").value == "beta"


def test_mount_html_app_rejects_host_without_mount() -> None:
    class _NoMount:
        pass

    with pytest.raises(TypeError, match="mount"):
        mount_html_app(_NoMount(), "/studio", tree=build_form_tree(_Schema))


def test_mount_html_app_rejects_session_with_ignored_tree_arguments() -> None:
    host = Starlette()
    session = EditSession(tree=build_form_tree(_Schema))

    with pytest.raises(TypeError, match="session"):
        mount_html_app(
            host,
            "/studio",
            tree=build_form_tree(_Schema),
            session=session,
        )
