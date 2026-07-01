"""HTTP route handlers for the React-backed HTML renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from fastapi import Request  # noqa: TC002 (FastAPI introspects this at runtime)
from fastapi.responses import HTMLResponse, JSONResponse

from pydantic_studio.tree.paths import paths_overlap as _paths_overlap

if TYPE_CHECKING:
    from fastapi import FastAPI

    from pydantic_studio.renderers.html.server import StudioServer

_PATH_MUTATION_OPS = {
    "set_value",
    "add_item",
    "insert_item",
    "remove_item",
    "move_item",
    "add_entry",
    "remove_entry",
    "rename_key",
    "select_variant",
}
_READONLY_MESSAGE = "read-only — value is managed by the caller"
_MISSING_READONLY_PATH = object()


def _tree_payload(server: StudioServer) -> dict[str, object]:
    from pydantic_studio.renderers.html.serialize import tree_to_json

    payload = tree_to_json(server.tree)
    history = payload["history"]
    if isinstance(history, dict):
        history["can_undo"] = bool(history["can_undo"]) and (
            _readonly_history_error(server, "undo") is None
        )
        history["can_redo"] = bool(history["can_redo"]) and (
            _readonly_history_error(server, "redo") is None
        )
    payload["readonly_paths"] = sorted(server.readonly_paths)
    return payload


def _readonly_mutation_error(
    server: StudioServer, mutation: dict[str, Any]
) -> str | None:
    op = mutation.get("op")
    if op in {"undo", "redo"}:
        return _readonly_history_error(server, op)
    if op == "select_root_variant" and server.readonly_paths:
        return f"root variant is {_READONLY_MESSAGE}"
    if op not in _PATH_MUTATION_OPS:
        return None
    path = mutation.get("path")
    if not isinstance(path, str):
        return None
    if any(_paths_overlap(path, readonly) for readonly in server.readonly_paths):
        return f"{path} is {_READONLY_MESSAGE}"
    return None


def _readonly_history_error(server: StudioServer, op: str) -> str | None:
    if not server.readonly_paths:
        return None
    target_root = _history_target_root(server.tree, op)
    if target_root is None:
        return None
    for readonly_path in sorted(server.readonly_paths):
        current = _readonly_path_state(server.tree, server.tree.root, readonly_path)
        target = _readonly_path_state(server.tree, target_root, readonly_path)
        if current != target:
            return f"{op} would modify read-only path {readonly_path!r}"
    return None


def _history_target_root(tree: Any, op: str) -> Any | None:
    from pydantic_studio.tree import snapshots as _snap

    if op == "undo":
        if tree.cursor == 0:
            return None
        return _snap.restore(tree.snapshots[tree.cursor - 1])
    if op == "redo":
        if tree.cursor + 1 >= len(tree.snapshots):
            return None
        return _snap.restore(tree.snapshots[tree.cursor + 1])
    return None


def _readonly_path_state(tree: Any, root: Any, path: str) -> Any:
    try:
        node = _resolve_path_from_root(tree, root, path)
    except Exception:
        return _MISSING_READONLY_PATH
    return node.model_dump(mode="json")


def _resolve_path_from_root(tree: Any, root: Any, path: str) -> Any:
    from pydantic_studio.tree.paths import Path

    path_obj = Path.parse(path)
    node = root
    for segment in path_obj.segments:
        node = tree._descend(node, segment)
    return node


def _mutation_error_path(mutation: dict[str, Any]) -> str:
    path = mutation.get("path")
    return path if isinstance(path, str) else ""


def register(app: FastAPI, server: StudioServer) -> None:
    """Wire the SPA shell and JSON API routes onto the FastAPI app."""

    @app.get("/")
    async def index() -> HTMLResponse:
        return server.render_spa_index()

    from pydantic_studio.renderers.html.serialize import (
        dispatch_mutation,
        validation_envelope,
    )

    @app.get("/api/tree", response_class=JSONResponse)
    async def api_tree() -> JSONResponse:
        try:
            payload = _tree_payload(server)
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": f"tree load failed: {exc}"},
            )
        return JSONResponse(content=payload)

    @app.post("/api/mutations", response_class=JSONResponse)
    async def api_mutations(request: Request) -> JSONResponse:
        try:
            raw_mutation = await request.json()
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"detail": f"invalid JSON mutation request: {exc}"},
            )
        if not isinstance(raw_mutation, dict):
            return JSONResponse(
                status_code=400,
                content={"detail": "mutation request must be a JSON object"},
            )
        mutation = cast("dict[str, Any]", raw_mutation)
        readonly_error = _readonly_mutation_error(server, mutation)
        if readonly_error is None:
            result = dispatch_mutation(server.tree, mutation)
        else:
            from pydantic_studio.tree.validation import ValidationResult

            result = ValidationResult.fail([readonly_error])
        # Unknown / malformed op -> 400 so the client knows it's a request
        # bug, not a state issue. Validation failures of valid ops keep
        # 200 (the tree is untouched, ``validation`` reports what failed).
        if not result.ok and any(
            "unknown op" in err or err.startswith("mutation failed:")
            for err in result.errors
        ):
            return JSONResponse(
                status_code=400, content={"detail": "; ".join(result.errors)}
            )
        # A rejected mutation leaves the prior tree intact. Fold the
        # mutation errors back into the validation envelope so the SPA can
        # render the rejection without needing a second request.
        try:
            validation = validation_envelope(server.tree)
            if not result.ok:
                mutation_path = _mutation_error_path(mutation)
                validation = {
                    "ok": False,
                    "errors": [
                        {"path": mutation_path, "message": err}
                        for err in result.errors
                    ]
                    + list(validation["errors"]),
                }
            tree_payload = _tree_payload(server)
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": f"mutation response failed: {exc}"},
            )
        return JSONResponse(
            content={
                "tree": tree_payload,
                "validation": validation,
                "mutation_result": {"ok": result.ok, "errors": list(result.errors)},
            }
        )

    @app.post("/api/submit", response_class=JSONResponse)
    async def api_submit() -> JSONResponse:
        try:
            result = server.session.submit()
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": f"submit failed: {exc}"},
            )
        if not result.ok:
            errors = [
                {
                    "path": result.paths[index] if index < len(result.paths) else "",
                    "message": message,
                }
                for index, message in enumerate(result.errors)
            ]
            if not errors:
                errors = validation_envelope(server.tree)["errors"]
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "errors": errors,
                },
            )
        return JSONResponse(content={"ok": True})

    @app.post("/api/cancel", response_class=JSONResponse)
    async def api_cancel() -> JSONResponse:
        try:
            server.session.cancel()
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": f"cancel failed: {exc}"},
            )
        return JSONResponse(content={"ok": True})

    @app.get("/api/heartbeat", response_class=JSONResponse)
    async def api_heartbeat() -> JSONResponse:
        import time as _t

        server.last_heartbeat_ts = _t.time()
        return JSONResponse(content={"ok": True})
