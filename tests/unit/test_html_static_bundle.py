"""Smoke tests for the committed Vite bundle served by FastAPI."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html import StudioServer

ROOT = Path(__file__).resolve().parents[2]
HTML_RENDERER_DIR = ROOT / "src" / "pydantic_studio" / "renderers" / "html"


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

    # After Phase 3's base-path fix the built HTML references the
    # asset at its full mounted path /static/dist/assets/<hash>.js;
    # no further path-rewriting is needed.
    html = client.get("/static/dist/index.html").text
    import re

    js_match = re.search(r'/static/dist/assets/[A-Za-z0-9_-]+\.js', html)
    assert js_match is not None, (
        f"no /static/dist/assets/*.js found in built index.html "
        f"(expected after vite.config base fix from T1):\n{html}"
    )
    mounted_path = js_match.group(0)

    response = client.get(mounted_path)
    assert response.status_code == 200, (
        f"GET {mounted_path} returned {response.status_code}; "
        f"the static mount under /static/dist/ should serve every "
        f"file under src/pydantic_studio/renderers/html/static/dist/. "
        f"Re-run `pnpm build` from frontend/ to refresh the bundle."
    )
    assert len(response.content) > 1000


def test_static_dist_asset_uses_static_prefixed_path() -> None:
    """After Phase 3's base-path fix, the built index.html should
    reference assets with the /static/dist/ prefix - meaning a browser
    loading /static/dist/index.html will fetch /static/dist/assets/<hash>.js
    (which the existing static mount serves), not the previously-stale
    root-relative /assets/<hash>.js.
    """
    tree = build_form_tree(_Demo)
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app)

    html = client.get("/static/dist/index.html").text
    import re

    # The base="/static/dist/" rewriting must produce prefixed asset URLs.
    js_match = re.search(r'/static/dist/assets/[A-Za-z0-9_-]+\.js', html)
    assert js_match is not None, (
        f"built index.html should reference /static/dist/assets/*.js "
        f"after Phase 3's base-path fix (vite.config.ts base='/static/dist/'); "
        f"current HTML:\n{html}"
    )

    # The bare /assets/<hash>.js form (Phase 2 default) should NOT appear -
    # all asset references must carry the /static/dist/ prefix.
    assert not re.search(r'(?<!/static/dist)/assets/[A-Za-z0-9_-]+\.js', html), (
        f"found a non-prefixed /assets/*.js reference in built HTML; "
        f"base path may not have taken effect:\n{html}"
    )


def test_legacy_htmx_assets_and_templates_are_not_packaged() -> None:
    legacy_paths = [
        HTML_RENDERER_DIR / "static" / "htmx.min.js",
        HTML_RENDERER_DIR / "static" / "studio.css",
        HTML_RENDERER_DIR / "templates",
    ]
    assert [path for path in legacy_paths if path.exists()] == []


def test_frontend_variant_schema_matches_supported_persistence_modes() -> None:
    schema = (ROOT / "frontend" / "src" / "api" / "schemas.ts").read_text(
        encoding="utf-8"
    )
    bundled_js = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((HTML_RENDERER_DIR / "static" / "dist" / "assets").glob("*.js"))
    )

    assert 'z.enum(["metadata", "inline_discriminator"])' in schema
    assert re.search(
        r"export const VariantOptionSchema = z\.object\(\{\n(?P<body>(?:  .+\n)+)\}\)\.strict\(\);",
        schema,
    )
    assert re.search(
        r"export const VariantStateSchema = z\.object\(\{\n(?P<body>(?:  .+\n)+)\}\)\.strict\(\);",
        schema,
    )
    assert '"model_field"' not in schema
    assert "model_field" not in bundled_js


def test_frontend_node_schema_strictly_covers_backend_node_kinds() -> None:
    schema = (ROOT / "frontend" / "src" / "api" / "schemas.ts").read_text(
        encoding="utf-8"
    )
    backend_nodes = (ROOT / "src" / "pydantic_studio" / "tree" / "nodes.py").read_text(
        encoding="utf-8"
    )

    backend_kinds = set(re.findall(r'kind: Literal\["([^"]+)"\]', backend_nodes))
    frontend_kinds = set(re.findall(r'kind: z\.literal\("([^"]+)"\)', schema))

    assert frontend_kinds == backend_kinds
    assert "UnknownNodeSchema" not in schema
    assert "[extra: string]" not in schema


def test_frontend_tree_schema_rejects_extra_top_level_fields() -> None:
    schema = (ROOT / "frontend" / "src" / "api" / "schemas.ts").read_text(
        encoding="utf-8"
    )

    node_base = re.search(
        r"const NodeBase = z\.object\(\{\n(?P<body>(?:  .+\n)+)\}\)\.strict\(\);",
        schema,
    )
    assert node_base is not None
    assert "error: z.string().nullable()," in node_base.group("body")

    match = re.search(
        r"export const FormTreeSchema = z\.object\(\{(?P<body>.*?)\}\)\.strict\(\);",
        schema,
        re.DOTALL,
    )
    assert match is not None
    assert "readonly_paths: z.array(z.string())," in match.group("body")
    assert ".passthrough()" not in schema
    assert ".strip()" not in schema
    assert "tolerate extra top-level fields" not in schema


def test_frontend_tree_schema_requires_readonly_paths() -> None:
    schema = (ROOT / "frontend" / "src" / "api" / "schemas.ts").read_text(
        encoding="utf-8"
    )

    assert "readonly_paths: z.array(z.string())," in schema
    assert "readonly_paths: z.array(z.string()).default([])" not in schema


def test_frontend_float_schema_accepts_non_finite_wire_strings() -> None:
    schema = (ROOT / "frontend" / "src" / "api" / "schemas.ts").read_text(
        encoding="utf-8"
    )
    float_field = (
        ROOT / "frontend" / "src" / "components" / "form" / "fields" / "FloatField.tsx"
    ).read_text(encoding="utf-8")

    assert 'z.enum(["NaN", "Infinity", "-Infinity"])' in schema
    assert "parseFloatWireValue" in float_field
    assert 'value: trimmed' in float_field


def test_frontend_mutation_response_schema_validates_full_envelope() -> None:
    mutations = (ROOT / "frontend" / "src" / "api" / "mutations.ts").read_text(
        encoding="utf-8"
    )

    assert "MutationErrorResponseSchema.parse(await response.json())" in mutations
    assert "MutationResponseSchema.parse(raw)" in mutations
    assert "body.detail ??" not in mutations
    assert "validation: raw.validation" not in mutations
    assert "mutation_result: raw.mutation_result" not in mutations
    assert re.search(
        r"const MutationErrorResponseSchema = z\.object\(\{(?P<body>.*?)\}\)\.strict\(\);",
        mutations,
        re.DOTALL,
    )
    assert re.search(
        r"const ValidationErrorSchema = z\.object\(\{(?P<body>.*?)\}\)\.strict\(\);",
        mutations,
        re.DOTALL,
    )
    assert re.search(
        r"const ValidationEnvelopeSchema = z\.object\(\{(?P<body>.*?)\}\)\.strict\(\);",
        mutations,
        re.DOTALL,
    )
    assert re.search(
        r"const MutationResultSchema = z\.object\(\{(?P<body>.*?)\}\)\.strict\(\);",
        mutations,
        re.DOTALL,
    )
    assert re.search(
        r"const MutationResponseSchema = z\.object\(\{(?P<body>.*?)\}\)\.strict\(\);",
        mutations,
        re.DOTALL,
    )


def test_frontend_submit_and_cancel_schemas_validate_http_responses() -> None:
    submit = (ROOT / "frontend" / "src" / "api" / "submit.ts").read_text(
        encoding="utf-8"
    )

    assert "SubmitFailureResponseSchema.parse(await response.json())" in submit
    assert "SubmitSuccessResponseSchema.parse(await response.json())" in submit
    assert "CancelResponseSchema.parse(await response.json())" in submit
    assert "as { ok?: boolean; errors?: SubmitError[] }" not in submit
    assert "body.errors ?? []" not in submit
    assert re.search(
        r"const SubmitErrorSchema = z\.object\(\{(?P<body>.*?)\}\)\.strict\(\);",
        submit,
        re.DOTALL,
    )
    assert re.search(
        r"const SubmitFailureResponseSchema = z\.object\(\{(?P<body>.*?)\}\)\.strict\(\);",
        submit,
        re.DOTALL,
    )
    assert re.search(
        r"const SubmitSuccessResponseSchema = z\.object\(\{(?P<body>.*?)\}\)\.strict\(\);",
        submit,
        re.DOTALL,
    )
    assert re.search(
        r"const CancelResponseSchema = z\.object\(\{(?P<body>.*?)\}\)\.strict\(\);",
        submit,
        re.DOTALL,
    )


def test_frontend_sends_heartbeat_while_web_session_is_open() -> None:
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "HEARTBEAT_INTERVAL_MS = 10_000" in app
    assert 'studioUrl("/api/heartbeat")' in app
    assert "void sendHeartbeat();" in app
    assert "window.setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS)" in app
    assert "window.clearInterval(intervalId)" in app
