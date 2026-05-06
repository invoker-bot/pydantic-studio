"""HTTP route handlers for the HTML renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

from fastapi import Request  # noqa: TC002 (FastAPI introspects this at runtime)
from fastapi.responses import HTMLResponse

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
