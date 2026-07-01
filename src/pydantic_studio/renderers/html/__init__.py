"""HTML renderer for pydantic-studio.

A local FastAPI app that serves the bundled React SPA and JSON API.
"""

from __future__ import annotations

from pydantic_studio.renderers.html.embed import StudioEmbedManager, mount_embed_app
from pydantic_studio.renderers.html.server import (
    StudioServer,
    mount_html_app,
    run_html_app,
)

__all__ = [
    "StudioEmbedManager",
    "StudioServer",
    "mount_embed_app",
    "mount_html_app",
    "run_html_app",
]
