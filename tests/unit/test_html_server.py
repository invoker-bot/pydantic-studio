"""Tests for the HTML renderer's FastAPI server."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import Server

if TYPE_CHECKING:
    from pathlib import Path


def test_index_route_serves_spa_shell() -> None:
    """`/` must serve the React SPA's index.html, not the legacy Jinja page.

    Regression for the incomplete cutover discovered after Phase 5: the
    SPA bundle was committed to static/dist/ but `/` was still routed to
    ``server.render_index`` (Jinja2 + HTMX), so users running
    ``run_html_app`` landed on the pre-redesign page even though all 25
    field components had shipped.
    """
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None)
    client = TestClient(studio_server.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    text = response.text
    assert '<div id="root">' in text
    assert 'src="/static/dist/assets/index-' in text
    assert ".js" in text
    assert "hx-post" not in text
    assert "hx-get" not in text


def test_spa_bundle_referenced_by_index_is_reachable() -> None:
    """The Vite-emitted script tag in /'s index.html must resolve.

    Guards against bundle/index version skew — e.g., if `/` somehow
    serves an older index.html that references a deleted asset hash.
    """
    import re

    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None)
    client = TestClient(studio_server.app)
    index_text = client.get("/").text
    match = re.search(r'src="(/static/dist/assets/index-[^"]+\.js)"', index_text)
    assert match is not None, "SPA bundle script tag missing from index.html"
    bundle_response = client.get(match.group(1))
    assert bundle_response.status_code == 200
    assert len(bundle_response.content) > 10000


def test_index_injects_runtime_base_path_for_mounted_app() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None, base_path="/studio")
    client = TestClient(studio_server.app)
    response = client.get("/")
    assert response.status_code == 200
    text = response.text
    assert 'window.__PYDANTIC_STUDIO__ = {"basePath": "/studio"};' in text
    assert 'src="/studio/static/dist/assets/index-' in text
    assert 'href="/studio/static/dist/assets/index-' in text


def test_base_path_normalization() -> None:
    from pydantic_studio.renderers.html.server import normalize_base_path

    assert normalize_base_path("") == ""
    assert normalize_base_path("/") == ""
    assert normalize_base_path("studio") == "/studio"
    assert normalize_base_path("/studio") == "/studio"
    assert normalize_base_path("/studio/") == "/studio"


def test_static_htmx_serves() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None)
    client = TestClient(studio_server.app)
    response = client.get("/static/htmx.min.js")
    assert response.status_code == 200
    assert len(response.content) > 1000


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


class TestSeqRoute:
    def test_seq_add(self) -> None:
        from pydantic import BaseModel

        from pydantic_studio.renderers.html import StudioServer

        class M(BaseModel):
            tags: list[str] = []

        tree = build_form_tree(M)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/seq/tags/add")
        assert response.status_code == 200
        node = tree.root.find("tags")
        assert node is not None
        assert len(node.items) == 1

    def test_seq_remove(self) -> None:
        from pydantic import BaseModel

        from pydantic_studio.renderers.html import StudioServer

        class M(BaseModel):
            tags: list[str] = []

        tree = build_form_tree(M, existing={"tags": ["a", "b", "c"]})
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/seq/tags/remove?index=1")
        assert response.status_code == 200
        node = tree.root.find("tags")
        assert node is not None
        assert len(node.items) == 2


class TestMapRoute:
    def test_map_add(self) -> None:
        from pydantic import BaseModel

        from pydantic_studio.renderers.html import StudioServer

        class M(BaseModel):
            settings: dict[str, int] = {}

        tree = build_form_tree(M)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/map/settings/add")
        assert response.status_code == 200
        node = tree.root.find("settings")
        assert node is not None
        assert len(node.entries) == 1


class TestSubmitCancel:
    def test_submit_writes_yaml(self, tmp_path: Path) -> None:
        from pydantic_studio.renderers.html import StudioServer

        out = tmp_path / "out.yaml"
        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=out)
        client = TestClient(studio_server.app)
        response = client.post("/submit")
        assert response.status_code == 200
        assert out.exists()
        assert studio_server.submitted is True

    def test_cancel_marks_cancelled(self) -> None:
        from pydantic_studio.renderers.html import StudioServer

        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.post("/cancel")
        assert response.status_code == 200
        assert studio_server.cancelled is True

    def test_heartbeat_returns_ok(self) -> None:
        from pydantic_studio.renderers.html import StudioServer

        tree = build_form_tree(Server)
        studio_server = StudioServer(tree=tree, save_path=None)
        client = TestClient(studio_server.app)
        response = client.get("/heartbeat")
        assert response.status_code == 200


def test_heartbeat_timeout_marks_cancelled() -> None:
    """If too much time passes since the last heartbeat, server marks cancelled."""
    import time

    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(
        tree=tree,
        save_path=None,
        heartbeat_timeout_seconds=0.1,
    )
    studio_server.last_heartbeat_ts = time.time()
    time.sleep(0.15)
    studio_server._check_heartbeat_timeout()
    assert studio_server.cancelled is True


def test_heartbeat_timeout_cancels_session() -> None:
    import time

    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(
        tree=tree,
        save_path=None,
        heartbeat_timeout_seconds=0.1,
    )
    studio_server.last_heartbeat_ts = time.time()
    time.sleep(0.15)
    studio_server._check_heartbeat_timeout()
    assert studio_server.session.cancelled is True
    assert studio_server.cancelled is True


def test_heartbeat_recent_does_not_cancel() -> None:
    import time

    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(
        tree=tree,
        save_path=None,
        heartbeat_timeout_seconds=10.0,
    )
    studio_server.last_heartbeat_ts = time.time()
    studio_server._check_heartbeat_timeout()
    assert studio_server.cancelled is False
