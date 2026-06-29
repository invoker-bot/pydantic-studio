# Release

This project publishes from Git tags through GitHub Actions. The release
workflow builds the frontend bundle, runs the Python/browser/package gates,
checks the tag against `pydantic_studio.__version__`, builds both package
formats, smoke-tests wheel and sdist installs, and then publishes to PyPI.

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

## Local preflight

Run the same gates before tagging:

```bash
uv run pytest -q
uv run ruff check
uv run pyright src/pydantic_studio
uv run mkdocs build --strict
cd frontend && pnpm build && cd ..
uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra"
uv build
uv run twine check dist/*
python -m venv .dist-smoke-wheel
.dist-smoke-wheel/bin/python -m pip install dist/*.whl
.dist-smoke-wheel/bin/pydantic-studio version
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

Pushing `v0.4.0` starts `.github/workflows/publish.yml`. The workflow aborts
before publishing if the tag version differs from `pydantic_studio.__version__`.
