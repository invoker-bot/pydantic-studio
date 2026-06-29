# Embeddable renderers

| Field | Value |
|---|---|
| Status | Design |
| Scope | Web-first embedding, then Textual screen embedding |
| Current public launchers | `run_html_app(...)`, `run_app(...)`, `StudioServer`, `StudioApp` |
| Primary invariant | `FormTree` remains the single source of truth |

## Summary

`pydantic-studio` already supports being called from Python as a blocking
subprogram: `run_app(...)` and `run_html_app(...)` launch a complete editing
session and return `EditOutcome`. The Web renderer also exposes
`StudioServer.app`, so advanced callers can manually run the FastAPI app.

This design turns that accidental support into a first-class embedding API.
The work is intentionally split:

1. **Phase 1: Web-first embedding.** External FastAPI/Starlette applications can
   mount pydantic-studio under a path such as `/studio`, serve the bundled React
   app with the correct asset/API prefix, and observe the same submit/cancel
   outcome without `run_html_app` owning the event loop, port, or browser.
2. **Phase 2: TUI screen embedding.** External Textual applications can push a
   pydantic-studio editor screen and receive submit/cancel as a screen result or
   message, while the standalone `StudioApp` remains a convenience launcher.

## Goals

- Preserve the current CLI and standalone library behavior.
- Add explicit embeddable APIs instead of requiring callers to copy pieces of
  `run_html_app` or subclass `StudioApp`.
- Support Web subpath mounting, including SPA assets and JSON API calls.
- Share session outcome handling across renderers.
- Keep renderer state non-authoritative: all edits still mutate one `FormTree`.
- Keep the first implementation small enough to validate with focused tests.

## Non-goals

- No multi-user server mode, authentication, authorization, collaborative edit
  sessions, persistence backend, or tenant model.
- No remote exposure policy. Standalone launchers keep binding to loopback;
  embedded hosts own their own network exposure and auth boundary.
- No WebSocket protocol. The existing request/response JSON API remains enough.
- No attempt to make the React field components reusable inside arbitrary React
  apps in this phase. Embedding means ASGI app mounting, not npm package export.
- No TUI screen embedding in Phase 1.

## Current constraints

The current Web launcher owns too much lifecycle for an embedded host:

- It binds a random loopback port.
- It opens the default browser.
- It calls `asyncio.run(...)`.
- It assumes the app is served from `/`.
- The React bundle fetches absolute `/api/...` paths.
- The built `index.html` references absolute `/static/dist/...` assets.

The current TUI implementation has a similar standalone bias:

- `StudioApp` owns app-level save/cancel bindings.
- `ConfigScreen` is the editor screen, but submit/cancel behavior lives on the
  app object.
- `ActionBar` calls `app.action_save()` / `app.action_cancel_session()`.
- `ConfirmExitScreen` calls private app methods `_submit()` and `_finish()`.
- `_finish()` exits the entire Textual app.

Those constraints are acceptable for standalone launchers, but an embedded host
needs lifecycle control.

## Core session model

Introduce a small renderer-agnostic session object:

```python
session = EditSession(
    tree=tree,
    save_path=save_path,
    readonly_paths={"name"},
)
```

`EditSession` owns only session metadata and outcome state:

- `tree: FormTree`
- `save_path: Path | None`
- `readonly_paths: frozenset[str]`
- `outcome: EditOutcome | None`
- `initial_state: object` for dirty checks
- `submitted`, `cancelled`, `done`, and `dirty` convenience properties

It exposes two lifecycle methods:

```python
result = session.submit()
outcome = session.cancel()
```

`submit()` validates with `tree.to_instance()`. If validation fails, it returns
a structured failure result and leaves `outcome` unset. If validation succeeds,
it writes `save_path` when configured, sets `outcome =
EditOutcome("submitted")`, and returns success.

`cancel()` sets `outcome = EditOutcome("cancelled")` unless the session is
already done, then returns the outcome.

The result shape should be explicit:

```python
@dataclass(frozen=True)
class SubmitResult:
    ok: bool
    outcome: EditOutcome | None = None
    errors: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
```

This keeps submit/cancel semantics shared without forcing every renderer to
catch `ValidationFailedError` itself.

Compatibility properties on `StudioServer` (`tree`, `save_path`, `submitted`,
`cancelled`, `readonly_paths`) can delegate to the session during migration.

## Phase 1: Web embedding

### Public API

The stable embedding surface is:

```python
from fastapi import FastAPI
from pydantic_studio import StudioServer, mount_html_app

host = FastAPI()
server = StudioServer(tree=tree, save_path=None, base_path="/studio")
host.mount("/studio", server.app)

# Later:
if server.session.submitted:
    instance = server.session.tree.to_instance()
```

Convenience helper:

```python
server = mount_html_app(
    host,
    "/studio",
    tree=tree,
    save_path=None,
    readonly_paths={"profile"},
)
```

`mount_html_app(...)` returns the `StudioServer` so callers can inspect
`server.session`, not just the mounted ASGI app.

When callers use `mount_html_app(...)`, the helper sets `base_path` from the
mount path. Callers only need to pass both values manually when constructing a
`StudioServer` themselves before calling `host.mount(...)`.

`run_html_app(...)` remains public and keeps the current blocking behavior. Its
implementation changes to use the same `StudioServer` and session underneath:

```python
server = StudioServer(tree=tree, save_path=save_path, base_path="")
uvicorn.Server(uvicorn.Config(server.app, ...))
```

### Base path handling

`base_path` is the external browser-visible prefix. Examples:

- Standalone: `base_path=""`, browser uses `/api/tree` and
  `/static/dist/assets/...`.
- Mounted: `base_path="/studio"`, browser uses `/studio/api/tree` and
  `/studio/static/dist/assets/...`.

The server normalizes `base_path`:

- `""` stays empty.
- `"studio"` becomes `"/studio"`.
- `"/studio/"` becomes `"/studio"`.
- `"/"` becomes empty.

### SPA index rendering

The root route should stop returning the static `index.html` by raw
`FileResponse`. Instead it returns an `HTMLResponse` generated from the bundled
index with two controlled rewrites:

1. Static asset URLs beginning with `/static/dist/` are prefixed with
   `base_path`.
2. A small runtime config script is injected before the module script:

```html
<script>
  window.__PYDANTIC_STUDIO__ = { basePath: "/studio" };
</script>
```

The React API layer reads this value and prefixes every fetch:

```ts
fetch(studioUrl("/api/tree"))
fetch(studioUrl("/api/mutations"), ...)
fetch(studioUrl("/api/submit"), ...)
fetch(studioUrl("/api/cancel"), ...)
```

This avoids rebuilding the bundle per mount path and keeps the packaged wheel
runtime free of Node.

### Routes

Inside the mounted app, routes remain app-local:

- `GET /`
- `GET /static/dist/...`
- `GET /api/tree`
- `POST /api/mutations`
- `POST /api/submit`
- `POST /api/cancel`
- `GET /api/heartbeat`

The browser-visible prefix is handled by ASGI mounting plus the SPA runtime
base path. Route handlers do not manually include `base_path`.

### Watcher behavior

Embedded mode does not start a watcher. The host owns process lifetime.

Standalone `run_html_app(...)` still starts a watcher that periodically checks:

- heartbeat timeout
- `server.session.submitted`
- `server.session.cancelled`

On submit/cancel, it shuts down uvicorn and returns `server.session.outcome`.

Heartbeat timeout calls `session.cancel()`.

### Error handling

Web submit failures keep returning HTTP 400 with:

```json
{ "ok": false, "errors": [{ "path": "field", "message": "..." }] }
```

Internally, routes use `session.submit()` and translate `SubmitResult` into the
existing JSON shape. Failed mutation semantics do not change: a valid mutation
request that fails validation returns the unmutated tree and
`mutation_result.ok = false`.

### Backward compatibility

Existing code continues to work:

```python
StudioServer(tree=tree, save_path=path).app
run_html_app(tree=tree, save_path=path)
```

`StudioServer.submitted` and `StudioServer.cancelled` remain readable and map to
the session outcome. Setting them directly is not part of the public API and
should not be preserved.

## Phase 2: TUI embedding

### Public API

External Textual apps should be able to do:

```python
session = EditSession(tree=tree, save_path=None)
outcome = await self.push_screen_wait(StudioScreen(session))
if outcome.submitted:
    instance = session.tree.to_instance()
```

`StudioScreen` is the embeddable editor surface. It wraps the current
`ConfigScreen` behavior plus submit/cancel lifecycle. It can also post a typed
message for hosts that prefer event handling:

```python
class StudioSessionEnded(Message):
    outcome: EditOutcome
```

Standalone `StudioApp` becomes a thin launcher:

```python
session = EditSession(tree=tree, save_path=save_path, readonly_paths=readonly_paths)
app = StudioApp(session=session)
app.run()
return session.outcome or EditOutcome("cancelled")
```

### Screen responsibilities

`StudioScreen` owns:

- root `ConfigScreen` composition
- Ctrl+S submit
- Ctrl+C / root Esc cancel
- dirty-tree confirm flow
- validation error presentation
- final `dismiss(outcome)` for embedded hosts

`ConfigScreen`, `FieldListView`, cells, `ChooserScreen`, and `ErrorsScreen`
remain focused on editing and display. They should not assume the app object has
private `_submit()` or `_finish()` methods.

### Refactor points

The current implementation has app-coupled points that must move behind the
screen/session boundary:

- `StudioApp.action_save()` delegates to `StudioScreen`.
- `ActionBar` should dispatch a screen action or message, not call app private
  methods.
- `ConfirmExitScreen` should return a choice (`save`, `discard`, `keep`) to the
  owning `StudioScreen`, not call `self.app._submit()`.
- `_finish(status)` should only exist on the standalone launcher, or disappear.

### Backward compatibility

Existing standalone users keep:

```python
StudioApp(tree=tree, save_path=path).run()
run_app(tree=tree, save_path=path)
```

The constructor may accept either the old arguments or a new `session=` keyword
during one compatibility window:

```python
StudioApp(tree=tree, save_path=path)
StudioApp(session=session)
```

The `StudioApp.outcome` property remains meaningful after `run()`.

## Testing strategy

### Unit tests

- `EditSession.submit()` succeeds without `save_path`.
- `EditSession.submit()` writes when `save_path` is configured.
- `EditSession.submit()` returns errors and leaves outcome unset on invalid
  trees.
- `EditSession.cancel()` sets cancelled and is idempotent.
- `StudioServer.submitted` / `cancelled` compatibility properties reflect the
  session.
- `base_path` normalization covers empty, slash, leading slash, and trailing
  slash variants.
- SPA index rendering prefixes static assets and injects runtime base config.

### Web integration tests

- `TestClient(StudioServer(tree, base_path="/studio").app)` serves `/`.
- When mounted under a host app at `/studio`, `/studio/`,
  `/studio/static/dist/...`, `/studio/api/tree`, `/studio/api/mutations`,
  `/studio/api/submit`, `/studio/api/cancel`, and `/studio/api/heartbeat` work.
- React source tests or lightweight build checks cover `studioUrl(...)` for root
  and subpath bases.
- Existing e2e tests continue to pass in standalone root mode.

### TUI tests

Phase 2 keeps the current pilot-driven coverage and adds:

- `StudioScreen(session)` submit returns/dismisses with submitted.
- Cancel on a clean tree dismisses with cancelled.
- Dirty cancel opens confirm; discard dismisses cancelled; save validates.
- ActionBar buttons work inside an embedded screen without `StudioApp` private
  methods.
- Existing `run_app(...)` outcome tests remain green.

## Documentation updates

Phase 1 documentation:

- README public API section: add `EditSession`, `mount_html_app`, and Web
  mounted-app example.
- `docs/site/api.md`: include new public objects.
- `docs/site/architecture.md`: distinguish standalone launchers from embedded
  renderer adapters.
- `docs/site/tutorial.md` or a new `docs/site/embedding.md`: show a minimal
  FastAPI host app.

Phase 2 documentation:

- Add a Textual host example that pushes `StudioScreen`.
- Explain that `StudioApp` is the standalone launcher and `StudioScreen` is the
  embeddable primitive.

## Migration sequence

1. Add `EditSession` and `SubmitResult`; route current TUI and Web submit/cancel
   through it without behavior changes.
2. Add Web `base_path`, dynamic SPA index rendering, and React API URL helper.
3. Add `mount_html_app(...)` and mounted FastAPI tests.
4. Refactor `run_html_app(...)` to use the shared Web builder.
5. Update docs for Web embedding.
6. Add `StudioScreen(session)` for Textual embedding.
7. Move ActionBar and ConfirmExitScreen away from app-private calls.
8. Refactor `StudioApp` into a standalone launcher around `StudioScreen`.
9. Update docs for TUI embedding.

The phases can ship independently. Phase 1 provides a complete supported Web
embedding story while leaving TUI behavior unchanged. Phase 2 then improves TUI
composition without destabilizing the already-shipped Web API.

## Open decisions resolved by this design

- The common abstraction is a session, not a generic renderer interface. The
  renderers differ too much in lifecycle mechanics, but they share submit,
  cancel, dirty checks, readonly paths, and outcome semantics.
- Web embedding means ASGI mounting, not React component export.
- TUI embedding means Textual screen composition, not terminal multiplexing.
- `run_html_app(...)` and `run_app(...)` remain compatibility launchers, not the
  canonical implementation layer.
