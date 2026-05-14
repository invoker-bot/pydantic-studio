"""Smoke test: the committed Vite bundle is reachable via FastAPI's
existing /static mount. Phase 5 / 6 will move the SPA's index.html
to be served at / directly; for Phase 2 we only verify it's
reachable AT ALL via the path the static mount already provides.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html import StudioServer


class _Demo(BaseModel):
    name: str = ""


def test_static_dist_index_is_served() -> None:
    tree = build_form_tree(_Demo)
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app)

    response = client.get("/static/dist/index.html")
    assert response.status_code == 200
    text = response.text
    # Vite always emits a div#root mount point.
    assert 'id="root"' in text
    # And a <script type="module"> tag for the bundled entry.
    assert '<script type="module"' in text


def test_static_dist_assets_are_served() -> None:
    tree = build_form_tree(_Demo)
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app)

    # Find the bundled JS file via the HTML to avoid hard-coding the hash.
    html = client.get("/static/dist/index.html").text
    # crude scrape: pull the first /assets/...js path from the HTML
    import re

    js_match = re.search(r'/assets/[A-Za-z0-9_-]+\.js', html)
    assert js_match is not None, f"no /assets/*.js found in built index.html:\n{html}"
    js_path = js_match.group(0)

    # The HTML references it as /assets/<hash>.js (root-relative),
    # but the static mount serves it at /static/dist/assets/<hash>.js.
    mounted_path = f"/static/dist{js_path}"
    response = client.get(mounted_path)
    assert response.status_code == 200, (
        f"GET {mounted_path} returned {response.status_code}; "
        f"the static mount under /static/dist/ should serve every "
        f"file under src/pydantic_studio/renderers/html/static/dist/. "
        f"Re-run `pnpm build` from frontend/ to refresh the bundle."
    )
    # Bundled JS must be a non-trivial size.
    assert len(response.content) > 1000
