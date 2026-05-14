"""Dev-loop helper: run StudioServer on a fixed port so Vite's
``server.proxy["/api"] -> http://127.0.0.1:8000`` (in ``vite.config.ts``)
can actually reach the backend.

The packaged ``run_html_app`` (and the ``examples/*.py web`` flows)
binds an ephemeral port chosen by the OS - great for the end-user
experience (no port clashes, browser auto-opens) but useless for a
fixed-port dev proxy. This helper exists to fill the gap.

Usage:

    uv run python frontend/scripts/dev-backend.py

Then in another terminal:

    cd frontend && pnpm dev

And open ``http://localhost:5173`` (Vite's port; the proxy forwards
``/api/*`` to this script's :8000).

Swap the ``Demo`` schema below for any BaseModel you want to drive the
SPA against during local development.
"""

from __future__ import annotations

import uvicorn
from pydantic import BaseModel, Field

from pydantic_studio import StudioServer, build_form_tree


class Demo(BaseModel):
    """Tiny schema so the SPA has something to render. Edit to taste."""

    name: str = Field(default="dev", description="Service identifier")
    workers: int = Field(default=4, description="Worker process count", ge=1, le=64)


def main() -> None:
    tree = build_form_tree(Demo, existing={"name": "frontend-dev", "workers": 8})
    server = StudioServer(tree=tree, save_path=None)
    uvicorn.run(server.app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
