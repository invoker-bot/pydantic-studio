# Embeddable Renderers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make pydantic-studio renderers explicitly embeddable: ASGI-first Web mounting in Phase 1 and Textual screen embedding in Phase 2, while preserving standalone `run_html_app(...)`, `run_app(...)`, `StudioServer`, and `StudioApp` behavior.

**Architecture:** Add a renderer-agnostic `EditSession` that owns tree/save/outcome lifecycle. Web wraps the session in a mountable ASGI app with base-path-aware SPA assets and API calls. Textual wraps the existing form UI in an embeddable `StudioScreen`, with `StudioApp` reduced to a standalone launcher.

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI/Starlette ASGI, Uvicorn, Textual, React/Vite/TanStack Query, pytest, Playwright e2e where needed.

---

## Reference Documents

- Design spec: `docs/superpowers/specs/2026-06-30-embeddable-renderers-design.md`
- Current Web server: `src/pydantic_studio/renderers/html/server.py`
- Current Web routes: `src/pydantic_studio/renderers/html/routes.py`
- Current React API wrappers: `frontend/src/api/tree.ts`, `frontend/src/api/mutations.ts`, `frontend/src/api/submit.ts`
- Current TUI launcher: `src/pydantic_studio/renderers/textual_/app.py`
- Current TUI screens: `src/pydantic_studio/renderers/textual_/screens.py`
- Current TUI action buttons: `src/pydantic_studio/renderers/textual_/widgets/action_bar.py`

## File Structure

Create:

- `src/pydantic_studio/session.py` — shared `EditSession` and `SubmitResult`.
- `tests/unit/test_session.py` — focused lifecycle tests for `EditSession`.
- `tests/unit/test_html_embedding.py` — ASGI host mounting and base path tests.
- `frontend/src/api/base.ts` — runtime base path helper for browser fetch URLs.
- `src/pydantic_studio/renderers/textual_/studio_screen.py` — embeddable Textual editor screen and session-ended message.
- `tests/unit/test_tui_v2_studio_screen.py` — embedded-screen submit/cancel tests.
- `docs/site/embedding.md` — user-facing embedding guide for ASGI and Textual.

Modify:

- `src/pydantic_studio/__init__.py` — export `EditSession`, `SubmitResult`, `mount_html_app`, and `StudioScreen`.
- `src/pydantic_studio/renderers/html/__init__.py` — export `mount_html_app`.
- `src/pydantic_studio/renderers/html/server.py` — accept `EditSession`, base path, index rendering, and mount helper.
- `src/pydantic_studio/renderers/html/routes.py` — use `session.submit()` / `session.cancel()`.
- `src/pydantic_studio/renderers/html/static/dist/index.html` — refreshed Vite bundle output after frontend build.
- `frontend/src/api/tree.ts`, `frontend/src/api/mutations.ts`, `frontend/src/api/submit.ts` — route fetches through `studioUrl(...)`.
- `src/pydantic_studio/renderers/textual_/__init__.py` — export `StudioScreen`.
- `src/pydantic_studio/renderers/textual_/app.py` — preserve old constructor while delegating lifecycle to `EditSession` and `StudioScreen`.
- `src/pydantic_studio/renderers/textual_/screens.py` — decouple confirm-exit screen from app-private methods.
- `src/pydantic_studio/renderers/textual_/widgets/action_bar.py` — dispatch screen actions instead of app-private methods.
- `tests/unit/test_public_api.py` — assert new public exports.
- `tests/unit/test_html_api_routes.py`, `tests/unit/test_html_server.py` — update expectations around session-backed submit/cancel and base-path index.
- `tests/unit/test_tui_v2_outcome.py`, `tests/unit/test_tui_v2_save_quit.py` — keep standalone launcher behavior pinned.
- `README.md`, `docs/site/api.md`, `docs/site/architecture.md`, `mkdocs.yml` — document embeddable APIs.

## Task 1: Shared EditSession

**Files:**
- Create: `src/pydantic_studio/session.py`
- Create: `tests/unit/test_session.py`
- Modify: `src/pydantic_studio/__init__.py`
- Modify: `tests/unit/test_public_api.py`

- [ ] **Step 1: Write failing lifecycle tests**

Create `tests/unit/test_session.py`:

```python
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree, load_yaml
from pydantic_studio.outcome import EditOutcome
from pydantic_studio.session import EditSession, SubmitResult


class _ValidSchema(BaseModel):
    name: str = "alpha"
    debug: bool = False


class _RequiredSchema(BaseModel):
    api_key: str = Field(...)
    timeout: int = 30


def test_submit_result_shape() -> None:
    result = SubmitResult(ok=False, errors=("missing",), paths=("api_key",))
    assert result.ok is False
    assert result.outcome is None
    assert result.errors == ("missing",)
    assert result.paths == ("api_key",)


def test_submit_without_save_path_sets_submitted_outcome() -> None:
    tree = build_form_tree(_ValidSchema)
    session = EditSession(tree=tree)
    result = session.submit()
    assert result == SubmitResult(ok=True, outcome=EditOutcome("submitted"))
    assert session.submitted is True
    assert session.cancelled is False
    assert session.done is True


def test_submit_with_save_path_writes_yaml(tmp_path: Path) -> None:
    out = tmp_path / "config.yaml"
    tree = build_form_tree(_ValidSchema)
    session = EditSession(tree=tree, save_path=out)
    result = session.submit()
    assert result.ok is True
    assert out.exists()
    assert load_yaml(out, _ValidSchema).to_instance().name == "alpha"


def test_submit_validation_failure_leaves_outcome_unset(tmp_path: Path) -> None:
    out = tmp_path / "config.yaml"
    tree = build_form_tree(_RequiredSchema)
    session = EditSession(tree=tree, save_path=out)
    result = session.submit()
    assert result.ok is False
    assert result.outcome is None
    assert result.errors
    assert result.paths == ("api_key",)
    assert session.outcome is None
    assert session.done is False
    assert not out.exists()


def test_cancel_sets_cancelled_and_is_idempotent() -> None:
    session = EditSession(tree=build_form_tree(_ValidSchema))
    first = session.cancel()
    second = session.cancel()
    assert first == EditOutcome("cancelled")
    assert second == EditOutcome("cancelled")
    assert session.cancelled is True
    assert session.submitted is False
    assert session.done is True


def test_dirty_tracks_tree_changes() -> None:
    tree = build_form_tree(_ValidSchema)
    session = EditSession(tree=tree)
    assert session.dirty is False
    tree.set_value("name", "changed")
    assert session.dirty is True
```

Extend `tests/unit/test_public_api.py`:

```python
def test_embeddable_session_exports():
    assert hasattr(ps, "EditSession")
    assert hasattr(ps, "SubmitResult")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m pytest tests/unit/test_session.py tests/unit/test_public_api.py -q
```

Expected: FAIL because `pydantic_studio.session` does not exist and top-level exports are missing.

- [ ] **Step 3: Add `EditSession` and `SubmitResult`**

Create `src/pydantic_studio/session.py`:

```python
"""Shared editing-session lifecycle for renderers."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from pydantic_studio.exceptions import ValidationFailedError
from pydantic_studio.outcome import EditOutcome

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic_studio.tree.nodes import FormTree


@dataclass(frozen=True)
class SubmitResult:
    """Result of an explicit submit attempt."""

    ok: bool
    outcome: EditOutcome | None = None
    errors: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()


class EditSession:
    """Renderer-neutral edit session state.

    Renderers own pixels and input handling. This object owns the shared tree,
    readonly paths, dirty tracking, and submit/cancel outcome.
    """

    def __init__(
        self,
        tree: FormTree,
        save_path: str | Path | None = None,
        readonly_paths: Iterable[str] = (),
    ) -> None:
        self.tree = tree
        self.save_path = Path(save_path) if save_path is not None else None
        self.readonly_paths = frozenset(readonly_paths)
        self.outcome: EditOutcome | None = None
        self._initial_state = copy.deepcopy(tree.to_python())

    @property
    def dirty(self) -> bool:
        return self.tree.to_python() != self._initial_state

    @property
    def submitted(self) -> bool:
        return self.outcome == EditOutcome("submitted")

    @property
    def cancelled(self) -> bool:
        return self.outcome == EditOutcome("cancelled")

    @property
    def done(self) -> bool:
        return self.outcome is not None

    def submit(self) -> SubmitResult:
        """Validate and optionally persist the current tree."""
        from pydantic_studio import save_yaml

        try:
            if self.save_path is not None:
                save_yaml(self.tree, self.save_path)
            else:
                self.tree.to_instance()
        except ValidationFailedError as exc:
            return SubmitResult(
                ok=False,
                errors=tuple(exc.errors),
                paths=tuple(exc.paths),
            )
        except ValidationError as exc:
            errors = tuple(str(err) for err in exc.errors())
            paths = tuple(".".join(str(part) for part in err.get("loc", ())) for err in exc.errors())
            return SubmitResult(ok=False, errors=errors, paths=paths)

        self.outcome = EditOutcome("submitted")
        return SubmitResult(ok=True, outcome=self.outcome)

    def cancel(self) -> EditOutcome:
        if self.outcome is None:
            self.outcome = EditOutcome("cancelled")
        return self.outcome
```

Modify `src/pydantic_studio/__init__.py`:

```python
from pydantic_studio.session import EditSession, SubmitResult
```

Add both names to `__all__`.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run python -m pytest tests/unit/test_session.py tests/unit/test_public_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Run lint on new production file**

Run:

```bash
uv run ruff check src/pydantic_studio/session.py tests/unit/test_session.py tests/unit/test_public_api.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pydantic_studio/session.py src/pydantic_studio/__init__.py tests/unit/test_session.py tests/unit/test_public_api.py
git commit -m "feat: add shared edit session"
```

## Task 2: Route Web Submit/Cancel Through EditSession

**Files:**
- Modify: `src/pydantic_studio/renderers/html/server.py`
- Modify: `src/pydantic_studio/renderers/html/routes.py`
- Modify: `tests/unit/test_html_api_routes.py`
- Modify: `tests/unit/test_html_server.py`

- [ ] **Step 1: Write failing compatibility tests**

Append to `tests/unit/test_html_api_routes.py`:

```python
def test_studio_server_exposes_session_and_compat_flags() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)
    assert server.session.tree is tree
    assert server.submitted is False
    assert server.cancelled is False

    response = TestClient(server.app).post("/api/submit")
    assert response.status_code == 200
    assert server.session.submitted is True
    assert server.submitted is True
    assert server.cancelled is False


def test_api_cancel_uses_session_outcome() -> None:
    tree = build_form_tree(_Demo, existing={"name": "alpha", "workers": 4})
    server = StudioServer(tree=tree, save_path=None)
    response = TestClient(server.app).post("/api/cancel")
    assert response.status_code == 200
    assert server.session.cancelled is True
    assert server.cancelled is True
```

Append to `tests/unit/test_html_server.py`:

```python
def test_heartbeat_timeout_cancels_session() -> None:
    import time

    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(
        tree=tree,
        save_path=None,
        heartbeat_timeout_seconds=0.1,
    )
    studio_server.last_heartbeat_ts = time.time()
    time.sleep(0.15)
    studio_server._check_heartbeat_timeout()
    assert studio_server.session.cancelled is True
    assert studio_server.cancelled is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m pytest tests/unit/test_html_api_routes.py tests/unit/test_html_server.py -q
```

Expected: FAIL because `StudioServer.session` does not exist and heartbeat timeout only toggles `cancelled`.

- [ ] **Step 3: Update `StudioServer` to own an `EditSession`**

In `src/pydantic_studio/renderers/html/server.py`, add the import:

```python
from pydantic_studio.session import EditSession
```

Change `StudioServer.__init__` to accept `session`:

```python
def __init__(
    self,
    tree: FormTree | None = None,
    save_path: str | Path | None = None,
    heartbeat_timeout_seconds: float = 30.0,
    readonly_paths: Iterable[str] = (),
    session: EditSession | None = None,
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
    self.app = FastAPI()
    self.templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    self.last_heartbeat_ts: float = 0.0
    self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
    self._mount_static()
    self._register_routes()
```

Add compatibility properties to `StudioServer`:

```python
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
```

Change `_check_heartbeat_timeout()`:

```python
if elapsed > self.heartbeat_timeout_seconds:
    self.session.cancel()
```

- [ ] **Step 4: Update Web submit/cancel routes**

In `src/pydantic_studio/renderers/html/routes.py`, change legacy `/submit`:

```python
@app.post("/submit", response_class=HTMLResponse)
async def submit() -> HTMLResponse:
    result = server.session.submit()
    if not result.ok:
        return HTMLResponse(
            content=f"<pre>Validation failed: {'; '.join(result.errors)}</pre>",
            status_code=200,
        )
    return HTMLResponse(content="<h2>Done — you can close this tab.</h2>")
```

Change legacy `/cancel`:

```python
@app.post("/cancel", response_class=HTMLResponse)
async def cancel() -> HTMLResponse:
    server.session.cancel()
    return HTMLResponse(content="<h2>Cancelled — you can close this tab.</h2>")
```

Change JSON `/api/submit`:

```python
@app.post("/api/submit", response_class=JSONResponse)
async def api_submit() -> JSONResponse:
    result = server.session.submit()
    if not result.ok:
        errors = [
            {"path": path, "message": message}
            for path, message in zip(result.paths, result.errors, strict=False)
        ]
        if not errors:
            errors = validation_envelope(server.tree)["errors"]
        return JSONResponse(
            status_code=400,
            content={"ok": False, "errors": errors},
        )
    return JSONResponse(content={"ok": True})
```

Change JSON `/api/cancel`:

```python
@app.post("/api/cancel", response_class=JSONResponse)
async def api_cancel() -> JSONResponse:
    server.session.cancel()
    return JSONResponse(content={"ok": True})
```

- [ ] **Step 5: Update standalone watcher to read session outcome**

In `run_html_app(...)`, change watcher condition:

```python
if studio_server.session.done:
    server.should_exit = True
```

Change return handling:

```python
outcome = studio_server.session.outcome
if outcome is not None and outcome.submitted:
    if save_path is not None:
        print(f"saved to {save_path}", file=sys.stdout)
    else:
        print("submitted (no save path configured)", file=sys.stdout)
    return outcome
print("cancelled", file=sys.stdout)
return EditOutcome(status="cancelled")
```

- [ ] **Step 6: Run targeted Web tests**

Run:

```bash
uv run python -m pytest tests/unit/test_html_api_routes.py tests/unit/test_html_server.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/pydantic_studio/renderers/html/server.py src/pydantic_studio/renderers/html/routes.py tests/unit/test_html_api_routes.py tests/unit/test_html_server.py
git commit -m "feat(web): share edit session lifecycle"
```

## Task 3: ASGI Base Path and SPA URL Helper

**Files:**
- Create: `frontend/src/api/base.ts`
- Modify: `frontend/src/api/tree.ts`
- Modify: `frontend/src/api/mutations.ts`
- Modify: `frontend/src/api/submit.ts`
- Modify: `src/pydantic_studio/renderers/html/server.py`
- Modify: `src/pydantic_studio/renderers/html/static/dist/index.html`
- Modify: bundled assets under `src/pydantic_studio/renderers/html/static/dist/assets/`
- Modify: `tests/unit/test_html_server.py`

- [ ] **Step 1: Write failing server tests for base path index rendering**

Append to `tests/unit/test_html_server.py`:

```python
def test_index_injects_runtime_base_path_for_mounted_app() -> None:
    from pydantic_studio.renderers.html import StudioServer

    tree = build_form_tree(Server)
    studio_server = StudioServer(tree=tree, save_path=None, base_path="/studio")
    client = TestClient(studio_server.app)
    response = client.get("/")
    assert response.status_code == 200
    text = response.text
    assert 'window.__PYDANTIC_STUDIO__ = {"basePath": "/studio"};' in text
    assert 'src="/studio/static/dist/assets/index-' in text
    assert 'href="/studio/static/dist/assets/index-' in text


def test_base_path_normalization() -> None:
    from pydantic_studio.renderers.html.server import normalize_base_path

    assert normalize_base_path("") == ""
    assert normalize_base_path("/") == ""
    assert normalize_base_path("studio") == "/studio"
    assert normalize_base_path("/studio") == "/studio"
    assert normalize_base_path("/studio/") == "/studio"
```

- [ ] **Step 2: Run server tests to verify failure**

Run:

```bash
uv run python -m pytest tests/unit/test_html_server.py::test_index_injects_runtime_base_path_for_mounted_app tests/unit/test_html_server.py::test_base_path_normalization -q
```

Expected: FAIL because `base_path` and `normalize_base_path` do not exist.

- [ ] **Step 3: Add base path normalization and dynamic SPA index**

In `src/pydantic_studio/renderers/html/server.py`, add:

```python
import html
import json
```

Add the runtime response import:

```python
from fastapi.responses import HTMLResponse
```

Add module constant:

```python
_SPA_INDEX = _STATIC_DIR / "dist" / "index.html"
```

Add function:

```python
def normalize_base_path(base_path: str) -> str:
    stripped = base_path.strip()
    if stripped in {"", "/"}:
        return ""
    return "/" + stripped.strip("/")
```

Add to `StudioServer.__init__` signature:

```python
base_path: str = "",
```

Store it:

```python
self.base_path = normalize_base_path(base_path)
```

Add method:

```python
def render_spa_index(self) -> HTMLResponse:
    index = _SPA_INDEX.read_text(encoding="utf-8")
    if self.base_path:
        index = index.replace('src="/static/dist/', f'src="{self.base_path}/static/dist/')
        index = index.replace('href="/static/dist/', f'href="{self.base_path}/static/dist/')
    config = json.dumps({"basePath": self.base_path})
    script = (
        "<script>"
        f"window.__PYDANTIC_STUDIO__ = {html.escape(config, quote=False)};"
        "</script>"
    )
    index = index.replace("</head>", f"    {script}\n  </head>")
    return HTMLResponse(index)
```

In `src/pydantic_studio/renderers/html/routes.py`, change index route:

```python
@app.get("/")
async def index() -> HTMLResponse:
    return server.render_spa_index()
```

Remove `FileResponse` from the `fastapi.responses` import in
`src/pydantic_studio/renderers/html/routes.py` because no route should return
the static index file directly after this change.

- [ ] **Step 4: Add React URL helper**

Create `frontend/src/api/base.ts`:

```ts
declare global {
  interface Window {
    __PYDANTIC_STUDIO__?: {
      basePath?: string;
    };
  }
}

function normalizedBasePath(): string {
  const raw = window.__PYDANTIC_STUDIO__?.basePath ?? "";
  const trimmed = raw.trim();
  if (trimmed === "" || trimmed === "/") {
    return "";
  }
  return `/${trimmed.replace(/^\/+|\/+$/g, "")}`;
}

export function studioUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBasePath()}${normalizedPath}`;
}
```

Modify `frontend/src/api/tree.ts`:

```ts
import { studioUrl } from "@/api/base";
import { FormTreeSchema, type FormTree } from "@/api/schemas";

export async function fetchTree(): Promise<FormTree> {
  const response = await fetch(studioUrl("/api/tree"));
  if (!response.ok) {
    throw new Error(`GET /api/tree failed: HTTP ${response.status}`);
  }
  const raw = await response.json();
  return FormTreeSchema.parse(raw);
}
```

Modify `frontend/src/api/mutations.ts` fetch call:

```ts
import { studioUrl } from "@/api/base";
```

```ts
const response = await fetch(studioUrl("/api/mutations"), {
```

Modify `frontend/src/api/submit.ts` fetch calls:

```ts
import { studioUrl } from "@/api/base";
```

```ts
const response = await fetch(studioUrl("/api/submit"), { method: "POST" });
```

```ts
const response = await fetch(studioUrl("/api/cancel"), { method: "POST" });
```

- [ ] **Step 5: Type-check and rebuild frontend bundle**

Run:

```bash
cd frontend && pnpm build
```

Expected: PASS and updates under `src/pydantic_studio/renderers/html/static/dist/`.

- [ ] **Step 6: Verify base path tests pass**

Run:

```bash
uv run python -m pytest tests/unit/test_html_server.py::test_index_route_serves_spa_shell tests/unit/test_html_server.py::test_spa_bundle_referenced_by_index_is_reachable tests/unit/test_html_server.py::test_index_injects_runtime_base_path_for_mounted_app tests/unit/test_html_server.py::test_base_path_normalization -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/base.ts frontend/src/api/tree.ts frontend/src/api/mutations.ts frontend/src/api/submit.ts src/pydantic_studio/renderers/html/server.py src/pydantic_studio/renderers/html/routes.py src/pydantic_studio/renderers/html/static/dist tests/unit/test_html_server.py
git commit -m "feat(web): support mounted base paths"
```

## Task 4: ASGI Mount Helper and Host Integration Tests

**Files:**
- Modify: `src/pydantic_studio/renderers/html/server.py`
- Modify: `src/pydantic_studio/renderers/html/__init__.py`
- Modify: `src/pydantic_studio/__init__.py`
- Create: `tests/unit/test_html_embedding.py`
- Modify: `tests/unit/test_public_api.py`

- [ ] **Step 1: Write failing ASGI host tests**

Create `tests/unit/test_html_embedding.py`:

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.applications import Starlette

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html import StudioServer, mount_html_app


class _Schema(BaseModel):
    name: str = "alpha"
    workers: int = 4


def test_studio_server_app_mounts_under_starlette_prefix() -> None:
    host = Starlette()
    server = StudioServer(tree=build_form_tree(_Schema), base_path="/studio")
    host.mount("/studio", server.app)
    client = TestClient(host)

    index = client.get("/studio/")
    assert index.status_code == 200
    assert 'window.__PYDANTIC_STUDIO__ = {"basePath": "/studio"};' in index.text

    tree = client.get("/studio/api/tree")
    assert tree.status_code == 200
    assert tree.json()["root"]["kind"] == "group"


def test_mount_html_app_mounts_under_starlette_prefix() -> None:
    host = Starlette()
    server = mount_html_app(host, "/studio", tree=build_form_tree(_Schema))
    client = TestClient(host)

    assert client.get("/studio/api/tree").status_code == 200
    assert server.session.tree.schema_name.endswith("_Schema")
    assert server.base_path == "/studio"


def test_mount_html_app_mounts_under_fastapi_prefix() -> None:
    host = FastAPI()
    server = mount_html_app(host, "/studio", tree=build_form_tree(_Schema))
    client = TestClient(host)

    assert client.get("/studio/api/tree").status_code == 200
    response = client.post(
        "/studio/api/mutations",
        json={"op": "set_value", "path": "name", "value": "beta"},
    )
    assert response.status_code == 200
    assert server.tree.root.find("name").value == "beta"


def test_mount_html_app_rejects_host_without_mount() -> None:
    class _NoMount:
        pass

    try:
        mount_html_app(_NoMount(), "/studio", tree=build_form_tree(_Schema))
    except TypeError as exc:
        assert "mount" in str(exc)
    else:
        raise AssertionError("mount_html_app should reject hosts without mount()")
```

Extend `tests/unit/test_public_api.py`:

```python
def test_web_embedding_exports():
    assert hasattr(ps, "mount_html_app")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m pytest tests/unit/test_html_embedding.py tests/unit/test_public_api.py -q
```

Expected: FAIL because `mount_html_app` is not exported.

- [ ] **Step 3: Add `mount_html_app` helper**

In `src/pydantic_studio/renderers/html/server.py`, add:

```python
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
```

Modify `src/pydantic_studio/renderers/html/__init__.py`:

```python
from pydantic_studio.renderers.html.server import StudioServer, mount_html_app, run_html_app

__all__ = ["StudioServer", "mount_html_app", "run_html_app"]
```

Modify `src/pydantic_studio/__init__.py`:

```python
from pydantic_studio.renderers.html import StudioServer, mount_html_app, run_html_app
```

Add `"mount_html_app"` to `__all__`.

- [ ] **Step 4: Run ASGI embedding tests**

Run:

```bash
uv run python -m pytest tests/unit/test_html_embedding.py tests/unit/test_html_api_routes.py tests/unit/test_html_server.py tests/unit/test_public_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pydantic_studio/renderers/html/server.py src/pydantic_studio/renderers/html/__init__.py src/pydantic_studio/__init__.py tests/unit/test_html_embedding.py tests/unit/test_public_api.py
git commit -m "feat(web): add ASGI mount helper"
```

## Task 5: Embeddable Textual StudioScreen

**Files:**
- Create: `src/pydantic_studio/renderers/textual_/studio_screen.py`
- Modify: `src/pydantic_studio/renderers/textual_/__init__.py`
- Modify: `src/pydantic_studio/__init__.py`
- Create: `tests/unit/test_tui_v2_studio_screen.py`
- Modify: `tests/unit/test_public_api.py`

- [ ] **Step 1: Write failing embedded screen tests**

Create `tests/unit/test_tui_v2_studio_screen.py`:

```python
from __future__ import annotations

import pytest
from pydantic import BaseModel, Field
from textual.app import App

from pydantic_studio import EditSession, build_form_tree
from pydantic_studio.renderers.textual_ import StudioScreen
from pydantic_studio.renderers.textual_.screens import ConfirmExitScreen, ErrorsScreen


class _Schema(BaseModel):
    name: str = "alpha"
    debug: bool = False


class _RequiredSchema(BaseModel):
    api_key: str = Field(...)
    timeout: int = 30


class _Host(App):
    def __init__(self, session: EditSession) -> None:
        super().__init__()
        self.session = session
        self.ended = None

    def on_mount(self) -> None:
        self.push_screen(StudioScreen(self.session))

    def on_studio_session_ended(self, event) -> None:
        self.ended = event.outcome


@pytest.mark.asyncio
async def test_studio_screen_ctrl_s_submits_without_exiting_host() -> None:
    session = EditSession(tree=build_form_tree(_Schema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.is_running is True
    assert session.submitted is True
    assert app.ended is not None
    assert app.ended.submitted is True


@pytest.mark.asyncio
async def test_studio_screen_ctrl_c_clean_cancels_without_exiting_host() -> None:
    session = EditSession(tree=build_form_tree(_Schema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.is_running is True
    assert session.cancelled is True
    assert app.ended is not None
    assert app.ended.submitted is False


@pytest.mark.asyncio
async def test_studio_screen_dirty_cancel_opens_confirm() -> None:
    session = EditSession(tree=build_form_tree(_Schema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        session.tree.set_value("name", "changed")
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmExitScreen)


@pytest.mark.asyncio
async def test_studio_screen_invalid_submit_shows_errors() -> None:
    session = EditSession(tree=build_form_tree(_RequiredSchema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, ErrorsScreen)
    assert session.outcome is None
```

Extend `tests/unit/test_public_api.py`:

```python
def test_tui_embedding_exports():
    assert hasattr(ps, "StudioScreen")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m pytest tests/unit/test_tui_v2_studio_screen.py tests/unit/test_public_api.py -q
```

Expected: FAIL because `StudioScreen` does not exist.

- [ ] **Step 3: Add initial `StudioScreen`**

Create `src/pydantic_studio/renderers/textual_/studio_screen.py`:

```python
"""Embeddable Textual screen for pydantic-studio."""

from __future__ import annotations

from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.message import Message

from pydantic_studio.outcome import EditOutcome
from pydantic_studio.renderers.textual_.screens import ConfigScreen, ConfirmExitScreen, ErrorsScreen
from pydantic_studio.session import EditSession


class StudioSessionEnded(Message):
    """Posted when an embedded StudioScreen reaches submit or cancel."""

    def __init__(self, outcome: EditOutcome) -> None:
        super().__init__()
        self.outcome = outcome


class StudioScreen(ConfigScreen):
    """Embeddable editor screen backed by an EditSession."""

    BINDINGS: ClassVar[list[BindingType]] = [
        *ConfigScreen.BINDINGS,
        Binding("ctrl+s", "save", "save", priority=True),
        Binding("ctrl+c", "quit", "quit", priority=True),
    ]

    def __init__(self, session: EditSession) -> None:
        self.session = session
        short_name = (
            self.session.tree.schema_name.split(":")[-1]
            if ":" in self.session.tree.schema_name
            else self.session.tree.schema_name
        )
        super().__init__(
            group=self.session.tree.root,
            form_tree=self.session.tree,
            breadcrumb_parts=[short_name],
        )

    @property
    def readonly_paths(self) -> frozenset[str]:
        return self.session.readonly_paths

    def _finish(self, outcome: EditOutcome) -> None:
        self.post_message(StudioSessionEnded(outcome))
        self.dismiss(outcome)

    async def action_quit(self) -> None:  # type: ignore[override]
        if isinstance(self.app.screen, ConfirmExitScreen):
            outcome = self.session.cancel()
            self._finish(outcome)
            return
        if not self.session.dirty:
            outcome = self.session.cancel()
            self._finish(outcome)
            return
        self.app.push_screen(ConfirmExitScreen())

    def action_cancel_session(self) -> None:
        self.call_next(self.action_quit)

    def action_save(self) -> None:
        self._submit()

    def _submit(self) -> bool:
        from pydantic_studio.renderers.textual_.widgets.field_list import FieldListView

        try:
            view = self.app.screen.query_one(FieldListView)
        except Exception:
            view = None
        if view is not None and not view._commit_gate():
            self.notify("fix the highlighted field first", severity="error", title="Save")
            return False

        result = self.session.submit()
        if not result.ok:
            if isinstance(self.app.screen, ConfirmExitScreen):
                self.app.pop_screen()
            n = len(result.errors)
            self.notify(
                f"{n} validation error{'s' if n != 1 else ''} — fix before saving",
                severity="error",
                title="Save failed",
            )
            self.app.push_screen(ErrorsScreen(errors=list(result.errors), paths=list(result.paths)))
            return False

        if self.session.save_path is not None:
            self.notify(
                f"Saved to {self.session.save_path}",
                severity="information",
                title="Save",
            )
        assert result.outcome is not None
        self._finish(result.outcome)
        return True
```

Modify `src/pydantic_studio/renderers/textual_/__init__.py`:

```python
from pydantic_studio.renderers.textual_.app import StudioApp, run_app
from pydantic_studio.renderers.textual_.studio_screen import StudioScreen

__all__ = ["StudioApp", "StudioScreen", "run_app"]
```

Modify `src/pydantic_studio/__init__.py`:

```python
from pydantic_studio.renderers.textual_ import StudioApp, StudioScreen, run_app
```

Add `"StudioScreen"` to `__all__`.

- [ ] **Step 4: Run StudioScreen tests**

Run:

```bash
uv run python -m pytest tests/unit/test_tui_v2_studio_screen.py tests/unit/test_public_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit when tests pass**

```bash
git add src/pydantic_studio/renderers/textual_/studio_screen.py src/pydantic_studio/renderers/textual_/__init__.py src/pydantic_studio/__init__.py tests/unit/test_tui_v2_studio_screen.py tests/unit/test_public_api.py
git commit -m "feat(tui): add embeddable studio screen"
```

## Task 6: Make StudioApp a Thin Launcher Around StudioScreen

**Files:**
- Modify: `src/pydantic_studio/renderers/textual_/app.py`
- Modify: `src/pydantic_studio/renderers/textual_/screens.py`
- Modify: `src/pydantic_studio/renderers/textual_/widgets/action_bar.py`
- Modify: `tests/unit/test_tui_v2_outcome.py`
- Modify: `tests/unit/test_tui_v2_save_quit.py`
- Modify: `tests/unit/test_tui_v2_studio_screen.py`

- [ ] **Step 1: Add failing tests for app compatibility and action routing**

Append to `tests/unit/test_tui_v2_studio_screen.py`:

```python
@pytest.mark.asyncio
async def test_action_bar_buttons_work_inside_embedded_screen() -> None:
    session = EditSession(tree=build_form_tree(_Schema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#action-save")
        await pilot.pause()
    assert session.submitted is True


@pytest.mark.asyncio
async def test_confirm_discard_finishes_embedded_screen_cancelled() -> None:
    session = EditSession(tree=build_form_tree(_Schema))
    app = _Host(session)
    async with app.run_test() as pilot:
        await pilot.pause()
        session.tree.set_value("name", "changed")
        await pilot.press("ctrl+c")
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
    assert session.cancelled is True
```

Append to `tests/unit/test_tui_v2_outcome.py`:

```python
def test_studio_app_accepts_session_keyword() -> None:
    from pydantic_studio import EditSession

    tree = build_form_tree(_Schema)
    session = EditSession(tree=tree)
    app = StudioApp(session=session)
    assert app.session is session
    assert app.tree is tree
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m pytest tests/unit/test_tui_v2_studio_screen.py tests/unit/test_tui_v2_outcome.py tests/unit/test_tui_v2_save_quit.py -q
```

Expected: FAIL because `ActionBar` and `ConfirmExitScreen` still call app-private methods and `StudioApp(session=...)` is unsupported.

- [ ] **Step 3: Update ActionBar to dispatch screen actions**

Modify `src/pydantic_studio/renderers/textual_/widgets/action_bar.py`:

```python
def on_button_pressed(self, event: Button.Pressed) -> None:
    event.stop()
    screen = self.screen
    if event.button.id == "action-save":
        save = getattr(screen, "action_save", None)
        if save is not None:
            save()
        return
    if event.button.id == "action-cancel":
        cancel = getattr(screen, "action_cancel_session", None)
        if cancel is not None:
            cancel()
            return
        app_cancel = getattr(self.app, "action_cancel_session", None)
        if app_cancel is not None:
            app_cancel()
```

- [ ] **Step 4: Update ConfirmExitScreen to call screen owner first**

Modify `src/pydantic_studio/renderers/textual_/screens.py`:

```python
def action_save_and_exit(self) -> None:
    owner = self.app.screen_stack[-2] if len(self.app.screen_stack) >= 2 else self.app
    submit = getattr(owner, "_submit", None)
    if submit is None:
        submit = getattr(self.app, "_submit", None)
    submit()

def action_discard(self) -> None:
    owner = self.app.screen_stack[-2] if len(self.app.screen_stack) >= 2 else self.app
    cancel = getattr(owner, "_cancel_from_confirm", None)
    if cancel is not None:
        cancel()
        return
    self.app._finish("cancelled")  # type: ignore[attr-defined]
```

Add to `StudioScreen`:

```python
def _cancel_from_confirm(self) -> None:
    outcome = self.session.cancel()
    self._finish(outcome)
```

- [ ] **Step 5: Refactor StudioApp around EditSession and StudioScreen**

Modify `src/pydantic_studio/renderers/textual_/app.py`:

```python
def __init__(
    self,
    tree: FormTree | None = None,
    save_path: str | Path | None = None,
    readonly_paths: Iterable[str] = (),
    session: EditSession | None = None,
) -> None:
    super().__init__()
    if session is None:
        if tree is None:
            raise TypeError("StudioApp requires either tree or session")
        session = EditSession(tree=tree, save_path=save_path, readonly_paths=readonly_paths)
    self.session = session
    self._outcome = EditOutcome(status="cancelled")
```

Change properties:

```python
@property
def outcome(self) -> EditOutcome:
    return self.session.outcome or self._outcome

@property
def dirty(self) -> bool:
    return self.session.dirty

@property
def readonly_paths(self) -> frozenset[str]:
    return self.session.readonly_paths

@property
def save_path(self) -> Path | None:
    return self.session.save_path

@property
def tree(self) -> FormTree:  # type: ignore[override]
    return self.session.tree

@tree.setter
def tree(self, value: FormTree) -> None:
    self.session.tree = value
```

Change `on_mount()`:

```python
def on_mount(self) -> None:
    from pydantic_studio.renderers.textual_.studio_screen import StudioScreen

    self.push_screen(StudioScreen(self.session))
```

Add message handler:

```python
def on_studio_session_ended(self, event) -> None:
    self._outcome = event.outcome
    self.exit()
```

Keep `action_save`, `action_quit`, `action_cancel_session`, and `_submit` as compatibility shims:

```python
def _studio_screen(self):
    from pydantic_studio.renderers.textual_.studio_screen import StudioScreen

    for screen in reversed(self.screen_stack):
        if isinstance(screen, StudioScreen):
            return screen
    return None

def action_save(self) -> None:
    screen = self._studio_screen()
    if screen is not None:
        screen.action_save()

async def action_quit(self) -> None:  # type: ignore[override]
    screen = self._studio_screen()
    if screen is not None:
        await screen.action_quit()

def action_cancel_session(self) -> None:
    screen = self._studio_screen()
    if screen is not None:
        screen.action_cancel_session()

def _submit(self) -> bool:
    screen = self._studio_screen()
    return False if screen is None else screen._submit()
```

Update `run_app(...)`:

```python
session = EditSession(tree=tree, save_path=save_path, readonly_paths=readonly_paths)
app = StudioApp(session=session)
app.run()
return session.outcome or app.outcome
```

- [ ] **Step 6: Run TUI outcome and embedded tests**

Run:

```bash
uv run python -m pytest tests/unit/test_tui_v2_studio_screen.py tests/unit/test_tui_v2_outcome.py tests/unit/test_tui_v2_save_quit.py -q
```

Expected: PASS.

- [ ] **Step 7: Run broader TUI unit suite**

Run:

```bash
uv run python -m pytest tests/unit/test_tui_v2_*.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/pydantic_studio/renderers/textual_/app.py src/pydantic_studio/renderers/textual_/screens.py src/pydantic_studio/renderers/textual_/widgets/action_bar.py tests/unit/test_tui_v2_studio_screen.py tests/unit/test_tui_v2_outcome.py tests/unit/test_tui_v2_save_quit.py
git commit -m "feat(tui): make studio app wrap embeddable screen"
```

## Task 7: Documentation, API Reference, and Final Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/site/api.md`
- Modify: `docs/site/architecture.md`
- Create: `docs/site/embedding.md`
- Modify: `mkdocs.yml`
- Modify: `docs/superpowers/specs/2026-06-30-embeddable-renderers-design.md` only if implementation names differ from spec

- [ ] **Step 1: Add embedding documentation**

Create `docs/site/embedding.md`:

```markdown
# Embedding

pydantic-studio can run as a standalone editor or as an embedded editor inside
a larger Python application.

## ASGI Web embedding

The Web renderer exposes a mountable ASGI application. FastAPI and Starlette are
both supported hosts because both use Starlette's `mount(...)` API.

```python
from starlette.applications import Starlette

from pydantic_studio import build_form_tree, mount_html_app
from myapp.config import Settings

host = Starlette()
tree = build_form_tree(Settings)
server = mount_html_app(host, "/studio", tree=tree)
```

Open `/studio/` in the host app. The browser uses `/studio/api/*` and
`/studio/static/*`; the editor does not assume it owns the site root.

FastAPI hosts use the same helper:

```python
from fastapi import FastAPI

from pydantic_studio import build_form_tree, mount_html_app
from myapp.config import Settings

app = FastAPI()
server = mount_html_app(app, "/studio", tree=build_form_tree(Settings))
```

The returned `StudioServer` exposes `server.session`. Persist only after an
explicit submit:

```python
if server.session.submitted:
    settings = server.session.tree.to_instance()
```

## Textual embedding

Textual applications can push `StudioScreen` with an `EditSession`:

```python
from textual.app import App, ComposeResult

from pydantic_studio import EditSession, StudioScreen, build_form_tree
from myapp.config import Settings


class HostApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.session = EditSession(tree=build_form_tree(Settings))

    def compose(self) -> ComposeResult:
        yield StudioScreen(self.session)

    def on_studio_session_ended(self, event) -> None:
        if event.outcome.submitted:
            settings = self.session.tree.to_instance()
```

`StudioApp` and `run_app(...)` remain the standalone launchers.
```

Add the page to `mkdocs.yml` navigation:

```yaml
- Embedding: embedding.md
```

- [ ] **Step 2: Update API reference**

Modify `docs/site/api.md`:

```markdown
::: pydantic_studio.EditSession
::: pydantic_studio.SubmitResult
```

Under renderers, add:

```markdown
::: pydantic_studio.mount_html_app
::: pydantic_studio.StudioScreen
```

- [ ] **Step 3: Update README public API and examples**

In `README.md`, add `EditSession`, `SubmitResult`, `mount_html_app`, and `StudioScreen` to the public API block.

Add a short Web embedding example:

```python
from fastapi import FastAPI
from pydantic_studio import build_form_tree, mount_html_app

app = FastAPI()
server = mount_html_app(app, "/studio", tree=build_form_tree(AppSettings))
```

Add a short TUI embedding sentence:

```markdown
Use `StudioScreen(EditSession(...))` when embedding inside an existing Textual app;
use `StudioApp` / `run_app` when pydantic-studio owns the terminal session.
```

- [ ] **Step 4: Update architecture page**

In `docs/site/architecture.md`, add a subsection under renderers:

```markdown
### Standalone launchers vs embedded adapters

`run_app(...)` and `run_html_app(...)` own the process-facing lifecycle:
terminal app startup, browser opening, loopback port binding, and blocking until
`EditOutcome`.

Embedded adapters expose the same editor inside a host lifecycle:
`mount_html_app(...)` mounts the Web renderer into an ASGI host, and
`StudioScreen(EditSession(...))` mounts the TUI renderer inside a Textual app.
Both use the same `FormTree` mutation contract and the same `EditSession`
submit/cancel outcome.
```

- [ ] **Step 5: Run docs and focused tests**

Run:

```bash
uv run mkdocs build --strict
uv run python -m pytest tests/unit/test_session.py tests/unit/test_html_embedding.py tests/unit/test_html_api_routes.py tests/unit/test_html_server.py tests/unit/test_tui_v2_studio_screen.py tests/unit/test_tui_v2_outcome.py tests/unit/test_tui_v2_save_quit.py tests/unit/test_public_api.py -q
```

Expected: both commands PASS.

- [ ] **Step 6: Run full unit suite and lint**

Run:

```bash
uv run python -m pytest tests/unit -q
uv run ruff check
uv run pyright src/pydantic_studio
```

Expected: all PASS.

- [ ] **Step 7: Run frontend build if frontend files changed in this branch**

Run:

```bash
cd frontend && pnpm build
```

Expected: PASS. If `pnpm build` updates `src/pydantic_studio/renderers/html/static/dist/`, include those generated files in the final commit.

- [ ] **Step 8: Commit docs and verification updates**

```bash
git add README.md docs/site/api.md docs/site/architecture.md docs/site/embedding.md mkdocs.yml src/pydantic_studio/renderers/html/static/dist
git commit -m "docs: document embeddable renderers"
```

## Final Verification Checklist

Run these commands after all tasks are complete:

```bash
uv run python -m pytest tests/unit -q
uv run ruff check
uv run pyright src/pydantic_studio
uv run mkdocs build --strict
cd frontend && pnpm build
```

Run browser e2e only if Chromium is installed in the current environment:

```bash
uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra"
```

If e2e is skipped because browsers are unavailable, record the exact missing-browser error in the final implementation summary.

## Plan Self-Review

- Spec coverage: `EditSession`, ASGI-first Web mounting, base path support, standalone launcher compatibility, Textual `StudioScreen`, public exports, tests, and docs each have a task.
- Scope: the plan keeps multi-user/auth/collaboration outside the implementation.
- Type consistency: public names are `EditSession`, `SubmitResult`, `mount_html_app`, `StudioServer`, `StudioScreen`, and `StudioSessionEnded`.
- Execution order: Web embedding ships before Textual embedding, matching the design.
