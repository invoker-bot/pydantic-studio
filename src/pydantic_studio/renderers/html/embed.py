"""StudioEmbedManager — multi-session embed layer for hosted config editors.

Built on top of the single-session embed foundation (:class:`EditSession`,
:class:`~pydantic_studio.renderers.html.server.StudioServer`, and base-path
plumbing). A single mounted ASGI app manages many concurrent
:class:`EditSession` instances, each addressed by ``/s/<id>/...``, so a host
(e.g. a config workbench serving multiple operators / tabs) can run more than
one edit at a time without spinning up a process per session.

Load-bearing points (see
``docs/superpowers/plans/2026-07-01-multi-session-embed-manager.md`` for the
full design rationale):

- Each session's :class:`StudioServer` is constructed directly with the
  **full external base path** (``<host prefix>/s/<id>``), not via
  :func:`~pydantic_studio.renderers.html.server.mount_html_app` — that helper
  derives ``base_path`` from the *mount* path, which would only ever be
  ``/s/<id>`` and would lose the host's own external prefix. Losing that
  prefix breaks the frontend's ``studioUrl()`` (asset + API URLs would 404
  once actually served behind the host's prefix).
- ``self.app`` (the manager's own ASGI app) never registers a catch-all
  route, so sessions mounted after the app has already started serving
  requests remain reachable.
- Heartbeat-triggered auto-cancel is a `run_html_app`-only behavior (the
  watcher loop lives there, not on ``StudioServer`` itself). Embedded
  sessions never get that watcher, so they never auto-cancel on their own;
  the manager instead runs an idle-TTL sweep that reads
  ``server.last_heartbeat_ts`` (kept fresh by ``/api/heartbeat``) and closes
  sessions that have gone quiet for longer than ``idle_ttl_seconds``.
- ``get_session(sid)`` returns the live :class:`EditSession` (usable at any
  time, including while the session is still active and ``outcome is
  None``) — this is deliberately distinct from ``get_outcome``, since
  :class:`~pydantic_studio.outcome.EditOutcome` carries no tree and an
  active embedded session's outcome is `None` until the host closes it.
- ``reopen_session(sid)`` resets ``session.outcome`` to `None` so
  ``/api/mutations`` (which 409s once an outcome is set) becomes usable
  again after a host-side business validation failure post-submit.
  ``EditSession.submit()`` itself is left unchanged — it still sets a
  terminal outcome on a clean validation, exactly as it does outside embed
  mode.
"""

from __future__ import annotations

import secrets
import time
from typing import TYPE_CHECKING

from fastapi import FastAPI

from pydantic_studio.renderers.html.server import StudioServer, normalize_base_path
from pydantic_studio.session import EditSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from starlette.routing import BaseRoute

    from pydantic_studio.outcome import EditOutcome
    from pydantic_studio.tree.nodes import FormTree

__all__ = ["StudioEmbedManager", "mount_embed_app"]

_DEFAULT_IDLE_TTL_SECONDS = 900.0


class StudioEmbedManager:
    """Manage multiple concurrent :class:`EditSession` instances behind one mount.

    Args:
        host_external_path: the *full* external path this manager will be
            mounted at on the host app (e.g. ``"/config-studio"``). Session
            base paths are derived from this, not from wherever
            ``self.app`` happens to be mounted, so the frontend always sees
            the true externally-visible prefix.
        idle_ttl_seconds: sessions whose ``last_heartbeat_ts`` is older than
            this are eligible for :meth:`sweep_idle_sessions` to close.
            ``None`` disables the idle sweep entirely.
    """

    def __init__(
        self,
        host_external_path: str,
        *,
        idle_ttl_seconds: float | None = _DEFAULT_IDLE_TTL_SECONDS,
    ) -> None:
        self.host_external_path = normalize_base_path(host_external_path)
        self.idle_ttl_seconds = idle_ttl_seconds
        self.app = FastAPI()
        self._sessions: dict[str, tuple[StudioServer, BaseRoute]] = {}

    def create_session(
        self,
        *,
        tree: FormTree,
        save_path: str | None = None,
        readonly_paths: Iterable[str] = (),
    ) -> str:
        """Create a new session, mount it, and return its session id."""
        session_id = secrets.token_hex(16)
        session = EditSession(
            tree=tree,
            save_path=save_path,
            readonly_paths=readonly_paths,
        )
        base_path = f"{self.host_external_path}/s/{session_id}"
        server = StudioServer(session=session, base_path=base_path)
        self.app.mount(f"/s/{session_id}", server.app)
        route = self.app.router.routes[-1]
        self._sessions[session_id] = (server, route)
        return session_id

    def get_session(self, session_id: str) -> EditSession:
        """Return the live :class:`EditSession` for ``session_id``.

        Usable at any time — including while the session is still active
        and ``outcome is None`` — unlike :meth:`get_outcome`, which only
        reports terminal state and never carries the tree.
        """
        return self._sessions[session_id][0].session

    def get_outcome(self, session_id: str) -> EditOutcome | None:
        """Read-only status query: `None` while active, else submitted/cancelled."""
        return self._sessions[session_id][0].session.outcome

    def reopen_session(self, session_id: str) -> None:
        """Clear a terminal outcome so ``/api/mutations`` stops 409ing.

        Used after the host's own business validation rejects a submitted
        tree: the studio-level submit already validated and completed
        cleanly, so re-editing needs the session pulled back out of its
        terminal state.
        """
        self._sessions[session_id][0].session.outcome = None

    def close_session(self, session_id: str) -> None:
        """Tear down a session and unmount its routes."""
        _server, route = self._sessions.pop(session_id)
        self.app.router.routes.remove(route)

    def sweep_idle_sessions(self) -> None:
        """Close sessions whose heartbeat has gone stale past the idle TTL.

        No-op when ``idle_ttl_seconds`` is `None`. Sessions that have never
        received a heartbeat (``last_heartbeat_ts == 0.0``) are left alone —
        mirrors :meth:`StudioServer._check_heartbeat_timeout`'s "still
        loading" grace behavior.
        """
        if self.idle_ttl_seconds is None:
            return
        now = time.time()
        stale = [
            session_id
            for session_id, (server, _route) in self._sessions.items()
            if server.last_heartbeat_ts != 0.0
            and (now - server.last_heartbeat_ts) > self.idle_ttl_seconds
        ]
        for session_id in stale:
            self.close_session(session_id)


def mount_embed_app(
    host_app,
    path: str,
    *,
    idle_ttl_seconds: float | None = _DEFAULT_IDLE_TTL_SECONDS,
) -> StudioEmbedManager:
    """Mount a :class:`StudioEmbedManager` onto a Starlette-compatible ASGI host."""
    mount = getattr(host_app, "mount", None)
    if mount is None:
        raise TypeError("mount_embed_app requires a host app with mount(path, app)")
    prefix = normalize_base_path(path)
    manager = StudioEmbedManager(prefix, idle_ttl_seconds=idle_ttl_seconds)
    mount(prefix or "/", manager.app)
    return manager
