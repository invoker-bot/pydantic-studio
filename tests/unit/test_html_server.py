"""Tests for the HTML renderer's FastAPI server."""

from __future__ import annotations

from fastapi.testclient import TestClient

from pydantic_studio import build_form_tree
from tests.fixtures.schemas import Server


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


def test_index_embeds_base_path_config_without_html_entity_mangling() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(
        tree=tree,
        save_path=None,
        base_path="/studio/<tenant>&region",
    )
    client = TestClient(studio_server.app)

    text = client.get("/").text
    script_start = text.index("window.__PYDANTIC_STUDIO__")
    script_end = text.index("</script>", script_start)
    config_script = text[script_start:script_end]

    assert config_script == (
        'window.__PYDANTIC_STUDIO__ = {"basePath": '
        '"/studio/\\u003ctenant\\u003e\\u0026region"};'
    )
    assert "&lt;tenant&gt;" not in config_script


def test_index_escapes_base_path_asset_attributes() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(
        tree=tree,
        save_path=None,
        base_path="/studio/<tenant>&region",
    )
    client = TestClient(studio_server.app)

    text = client.get("/").text

    assert 'src="/studio/&lt;tenant&gt;&amp;region/static/dist/assets/index-' in text
    assert 'href="/studio/&lt;tenant&gt;&amp;region/static/dist/assets/index-' in text


def test_base_path_normalization() -> None:
    from pydantic_studio.renderers.html.server import normalize_base_path

    assert normalize_base_path("") == ""
    assert normalize_base_path("/") == ""
    assert normalize_base_path("studio") == "/studio"
    assert normalize_base_path("/studio") == "/studio"
    assert normalize_base_path("/studio/") == "/studio"


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
