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
