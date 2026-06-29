"""StudioServer — FastAPI app for the HTML renderer."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pydantic_studio.session import EditSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from fastapi import Request

    from pydantic_studio.tree.nodes import FormTree

_HERE = Path(__file__).parent
_TEMPLATES_DIR = _HERE / "templates"
_STATIC_DIR = _HERE / "static"
_SPA_INDEX = _STATIC_DIR / "dist" / "index.html"


def normalize_base_path(base_path: str) -> str:
    stripped = base_path.strip()
    if stripped in {"", "/"}:
        return ""
    return "/" + stripped.strip("/")


class StudioServer:
    """FastAPI app + state for the HTML renderer.

    Args:
        tree: the FormTree to edit.
        save_path: optional path to write to on /submit.
    """

    def __init__(
        self,
        tree: FormTree | None = None,
        save_path: str | Path | None = None,
        heartbeat_timeout_seconds: float = 30.0,
        readonly_paths: Iterable[str] = (),
        session: EditSession | None = None,
        base_path: str = "",
    ) -> None:
        if session is None:
            if tree is None:
                raise TypeError("StudioServer requires either tree or session")
            session = EditSession(
                tree=tree,
                save_path=save_path,
                readonly_paths=readonly_paths,
            )
        self.session = session
        self.base_path = normalize_base_path(base_path)
        self.app = FastAPI()
        self.templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
        self.last_heartbeat_ts: float = 0.0
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._mount_static()
        self._register_routes()

    @property
    def tree(self) -> FormTree:
        return self.session.tree

    @property
    def save_path(self) -> Path | None:
        return self.session.save_path

    @property
    def readonly_paths(self) -> frozenset[str]:
        return self.session.readonly_paths

    @property
    def submitted(self) -> bool:
        return self.session.submitted

    @property
    def cancelled(self) -> bool:
        return self.session.cancelled

    def _check_heartbeat_timeout(self) -> None:
        """Mark cancelled if heartbeat is older than the timeout.

        last_heartbeat_ts == 0.0 means no heartbeat received yet — don't
        auto-cancel (user may still be loading the page).
        """
        import time

        if self.last_heartbeat_ts == 0.0:
            return
        elapsed = time.time() - self.last_heartbeat_ts
        if elapsed > self.heartbeat_timeout_seconds:
            self.session.cancel()

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

    def render_spa_index(self) -> HTMLResponse:
        """Serve the built SPA index with runtime mount-path config."""
        index = _SPA_INDEX.read_text(encoding="utf-8")
        if self.base_path:
            index = index.replace(
                'src="/static/dist/',
                f'src="{self.base_path}/static/dist/',
            )
            index = index.replace(
                'href="/static/dist/',
                f'href="{self.base_path}/static/dist/',
            )
        config = json.dumps({"basePath": self.base_path})
        script = (
            "<script>"
            f"window.__PYDANTIC_STUDIO__ = {html.escape(config, quote=False)};"
            "</script>"
        )
        index = index.replace("</head>", f"    {script}\n  </head>")
        return HTMLResponse(index)

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


def mount_html_app(
    host_app,
    path: str,
    *,
    tree: FormTree | None = None,
    save_path: str | Path | None = None,
    heartbeat_timeout_seconds: float = 30.0,
    readonly_paths: Iterable[str] = (),
    session: EditSession | None = None,
) -> StudioServer:
    """Mount pydantic-studio into a Starlette-compatible ASGI host."""
    mount = getattr(host_app, "mount", None)
    if mount is None:
        raise TypeError("mount_html_app requires a host app with mount(path, app)")
    base_path = normalize_base_path(path)
    server = StudioServer(
        tree=tree,
        save_path=save_path,
        heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        readonly_paths=readonly_paths,
        session=session,
        base_path=base_path,
    )
    mount(base_path or "/", server.app)
    return server


def run_html_app(
    tree: FormTree,
    save_path: str | Path | None = None,
    heartbeat_timeout_seconds: float = 30.0,
    readonly_paths: Iterable[str] = (),
):
    """Launch the HTML renderer. Blocks until /submit, /cancel, or heartbeat timeout.

    Prints the editor URL to stdout before opening the browser so the user
    can copy/paste it (e.g. when the auto-open fails or the terminal lives
    on a different host than the desktop). When the server exits, prints
    a one-line summary indicating whether the form was saved or cancelled.

    Returns the session's :class:`~pydantic_studio.outcome.EditOutcome` —
    the same contract as the TUI's ``run_app``: persist only on
    ``outcome.submitted`` (heartbeat timeouts and Cancel both come back
    ``cancelled``).
    """
    import asyncio
    import socket
    import sys
    import webbrowser

    import uvicorn

    from pydantic_studio.outcome import EditOutcome

    studio_server = StudioServer(
        tree=tree,
        save_path=save_path,
        heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        readonly_paths=readonly_paths,
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    url = f"http://127.0.0.1:{port}/"

    print(f"\npydantic-studio editor: {url}", file=sys.stdout)
    if save_path is not None:
        print(
            f"  edit in the browser and click Save; output will be written to {save_path}",
            file=sys.stdout,
        )
    else:
        print(
            "  edit in the browser and click Save to commit your changes",
            file=sys.stdout,
        )
    print(
        "  the terminal will return automatically when you save or cancel.\n",
        file=sys.stdout,
        flush=True,
    )

    webbrowser.open(url)

    config = uvicorn.Config(
        studio_server.app, host="127.0.0.1", port=port, log_level="warning"
    )
    server = uvicorn.Server(config)

    async def watcher() -> None:
        while not server.should_exit:
            await asyncio.sleep(1.0)
            studio_server._check_heartbeat_timeout()
            if studio_server.session.done:
                server.should_exit = True

    async def main() -> None:
        watcher_task = asyncio.create_task(watcher())
        try:
            await server.serve()
        finally:
            watcher_task.cancel()

    asyncio.run(main())

    outcome = studio_server.session.outcome
    if outcome is not None and outcome.submitted:
        if save_path is not None:
            print(f"saved to {save_path}", file=sys.stdout)
        else:
            print("submitted (no save path configured)", file=sys.stdout)
        return outcome
    print("cancelled", file=sys.stdout)
    return EditOutcome(status="cancelled")
