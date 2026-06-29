# Contributing

Thank you for improving pydantic-studio. This project is still alpha, so small
focused changes with clear validation are preferred.

## Development Setup

Install the default development and lint dependencies:

```bash
uv sync
```

The React/Vite frontend has its own lockfile:

```bash
cd frontend
pnpm install --frozen-lockfile
```

## Validation

Run the focused tests for your change first, then the default suite:

```bash
uv run pytest -q
uv run ruff check
uv run pyright src/pydantic_studio
uv run mkdocs build --strict
```

Browser tests are explicit because they need Playwright's browser install:

```bash
uv run playwright install chromium
uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra"
```

When changing the React app, rebuild the committed bundle and verify it has no
uncommitted drift:

```bash
cd frontend
pnpm build
cd ..
git diff --exit-code -- src/pydantic_studio/renderers/html/static/dist
```

## Pull Requests

Keep pull requests scoped to one behavior or documentation improvement. Include
the validation commands you ran, screenshots or recordings for UI changes, and
any release or packaging impact.

Do not push to origin without maintainer confirmation.
