# Release

This project publishes from Git tags through GitHub Actions. The release
workflow builds the frontend bundle, runs the Python/browser/package gates,
checks the tag against `pydantic_studio.__version__`, builds both package
formats, smoke-tests wheel and sdist installs, uploads the distributions as
one release artifact, and then publishes that artifact to PyPI and piesource.
The artifact upload fails immediately if no distributions are present and
retains that artifact for 30 days for release troubleshooting.
The package metadata exposes Source, Documentation, and Issues project URLs
so registry pages have clear support and navigation links.
It also includes the MIT license classifier and PyPI search keywords for
registry discovery.

## PyPI trusted publisher

Configure the PyPI project for GitHub Actions Trusted Publishing before
creating a release tag. The publisher configuration must match the workflow:

| PyPI field | Value |
| --- | --- |
| Publisher | GitHub Actions |
| Owner / repository | `invoker-bot/pydantic-studio` |
| Workflow filename | `.github/workflows/publish.yml` |
| Environment name | `pypi` |
| Project URL | `https://pypi.org/p/pydantic-studio` |

Do not create or store a `PYPI_API_TOKEN` repository secret. The workflow
uses GitHub OIDC with `id-token: write`, and the publish action receives no
username, password, or API token.

## piesource publisher

The `publish-piesource` job downloads the same distributions produced by the
`build` job and publishes them to piesource. Configure these repository
secrets before tagging:

| Secret | Purpose |
| --- | --- |
| `PIESOURCE_REPOSITORY_URL` | Package index upload endpoint |
| `PIESOURCE_USERNAME` | piesource upload username |
| `PIESOURCE_PASSWORD` | piesource upload password or token |

The `publish-pypi` and `publish-piesource` jobs are independent consumers of
the `build` artifact. If PyPI publish failed, the workflow emits a warning and
still lets piesource continue. If piesource publish failed, the workflow emits
a warning and still lets PyPI continue. After both registry jobs attempt to
publish, `publish-result` reads their outcomes and fails the workflow with
`One or more registry publishes failed` if either registry publish failed.

## Local preflight

Run the same gates before tagging:

```bash
uv sync --locked
uv run pytest -q
uv run ruff check
uv run pyright src/pydantic_studio
uv run mkdocs build --strict
cd frontend && pnpm build && cd ..
uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra"
rm -rf dist
uv build
uv run twine check dist/*
rm -rf .dist-smoke-wheel
python -m venv .dist-smoke-wheel
.dist-smoke-wheel/bin/python -m pip install dist/*.whl
.dist-smoke-wheel/bin/pydantic-studio version
rm -rf .dist-smoke-sdist
python -m venv .dist-smoke-sdist
.dist-smoke-sdist/bin/python -m pip install dist/*.tar.gz
.dist-smoke-sdist/bin/pydantic-studio version
rm -rf .dist-smoke-wheel .dist-smoke-sdist
```

## Tagging

Only create the release tag after the local preflight and the main-branch CI
gate are green. The tag must match the package version exactly; for the
current package this is:

```bash
git tag v0.4.0
```

Pushing `v0.4.0` starts `.github/workflows/publish.yml`. The `build` job
aborts before publishing if the tag version differs from
`pydantic_studio.__version__`; `publish-pypi` and `publish-piesource` only run
after that build artifact exists, and `publish-result` reports the final
registry publish state.
