"""StudioServer — FastAPI app for the HTML renderer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    from pydantic_studio.tree.nodes import FormTree

_HERE = Path(__file__).parent
_TEMPLATES_DIR = _HERE / "templates"
_STATIC_DIR = _HERE / "static"


class StudioServer:
    """FastAPI app + state for the HTML renderer.

    Args:
        tree: the FormTree to edit.
        save_path: optional path to write to on /submit.
    """

    def __init__(
        self,
        tree: FormTree,
        save_path: str | Path | None = None,
    ) -> None:
        self.tree = tree
        self.save_path = Path(save_path) if save_path is not None else None
        self.app = FastAPI()
        self.templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
        # Lifecycle state.
        self.submitted = False
        self.cancelled = False
        self.last_heartbeat_ts: float = 0.0
        self._mount_static()
        self._register_routes()

    def _mount_static(self) -> None:
        if _STATIC_DIR.exists():
            self.app.mount(
                "/static",
                StaticFiles(directory=str(_STATIC_DIR)),
                name="static",
            )

    def _register_routes(self) -> None:
        from pydantic_studio.renderers.html import routes

        routes.register(self.app, self)

    def render_index(self, request: Request) -> HTMLResponse:
        """Render the index page."""
        from pydantic_studio.renderers.html.render import (
            initial_value_str,
            list_groups,
            list_root_fields,
            render_yaml_preview,
        )

        schema_name = (
            self.tree.schema_name.split(":")[-1]
            if ":" in self.tree.schema_name
            else self.tree.schema_name
        )
        return self.templates.TemplateResponse(
            request,
            "base.html.jinja",
            {
                "schema_name": schema_name,
                "tree": self.tree,
                "fields": list_root_fields(self.tree),
                "groups": list_groups(self.tree),
                "preview": render_yaml_preview(self.tree),
                "initial_value_str": initial_value_str,
            },
        )


def run_html_app(tree: FormTree, save_path: str | Path | None = None) -> None:
    """Launch the HTML renderer synchronously. Blocks until /submit or /cancel."""
    import socket
    import webbrowser

    import uvicorn

    studio_server = StudioServer(tree=tree, save_path=save_path)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    url = f"http://127.0.0.1:{port}/"
    webbrowser.open(url)
    uvicorn.run(studio_server.app, host="127.0.0.1", port=port, log_level="warning")
