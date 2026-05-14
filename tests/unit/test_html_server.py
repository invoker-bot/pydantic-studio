"""Tests for the HTML renderer's FastAPI server."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import Server

if TYPE_CHECKING:
    from pathlib import Path


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


def test_index_includes_heartbeat_poll() -> None:
    """The base template emits an HTMX heartbeat trigger so the server
    can detect a closed tab. Without this, run_html_app's watchdog never
    fires and the process runs forever when the browser is dismissed.
    """
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None)
    client = TestClient(studio_server.app)
    response = client.get("/")
    assert response.status_code == 200
    text = response.text
    assert 'hx-get="/heartbeat"' in text
    # The trigger must include both load (first hit) and a recurring
    # interval — load alone wouldn't refresh; interval alone would let
    # a fast tab-close before the first interval slip past unnoticed.
    assert 'hx-trigger="load, every' in text


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
