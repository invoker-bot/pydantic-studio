# Repository Guidelines

## Project Structure & Module Organization

`src/pydantic_studio/` contains the Python package. Core form state lives in
`tree/`, type builders in `types/`, file format handling in `io/`, and UI
frontends in `renderers/textual_` and `renderers/html`. The React/Vite SPA is
under `frontend/src/`; its committed production bundle is
`src/pydantic_studio/renderers/html/static/dist/`. Tests are split between
`tests/unit/` and explicit browser e2e tests in `tests/e2e/`. Documentation is
in `docs/site/`, long-form plans are in `docs/superpowers/plans/`, and runnable
examples are in `examples/`.

## Build, Test, and Development Commands

- `uv sync`: install Python dependencies and default dev/lint groups.
- `uv run pytest -q`: run the default test suite; this intentionally skips
  `tests/e2e/`.
- `uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra"`: run
  Playwright e2e tests after `uv run playwright install chromium`.
- `uv run ruff check`: lint Python code using the repository Ruff rules.
- `uv run pyright src/pydantic_studio`: type-check production Python code.
- `uv run mkdocs build --strict`: validate documentation.
- `cd frontend && pnpm install && pnpm dev`: run the SPA dev server.
- `cd frontend && pnpm build`: rebuild the committed static bundle.

## Coding Style & Naming Conventions

Target Python 3.11+ and Pydantic v2. Keep `from __future__ import annotations`
at the top of Python modules. Ruff enforces 100-character lines and rules
`E`, `F`, `I`, `B`, `UP`, `PT`, `RUF`, `TC`, and `SIM`. Use snake_case for
modules, functions, and methods; PascalCase for classes; UPPER_SNAKE for
constants; and a trailing underscore only to avoid stdlib name collisions
such as `json_.py`. React components use PascalCase `.tsx` files, with shared
UI primitives in `frontend/src/components/ui/`.

## Testing Guidelines

Name Python tests `test_*.py`. Put focused behavior tests in `tests/unit/` and
browser workflow tests in `tests/e2e/`. Add regression tests for new tree
mutations, builders, file writers, and renderer behavior. For new node types,
include snapshot round-trip coverage through `model_dump_json` and
`model_validate_json`.

## Commit & Pull Request Guidelines

History uses short Conventional Commit-style subjects, for example
`feat(tui-v2): ...`, `fix(tui-v2): ...`, and `test(tui-v2): ...`; merge commits
use `merge: branch - summary`. Keep commits scoped and include tests or docs
with the behavior they protect. PRs should describe user-visible changes,
validation commands run, linked issues, and screenshots or recordings for UI
changes.

## Agent-Specific Instructions

Respect `CLAUDE.md` for deeper project invariants. Do not push to origin
without explicit user confirmation.
