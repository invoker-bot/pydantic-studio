# Changelog

All notable user-facing changes are recorded here.

## 0.5.0 - Alpha

- Adds `StudioEmbedManager` / `mount_embed_app`, a multi-session layer on top
  of the existing single-session embed foundation: a host mounts one ASGI
  app that manages many concurrent `EditSession`s under session-scoped
  `/s/<id>` routes, each carrying the full external base path.
- Embedded sessions never auto-cancel on heartbeat timeout (that watcher
  only runs in `run_html_app`); an idle-TTL sweep (`sweep_idle_sessions`,
  default 900s) reclaims abandoned sessions instead.
- Adds `reopen_session` so a host can clear a session's terminal outcome
  and let `/api/mutations` recover after a host-side business validation
  failure post-submit, without changing `EditSession.submit()`'s existing
  terminal-outcome behavior.
- Injects a `sessionId` into the embedded frontend's runtime config and
  posts `pydantic-studio:submitted` / `pydantic-studio:cancelled` messages
  to the parent window on save/cancel, so a hosting page can identify which
  embedded session just finished.

## 0.4.0 - Alpha

- Ships the Interactive editor for Pydantic models across console prompts,
  Textual TUI, and the React-backed local web app.
- Supports YAML round-trip editing with comments, plus TOML and JSON I/O.
- Adds root model variants, task-oriented submit/cancel sessions, parse-on-load
  symmetry for validator-backed fields, and embeddable renderer entry points.
- Hardens release readiness with Python 3.11-3.14 default tests, explicit
  Playwright browser e2e tests, frontend bundle drift checks,
  wheel and sdist install smoke gates, distribution metadata checks,
  GitHub OIDC Trusted Publishing, and independent piesource publishing.
