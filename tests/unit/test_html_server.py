"""Tests for the HTML renderer's FastAPI server."""

from __future__ import annotations

from fastapi.testclient import TestClient

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import Server


def test_index_route_returns_html() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None)
    client = TestClient(studio_server.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Page should reference the schema's class name somewhere.
    assert "Server" in response.text or "name" in response.text


def test_static_htmx_serves() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None)
    client = TestClient(studio_server.app)
    response = client.get("/static/htmx.min.js")
    assert response.status_code == 200
    # Real htmx is at least a few KB; the stub was a single line.
    assert len(response.content) > 1000


def test_index_renders_form_fields() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None)
    client = TestClient(studio_server.app)
    response = client.get("/")
    assert response.status_code == 200
    text = response.text
    # Each Server field should appear with an htmx-bound input.
    assert 'name="value"' in text
    assert "hx-post" in text
    # The field names appear as labels.
    assert "name:" in text
    assert "port:" in text
    assert "debug:" in text


class TestFieldRoute:
    def test_field_post_updates_tree_and_returns_preview(self) -> None:
        from pydantic_studio.renderers.html import StudioServer

        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/field/name", data={"value": "newname"})
        assert response.status_code == 200
        assert "newname" in response.text
        node = tree.root.find("name")
        assert node is not None
        assert node.value == "newname"

    def test_field_post_int_parses(self) -> None:
        from pydantic_studio.renderers.html import StudioServer

        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/field/port", data={"value": "9090"})
        assert response.status_code == 200
        node = tree.root.find("port")
        assert node is not None
        assert node.value == 9090

    def test_field_post_validation_failure_keeps_old_value(self) -> None:
        from pydantic_studio.renderers.html import StudioServer

        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        # port has le=65535; provide something out of range.
        response = client.post("/field/port", data={"value": "99999"})
        # 200 (HTMX-friendly), but tree not mutated.
        assert response.status_code == 200
        node = tree.root.find("port")
        assert node is not None
        # Default Server.port = 8080; value is None on a fresh tree
        # (default-seeding was removed in T1 housekeeping). Either is fine —
        # what matters is that the failed parse didn't poison the value.
        assert node.value != 99999
