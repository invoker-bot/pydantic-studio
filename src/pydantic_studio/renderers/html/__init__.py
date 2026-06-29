"""HTML renderer for pydantic-studio.

A local FastAPI app that serves an HTMX-driven editor in the browser.
"""

from __future__ import annotations

from pydantic_studio.renderers.html.server import (
    StudioServer,
    mount_html_app,
    run_html_app,
)

__all__ = ["StudioServer", "mount_html_app", "run_html_app"]
