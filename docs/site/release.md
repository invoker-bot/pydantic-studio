# Release

This project publishes from Git tags through GitHub Actions. The release
workflow builds the frontend bundle, runs the Python/browser/package gates,
checks the tag against `pydantic_studio.__version__`, builds both package
formats, smoke-tests wheel and sdist installs, uploads the distributions as
one release artifact, and then publishes that artifact to PyPI and piesource.
The artifact upload fails immediately if no distributions are present and
retains that artifact for 30 days for release troubleshooting.
The release metadata verifier checks the package Name, Version, Summary, Author,
Description-Content-Type, Requires-Python, license files, classifiers, keywords,
dependencies, optional extras, and every declared Project-URL in both the wheel
`METADATA` and the sdist `PKG-INFO`, confirms the wheel `.dist-info` identity,
structure files, purelib flag, compatibility tag, declared license files,
package `__init__.py`, `py.typed` marker, console script target modules,
packaged web static bundle files plus the assets referenced by `index.html`,
`RECORD` entries, and console script entry points match `[project.scripts]`,
then confirms `pyproject.toml`, the declared README file, the sdist package
`__init__.py`, the sdist `py.typed` marker, the sdist console script target
modules, the sdist web static bundle files plus the assets referenced by
`index.html`, and every explicit `source-include` entry are
present in the source archive. The Changelog, Security, and Contributing URL
targets must also be listed in `source-include`.
The package metadata exposes Source, Documentation, Issues, Changelog,
Security, and Contributing project URLs so registry pages have clear support,
navigation, release history, vulnerability-reporting links, and contributor
setup guidance. The Changelog project URL points to `CHANGELOG.md`; the
Security project URL points to `SECURITY.md`; the Contributing project URL
points to `CONTRIBUTING.md`.
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
uv sync --locked --all-extras --python 3.13
uv run python - <<'PY'
import sys

assert sys.version_info[:2] == (3, 13), sys.version
PY
uv run python - <<'PY'
from pathlib import Path
import tomllib

import pydantic_studio as ps

pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
assert pyproject["project"]["version"] == ps.__version__, (
    pyproject["project"]["version"],
    ps.__version__,
)
PY
uv run pytest -q
uv run ruff check
uv run pyright src/pydantic_studio
uv run mkdocs build --strict
cd frontend
pnpm install --frozen-lockfile
pnpm build
cd ..
git diff --exit-code -- src/pydantic_studio/renderers/html/static/dist
uv run playwright install --with-deps chromium
uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra"
rm -rf dist
uv build
uv run twine check dist/*
uv run python scripts/verify_distribution_metadata.py dist
rm -rf .dist-smoke-wheel
uv run python -m venv .dist-smoke-wheel
.dist-smoke-wheel/bin/python -m pip install dist/*.whl
.dist-smoke-wheel/bin/pydantic-studio version
.dist-smoke-wheel/bin/python - <<'PY'
from importlib import resources

import pydantic_studio as ps

assert ps.__version__
assert resources.files("pydantic_studio").joinpath("py.typed").is_file()
assert resources.files("pydantic_studio").joinpath(
    "renderers/html/static/dist/index.html"
).is_file()
PY
rm -rf .dist-smoke-sdist
uv run python -m venv .dist-smoke-sdist
.dist-smoke-sdist/bin/python -m pip install dist/*.tar.gz
.dist-smoke-sdist/bin/pydantic-studio version
.dist-smoke-sdist/bin/python - <<'PY'
from importlib import resources

import pydantic_studio as ps

assert ps.__version__
assert resources.files("pydantic_studio").joinpath("py.typed").is_file()
assert resources.files("pydantic_studio").joinpath(
    "renderers/html/static/dist/index.html"
).is_file()
PY
# Smoke-test email extra install
rm -rf .dist-smoke-email
uv run python -m venv .dist-smoke-email
wheel=$(
  uv run python - <<'PY'
from pathlib import Path

wheels = sorted(Path("dist").glob("*.whl"))
assert len(wheels) == 1, wheels
print(wheels[0])
PY
)
.dist-smoke-email/bin/python -m pip install "${wheel}[email]"
.dist-smoke-email/bin/python - <<'PY'
import email_validator

assert email_validator
PY
rm -rf .dist-smoke-wheel .dist-smoke-sdist .dist-smoke-email
```

## Tagging

Only create the release tag after the local preflight and the main-branch CI
gate are green. The tagging check uses the GitHub CLI (`gh`) authenticated to
this repository. The tag must match the package version exactly; for the
current package this is:

```bash
git fetch origin main:refs/remotes/origin/main
if [ -n "$(git status --short)" ]; then
  echo "Worktree has uncommitted changes"
  exit 1
fi
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "HEAD does not match origin/main"
  exit 1
fi
ci_status=$(
  gh run list \
    --workflow CI \
    --branch main \
    --commit "$(git rev-parse HEAD)" \
    --limit 1 \
    --json conclusion,status \
    --jq '.[0] | "\(.status) \(.conclusion)"'
)
if [ "$ci_status" != "completed success" ]; then
  echo "CI is not green for $(git rev-parse --short HEAD): ${ci_status:-no run found}"
  exit 1
fi
RELEASE_TAG="v0.4.0"
tag_version="${RELEASE_TAG#v}"
pkg_version=$(uv run python -c 'import pydantic_studio as ps; print(ps.__version__)')
if [ "$tag_version" != "$pkg_version" ]; then
  echo "Tag ${RELEASE_TAG} (${tag_version}) != package ${pkg_version}"
  exit 1
fi
git tag "$RELEASE_TAG"
git push origin "$RELEASE_TAG"
```

Pushing `v0.4.0` starts `.github/workflows/publish.yml`. The `build` job
aborts before publishing if the tag version differs from
`pydantic_studio.__version__`; `publish-pypi` and `publish-piesource` only run
after that build artifact exists, and `publish-result` reports the final
registry publish state.
