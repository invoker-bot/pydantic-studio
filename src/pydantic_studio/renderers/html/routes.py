"""HTTP route handlers for the HTML renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request  # noqa: TC002 (FastAPI introspects this at runtime)
from fastapi.responses import HTMLResponse

if TYPE_CHECKING:
    from fastapi import FastAPI

    from pydantic_studio.renderers.html.server import StudioServer


def register(app: FastAPI, server: StudioServer) -> None:
    """Wire all routes onto the FastAPI app."""

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return server.render_index(request)
