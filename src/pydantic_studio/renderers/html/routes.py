"""HTTP route handlers for the HTML renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

from fastapi import Request  # noqa: TC002 (FastAPI introspects this at runtime)
from fastapi.responses import HTMLResponse, PlainTextResponse

if TYPE_CHECKING:
    from fastapi import FastAPI

    from pydantic_studio.renderers.html.server import StudioServer


def _parse_for_kind(kind: str, raw: str) -> tuple[bool, Any]:
    """Same parser as the Textual renderer's TextInputEditor."""
    raw = raw.strip()
    if raw == "":
        return True, None

    try:
        if kind == "string":
            return True, raw
        if kind == "int":
            return True, int(raw)
        if kind == "float":
            return True, float(raw)
        if kind == "decimal":
            from decimal import Decimal

            return True, Decimal(raw)
        if kind == "datetime":
            from datetime import datetime

            return True, datetime.fromisoformat(raw)
        if kind == "date":
            from datetime import date

            return True, date.fromisoformat(raw)
        if kind == "time":
            from datetime import time

            return True, time.fromisoformat(raw)
        if kind == "timedelta":
            from datetime import timedelta

            from pydantic import TypeAdapter

            return True, TypeAdapter(timedelta).validate_python(raw)
        if kind in ("ip_address", "ip_network", "url", "email", "path", "pattern"):
            return True, raw
        if kind == "uuid":
            from uuid import UUID

            return True, UUID(raw)
        if kind == "secret":
            return True, raw
        if kind == "bytes":
            return True, bytes.fromhex(raw)
        if kind == "bool":
            return True, raw.lower() in ("true", "1", "on", "yes")
        if kind == "any":
            # ``typing.Any`` carries arbitrary primitives or simple
            # collections — try parsing as JSON literal first (covers
            # numbers, booleans, null, arrays, objects in one path);
            # otherwise treat the input as a plain string.
            import json

            try:
                return True, json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return True, raw
    except (ValueError, TypeError):
        return False, None
    return False, None


def _resolve_node(server: StudioServer, path: str) -> Any:
    """Walk path segments to find the target node. Returns None on miss."""
    from pydantic_studio.tree.nodes import GroupNode

    if not path:
        return None
    node: Any = server.tree.root
    for seg in path.split("."):
        if isinstance(node, GroupNode):
            child = node.find(seg)
            if child is None:
                return None
            node = child
        else:
            return None
    return node


def _within_constraints(node: Any, value: Any) -> bool:
    """Check numeric constraints (ge/le/gt/lt/multiple_of) declared on the
    node. ``validate_value`` only enforces type for IntNode/FloatNode/etc.;
    bounds are otherwise checked at submit time. The HTML route enforces
    them eagerly so a bad input doesn't poison the tree.
    """
    if value is None:
        return True
    for attr, op in (
        ("ge", lambda v, b: v >= b),
        ("le", lambda v, b: v <= b),
        ("gt", lambda v, b: v > b),
        ("lt", lambda v, b: v < b),
    ):
        bound = getattr(node, attr, None)
        if bound is not None and not op(value, bound):
            return False
    multiple_of = getattr(node, "multiple_of", None)
    return not (multiple_of is not None and value % multiple_of != 0)


async def _read_form_value(request: Request, key: str = "value") -> str:
    """Decode an ``application/x-www-form-urlencoded`` body without pulling
    in ``python-multipart``. HTMX form posts use this content-type by default.
    """
    body = await request.body()
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    values = parsed.get(key, [""])
    return values[0] if values else ""


async def _read_form_field(request: Request, field: str) -> str:
    """Read a single form field from urlencoded body — avoids python-multipart."""
    body = await request.body()
    parsed = parse_qs(body.decode("utf-8"))
    values = parsed.get(field, [""])
    return values[0] if values else ""


def _render_seq_partial(server: StudioServer, path: str) -> HTMLResponse:
    """Re-render <div id="seq-{path}"> after add/remove."""
    node = _resolve_node(server, path)
    if node is None:
        return HTMLResponse(content="<pre>not found</pre>")
    parts = [f'<div id="seq-{path}">']
    parts.append(
        f'<button hx-post="/seq/{path}/add" '
        f'hx-target="#seq-{path}" hx-swap="outerHTML">+ Add</button>'
    )
    for i in range(len(node.items)):
        parts.append(
            f'<div class="seq-row">'
            f"<span>[{i}] {node.items[i].kind}</span>"
            f'<button hx-post="/seq/{path}/remove?index={i}" '
            f'hx-target="#seq-{path}" hx-swap="outerHTML">remove</button>'
            "</div>"
        )
    parts.append("</div>")
    return HTMLResponse(content="".join(parts))


def _render_map_partial(server: StudioServer, path: str) -> HTMLResponse:
    node = _resolve_node(server, path)
    if node is None:
        return HTMLResponse(content="<pre>not found</pre>")
    parts = [f'<div id="map-{path}">']
    parts.append(
        f'<button hx-post="/map/{path}/add" '
        f'hx-target="#map-{path}" hx-swap="outerHTML">+ Add Entry</button>'
    )
    for i, (k_node, v_node) in enumerate(node.entries):
        parts.append(
            f'<div class="map-row">'
            f"<span>{k_node.value} → {v_node.value}</span>"
            f'<button hx-post="/map/{path}/remove?index={i}" '
            f'hx-target="#map-{path}" hx-swap="outerHTML">remove</button>'
            "</div>"
        )
    parts.append("</div>")
    return HTMLResponse(content="".join(parts))


def register(app: FastAPI, server: StudioServer) -> None:
    """Wire all routes onto the FastAPI app."""

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return server.render_index(request)

    @app.post("/field/{path:path}", response_class=HTMLResponse)
    async def field_update(path: str, request: Request) -> HTMLResponse:
        from pydantic_studio.renderers.html.render import render_yaml_preview

        node = _resolve_node(server, path)
        if node is None:
            return HTMLResponse(content="<pre>field not found</pre>", status_code=404)

        value = await _read_form_value(request)
        kind = node.kind
        parsed_value: Any
        if kind == "enum":
            for choice_name, member in node.choices:
                if choice_name == value:
                    parsed_value = member
                    break
            else:
                return HTMLResponse(content=render_yaml_preview(server.tree))
        elif kind == "literal":
            parsed_value = None
            for c in node.choices:
                if str(c) == value:
                    parsed_value = c
                    break
            if parsed_value is None:
                return HTMLResponse(content=render_yaml_preview(server.tree))
        else:
            ok, parsed_value = _parse_for_kind(kind, value)
            if not ok:
                return HTMLResponse(content=render_yaml_preview(server.tree))
            if not _within_constraints(node, parsed_value):
                return HTMLResponse(content=render_yaml_preview(server.tree))

        # set_value handles validation; if it fails, we still return preview
        # so the user sees current state (errors should be surfaced via OOB
        # swap or status bar in a future polish pass).
        server.tree.set_value(path, parsed_value)
        return HTMLResponse(content=render_yaml_preview(server.tree))

    @app.post("/seq/{path:path}/add", response_class=HTMLResponse)
    async def seq_add(path: str) -> HTMLResponse:
        server.tree.add_item(path)
        return _render_seq_partial(server, path)

    @app.post("/seq/{path:path}/remove", response_class=HTMLResponse)
    async def seq_remove(path: str, index: int = 0) -> HTMLResponse:
        server.tree.remove_item(path, index)
        return _render_seq_partial(server, path)

    @app.post("/map/{path:path}/add", response_class=HTMLResponse)
    async def map_add(path: str) -> HTMLResponse:
        node = _resolve_node(server, path)
        if node is None:
            return HTMLResponse(content="<pre>field not found</pre>", status_code=404)
        existing_keys = {
            getattr(k_node, "value", "") for k_node, _ in node.entries
        }
        i = 0
        while f"key{i}" in existing_keys:
            i += 1
        server.tree.add_entry(path, key=f"key{i}")
        return _render_map_partial(server, path)

    @app.post("/map/{path:path}/remove", response_class=HTMLResponse)
    async def map_remove(path: str, index: int = 0) -> HTMLResponse:
        server.tree.remove_entry(path, index)
        return _render_map_partial(server, path)

    @app.post("/union/{path:path}/select", response_class=HTMLResponse)
    async def union_select(path: str, request: Request) -> HTMLResponse:
        from pydantic_studio.renderers.html.render import render_yaml_preview

        # Read variant from form body using the same urlencoded helper as /field.
        variant = await _read_form_field(request, "variant")
        node = _resolve_node(server, path)
        if node is None:
            return HTMLResponse(content="<pre>field not found</pre>", status_code=404)
        for i, name in enumerate(node.variant_type_names):
            if name == variant:
                server.tree.select_variant(path, i)
                break
        return HTMLResponse(content=render_yaml_preview(server.tree))

    @app.post("/submit", response_class=HTMLResponse)
    async def submit() -> HTMLResponse:
        from pydantic import ValidationError

        from pydantic_studio import save_yaml
        from pydantic_studio.exceptions import ValidationFailedError

        try:
            server.tree.to_instance()
        except (ValidationError, ValidationFailedError) as e:
            return HTMLResponse(
                content=f"<pre>Validation failed: {e}</pre>",
                status_code=200,
            )
        if server.save_path is not None:
            save_yaml(server.tree, server.save_path)
        server.submitted = True
        return HTMLResponse(
            content="<h2>Done — you can close this tab.</h2>",
        )

    @app.post("/cancel", response_class=HTMLResponse)
    async def cancel() -> HTMLResponse:
        server.cancelled = True
        return HTMLResponse(
            content="<h2>Cancelled — you can close this tab.</h2>",
        )

    @app.get("/heartbeat", response_class=PlainTextResponse)
    async def heartbeat() -> PlainTextResponse:
        import time

        server.last_heartbeat_ts = time.time()
        return PlainTextResponse(content="ok")

    # ----- JSON API (Phase 1 of the shadcn web redesign) -----
    from fastapi.responses import JSONResponse

    from pydantic_studio.renderers.html.serialize import (
        dispatch_mutation,
        tree_to_json,
        validation_envelope,
    )

    @app.get("/api/tree", response_class=JSONResponse)
    async def api_tree() -> JSONResponse:
        return JSONResponse(content=tree_to_json(server.tree))

    @app.post("/api/mutations", response_class=JSONResponse)
    async def api_mutations(request: Request) -> JSONResponse:
        mutation = await request.json()
        result = dispatch_mutation(server.tree, mutation)
        # Unknown / malformed op -> 400 so the client knows it's a request
        # bug, not a state issue. Validation failures of valid ops keep
        # 200 (the tree is untouched, ``validation`` reports what failed).
        # T8 introduced a second error family with prefix "mutation failed: "
        # for malformed-request exceptions (KeyError/ValueError/TypeError);
        # only the "unknown op" family promotes to 400.
        if not result.ok and any("unknown op" in err for err in result.errors):
            return JSONResponse(
                status_code=400, content={"detail": "; ".join(result.errors)}
            )
        # Spec §5.2: a rejected mutation surfaces in ``validation.errors``.
        # The static envelope from ``validation_envelope`` reports whether
        # ``to_instance()`` would succeed — but a failed ``set_value`` leaves
        # the prior valid value in place, so the envelope alone would miss
        # the rejection. Fold the mutation errors back in so the client sees
        # ``validation.ok = false`` after any failed op (matching the
        # ``dispatch_mutation`` docstring's contract).
        validation = validation_envelope(server.tree)
        if not result.ok:
            mutation_path = str(mutation.get("path", ""))
            validation = {
                "ok": False,
                "errors": [
                    {"path": mutation_path, "message": err}
                    for err in result.errors
                ]
                + list(validation["errors"]),
            }
        return JSONResponse(
            content={
                "tree": tree_to_json(server.tree),
                "validation": validation,
                "mutation_result": {"ok": result.ok, "errors": list(result.errors)},
            }
        )

    @app.post("/api/submit", response_class=JSONResponse)
    async def api_submit() -> JSONResponse:
        from pydantic import ValidationError

        from pydantic_studio import save_yaml
        from pydantic_studio.exceptions import ValidationFailedError

        try:
            server.tree.to_instance()
        except (ValidationError, ValidationFailedError):
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "errors": validation_envelope(server.tree)["errors"],
                },
            )
        if server.save_path is not None:
            save_yaml(server.tree, server.save_path)
        server.submitted = True
        return JSONResponse(content={"ok": True})

    @app.post("/api/cancel", response_class=JSONResponse)
    async def api_cancel() -> JSONResponse:
        server.cancelled = True
        return JSONResponse(content={"ok": True})

    @app.get("/api/heartbeat", response_class=JSONResponse)
    async def api_heartbeat() -> JSONResponse:
        import time as _t

        server.last_heartbeat_ts = _t.time()
        return JSONResponse(content={"ok": True})
