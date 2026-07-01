"""Release-readiness documentation consistency checks."""

from __future__ import annotations

import tomllib
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]


def test_release_gate_docs_name_wheel_and_sdist_install_smokes() -> None:
    expected = "wheel and sdist install smoke gates"
    for doc in ("README.md", "CLAUDE.md"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        assert expected in text, f"{doc} should describe both package install smokes"


def test_release_gate_docs_use_current_test_counts() -> None:
    expectations = {
        "README.md": (
            "1251",
            "1212 default",
            "39 explicit Playwright browser e2e tests",
        ),
        "CLAUDE.md": (
            "1251",
            "1212 default",
            "39 explicit Playwright browser e2e tests",
        ),
    }
    for doc, snippets in expectations.items():
        text = (ROOT / doc).read_text(encoding="utf-8")
        normalized_text = " ".join(text.split())
        for snippet in snippets:
            assert snippet in normalized_text, f"{doc} should mention {snippet!r}"


def test_release_guide_names_console_script_entry_point_verification() -> None:
    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")

    assert "console script entry points" in guide


def test_workflow_jobs_have_timeout_limits() -> None:
    for workflow_name in ("ci.yml", "publish.yml"):
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        for job_name, job in workflow["jobs"].items():
            assert "timeout-minutes" in job, f"{workflow_name}:{job_name} needs a timeout"
            assert isinstance(job["timeout-minutes"], int)
            assert 1 <= job["timeout-minutes"] <= 60


def test_workflows_install_dependencies_from_locked_resolution() -> None:
    expected_install_commands = {
        ("ci.yml", "python"): "uv sync --locked --python ${{ matrix.python-version }}",
        ("ci.yml", "release-gate"): "uv sync --locked --all-extras --python 3.13",
        ("publish.yml", "build"): "uv sync --locked --all-extras --python 3.13",
    }
    for (workflow_name, job_name), expected in expected_install_commands.items():
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        steps = workflow["jobs"][job_name]["steps"]
        install_steps = [
            step for step in steps if step.get("name") == "Install Python dependencies"
        ]

        assert len(install_steps) == 1
        assert install_steps[0]["run"] == expected

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert "uv sync --locked" in guide


def test_release_guide_uses_publish_python_environment_for_local_preflight() -> None:
    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    install = "uv sync --locked --all-extras --python 3.13"
    default_tests = "uv run pytest -q"

    assert install in guide
    assert guide.index(install) < guide.index(default_tests)


def test_release_guide_verifies_uv_python_before_local_preflight_gates() -> None:
    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    install = "uv sync --locked --all-extras --python 3.13"
    version_check = "assert sys.version_info[:2] == (3, 13), sys.version"
    default_tests = "uv run pytest -q"

    assert version_check in guide
    assert guide.index(install) < guide.index(version_check) < guide.index(default_tests)


def test_release_gates_verify_project_metadata_version_matches_runtime() -> None:
    expected_run = """uv run python - <<'PY'
from pathlib import Path
import tomllib

import pydantic_studio as ps

pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
assert pyproject["project"]["version"] == ps.__version__, (
    pyproject["project"]["version"],
    ps.__version__,
)
PY
"""
    for workflow_name, job_name in {
        "ci.yml": "release-gate",
        "publish.yml": "build",
    }.items():
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        steps = workflow["jobs"][job_name]["steps"]
        metadata_steps = [
            step for step in steps if step.get("name") == "Verify package metadata version"
        ]

        assert len(metadata_steps) == 1
        assert metadata_steps[0]["run"] == expected_run

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert 'pyproject["project"]["version"] == ps.__version__' in guide


def test_workflows_define_concurrency_policies() -> None:
    ci = YAML(typ="safe").load(ROOT / ".github" / "workflows" / "ci.yml")
    publish = YAML(typ="safe").load(ROOT / ".github" / "workflows" / "publish.yml")

    assert ci["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": True,
    }
    assert publish["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": False,
    }


def test_workflows_do_not_persist_checkout_credentials() -> None:
    for workflow_name in ("ci.yml", "publish.yml"):
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        for job_name, job in workflow["jobs"].items():
            checkout_steps = [
                step for step in job.get("steps", []) if step.get("uses") == "actions/checkout@v4"
            ]
            for step in checkout_steps:
                assert step["with"] == {
                    "persist-credentials": False
                }, f"{workflow_name}:{job_name} must not persist checkout credentials"


def test_dependabot_keeps_automation_and_frontend_dependencies_current() -> None:
    dependabot = YAML(typ="safe").load(ROOT / ".github" / "dependabot.yml")

    assert dependabot == {
        "version": 2,
        "updates": [
            {
                "package-ecosystem": "github-actions",
                "directory": "/",
                "schedule": {
                    "interval": "weekly",
                    "day": "monday",
                    "time": "07:00",
                    "timezone": "Etc/UTC",
                },
                "open-pull-requests-limit": 5,
                "commit-message": {"prefix": "ci"},
            },
            {
                "package-ecosystem": "npm",
                "directory": "/frontend",
                "schedule": {
                    "interval": "weekly",
                    "day": "monday",
                    "time": "07:15",
                    "timezone": "Etc/UTC",
                },
                "open-pull-requests-limit": 5,
                "commit-message": {"prefix": "chore(frontend)"},
            },
        ],
    }


def test_publish_workflow_uses_package_name_and_read_only_default_token() -> None:
    workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / "publish.yml")

    assert workflow["name"] == "Publish packages"
    assert workflow["permissions"] == {"contents": "read"}


def test_publish_workflow_uses_trusted_publishing_without_api_token_secret() -> None:
    workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / "publish.yml")
    build_job = workflow["jobs"]["build"]
    publish_job = workflow["jobs"]["publish-pypi"]

    assert build_job["permissions"] == {"contents": "read"}
    assert publish_job["environment"]["name"] == "pypi"
    assert publish_job["environment"]["url"] == "https://pypi.org/p/pydantic-studio"
    assert publish_job["permissions"] == {"id-token": "write"}

    publish_steps = [
        step
        for step in publish_job["steps"]
        if step.get("uses") == "pypa/gh-action-pypi-publish@release/v1"
    ]
    assert len(publish_steps) == 1
    assert "with" not in publish_steps[0]
    assert publish_steps[0]["continue-on-error"] is True


def test_publish_workflow_pushes_to_piesource_independently() -> None:
    workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / "publish.yml")
    publish_job = workflow["jobs"]["publish-piesource"]

    assert publish_job["needs"] == "build"
    publish_steps = [
        step
        for step in publish_job["steps"]
        if step.get("uses") == "pypa/gh-action-pypi-publish@release/v1"
    ]
    assert len(publish_steps) == 1
    assert publish_steps[0]["continue-on-error"] is True
    assert publish_steps[0]["with"] == {
        "repository-url": "${{ secrets.PIESOURCE_REPOSITORY_URL }}",
        "user": "${{ secrets.PIESOURCE_USERNAME }}",
        "password": "${{ secrets.PIESOURCE_PASSWORD }}",
    }


def test_publish_workflow_reports_registry_publish_failures_after_both_attempts() -> None:
    workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / "publish.yml")

    assert workflow["jobs"]["publish-pypi"]["outputs"] == {
        "publish-outcome": "${{ steps.publish-pypi.outcome }}"
    }
    assert workflow["jobs"]["publish-piesource"]["outputs"] == {
        "publish-outcome": "${{ steps.publish-piesource.outcome }}"
    }

    result_job = workflow["jobs"]["publish-result"]
    assert result_job["needs"] == ["publish-pypi", "publish-piesource"]
    assert result_job["if"] == "${{ always() }}"
    assert "One or more registry publishes failed" in result_job["steps"][0]["run"]


def test_publish_workflow_uploads_release_artifact_strictly() -> None:
    workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / "publish.yml")
    build_steps = workflow["jobs"]["build"]["steps"]

    upload_steps = [
        step for step in build_steps if step.get("uses") == "actions/upload-artifact@v4"
    ]
    assert len(upload_steps) == 1
    assert upload_steps[0]["with"] == {
        "name": "python-package-distributions",
        "path": "dist/",
        "if-no-files-found": "error",
        "retention-days": 30,
    }

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert "fails immediately if no distributions are present" in guide
    assert "retains that artifact for 30 days" in guide


def test_distribution_build_steps_start_from_clean_dist_directory() -> None:
    workflow_jobs = {
        "ci.yml": "release-gate",
        "publish.yml": "build",
    }
    for workflow_name, job_name in workflow_jobs.items():
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        steps = workflow["jobs"][job_name]["steps"]
        build_steps = [step for step in steps if step.get("name") == "Build distributions"]

        assert len(build_steps) == 1
        assert build_steps[0]["run"] == "rm -rf dist\nuv build\n"

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert "rm -rf dist\nuv build" in guide


def test_distribution_release_metadata_is_verified_before_install_smokes() -> None:
    workflow_jobs = {
        "ci.yml": "release-gate",
        "publish.yml": "build",
    }
    command = "uv run python scripts/verify_distribution_metadata.py dist"
    for workflow_name, job_name in workflow_jobs.items():
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        steps = workflow["jobs"][job_name]["steps"]
        names = [step.get("name") for step in steps]
        verify_index = names.index("Verify distribution release metadata")
        wheel_smoke_index = names.index("Smoke-test wheel install")
        verify_step = steps[verify_index]

        assert names.index("Check distribution metadata") < verify_index < wheel_smoke_index
        assert verify_step["run"] == command

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert guide.index("uv run twine check dist/*") < guide.index(command) < guide.index(
        "rm -rf .dist-smoke-wheel"
    )


def test_distribution_release_metadata_uses_shared_verifier_script() -> None:
    command = "uv run python scripts/verify_distribution_metadata.py dist"

    assert (ROOT / "scripts" / "verify_distribution_metadata.py").is_file()

    for workflow_name, job_name in {
        "ci.yml": "release-gate",
        "publish.yml": "build",
    }.items():
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        steps = workflow["jobs"][job_name]["steps"]
        verify_steps = [
            step for step in steps if step.get("name") == "Verify distribution release metadata"
        ]

        assert len(verify_steps) == 1
        assert verify_steps[0]["run"] == command

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert command in guide
    assert "zipfile.ZipFile(wheel)" not in guide


def test_distribution_smoke_tests_start_from_clean_virtualenvs() -> None:
    workflow_jobs = {
        "ci.yml": "release-gate",
        "publish.yml": "build",
    }
    for workflow_name, job_name in workflow_jobs.items():
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        steps = workflow["jobs"][job_name]["steps"]
        smoke_steps = {
            step.get("name"): step["run"]
            for step in steps
            if "Smoke-test" in step.get("name", "")
        }

        assert smoke_steps["Smoke-test wheel install"].startswith(
            "rm -rf .dist-smoke-wheel\npython -m venv .dist-smoke-wheel\n"
        )
        assert smoke_steps["Smoke-test source distribution install"].startswith(
            "rm -rf .dist-smoke-sdist\npython -m venv .dist-smoke-sdist\n"
        )

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert "rm -rf .dist-smoke-wheel\nuv run python -m venv .dist-smoke-wheel" in guide
    assert "rm -rf .dist-smoke-sdist\nuv run python -m venv .dist-smoke-sdist" in guide


def test_release_guide_uses_uv_python_for_local_smoke_virtualenvs() -> None:
    lines = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8").splitlines()

    for env_name in ("wheel", "sdist", "email"):
        assert f"uv run python -m venv .dist-smoke-{env_name}" in lines
        assert f"python -m venv .dist-smoke-{env_name}" not in lines


def test_release_guide_uses_uv_python_for_local_wheel_discovery() -> None:
    lines = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8").splitlines()

    assert "  uv run python - <<'PY'" in lines
    assert "  python - <<'PY'" not in lines


def test_distribution_smoke_tests_verify_typed_marker_and_frontend_bundle() -> None:
    workflow_jobs = {
        "ci.yml": "release-gate",
        "publish.yml": "build",
    }
    required_snippets = [
        'resources.files("pydantic_studio").joinpath("py.typed").is_file()',
        '"renderers/html/static/dist/index.html"',
    ]
    for workflow_name, job_name in workflow_jobs.items():
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        steps = workflow["jobs"][job_name]["steps"]
        smoke_steps = [
            step["run"]
            for step in steps
            if step.get("name")
            in {
                "Smoke-test wheel install",
                "Smoke-test source distribution install",
            }
        ]

        assert len(smoke_steps) == 2
        for run in smoke_steps:
            for snippet in required_snippets:
                assert snippet in run

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert ".dist-smoke-wheel/bin/python - <<'PY'" in guide
    assert ".dist-smoke-sdist/bin/python - <<'PY'" in guide
    for snippet in required_snippets:
        assert snippet in guide


def test_distribution_smoke_tests_verify_email_extra_install() -> None:
    workflow_jobs = {
        "ci.yml": "release-gate",
        "publish.yml": "build",
    }
    required_snippets = [
        "Smoke-test email extra install",
        "rm -rf .dist-smoke-email",
        "python -m venv .dist-smoke-email",
        'pip install "${wheel}[email]"',
        "import email_validator",
    ]
    for workflow_name, job_name in workflow_jobs.items():
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        steps = workflow["jobs"][job_name]["steps"]
        email_steps = [
            step for step in steps if step.get("name") == "Smoke-test email extra install"
        ]

        assert len(email_steps) == 1
        for snippet in required_snippets[1:]:
            assert snippet in email_steps[0]["run"]

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    for snippet in required_snippets:
        assert snippet in guide


def test_package_metadata_exposes_support_project_urls() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    urls = pyproject["project"]["urls"]

    assert urls == {
        "Source": "https://github.com/invoker-bot/pydantic-studio",
        "Documentation": "https://github.com/invoker-bot/pydantic-studio/tree/main/docs/site",
        "Issues": "https://github.com/invoker-bot/pydantic-studio/issues",
        "Changelog": "https://github.com/invoker-bot/pydantic-studio/blob/main/CHANGELOG.md",
        "Security": "https://github.com/invoker-bot/pydantic-studio/blob/main/SECURITY.md",
        "Contributing": "https://github.com/invoker-bot/pydantic-studio/blob/main/CONTRIBUTING.md",
    }

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert "Source, Documentation, Issues, Changelog," in guide


def test_package_metadata_exposes_changelog_and_release_notes() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    urls = pyproject["project"]["urls"]

    assert urls["Changelog"] == (
        "https://github.com/invoker-bot/pydantic-studio/blob/main/CHANGELOG.md"
    )

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    required_snippets = [
        "# Changelog",
        "## 0.4.0",
        "Interactive editor for Pydantic models",
        "wheel and sdist install smoke gates",
        "GitHub OIDC Trusted Publishing",
    ]
    for snippet in required_snippets:
        assert snippet in changelog

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert "Changelog project URL" in guide


def test_source_distribution_includes_changelog_file() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "CHANGELOG.md" in pyproject["tool"]["uv"]["build-backend"]["source-include"]


def test_package_metadata_exposes_security_policy() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["urls"]["Security"] == (
        "https://github.com/invoker-bot/pydantic-studio/blob/main/SECURITY.md"
    )
    assert "SECURITY.md" in pyproject["tool"]["uv"]["build-backend"]["source-include"]

    policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    for snippet in (
        "# Security Policy",
        "Supported Versions",
        "Reporting a Vulnerability",
        "Do not report suspected vulnerabilities in public issues",
    ):
        assert snippet in policy

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert "Security project URL" in guide


def test_package_metadata_exposes_contributing_guide() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["urls"]["Contributing"] == (
        "https://github.com/invoker-bot/pydantic-studio/blob/main/CONTRIBUTING.md"
    )
    assert "CONTRIBUTING.md" in pyproject["tool"]["uv"]["build-backend"]["source-include"]

    guide = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for snippet in (
        "# Contributing",
        "uv sync",
        "uv run pytest -q",
        "Do not push to origin without maintainer confirmation",
    ):
        assert snippet in guide

    release = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert "Contributing project URL" in release


def test_package_metadata_exposes_license_and_discovery_terms() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert "License :: OSI Approved :: MIT License" in project["classifiers"]
    assert project["keywords"] == [
        "config",
        "editor",
        "fastapi",
        "pydantic",
        "textual",
    ]

    guide = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    assert "MIT license classifier and PyPI search keywords" in guide


def test_release_guide_documents_external_trusted_publisher_setup() -> None:
    guide = ROOT / "docs" / "site" / "release.md"
    text = guide.read_text(encoding="utf-8")

    required_snippets = [
        "# Release",
        "GitHub Actions",
        "invoker-bot/pydantic-studio",
        ".github/workflows/publish.yml",
        "pypi",
        "https://pypi.org/p/pydantic-studio",
        "Do not create or store a `PYPI_API_TOKEN`",
        "uv run pytest -q",
        "uv run python -m pytest tests/e2e -p playwright -o \"addopts=-ra\"",
        "uv build",
        "uv run twine check dist/*",
        "v0.4.0",
    ]
    for snippet in required_snippets:
        assert snippet in text

    mkdocs = YAML(typ="safe").load(ROOT / "mkdocs.yml")
    assert {"Release": "release.md"} in mkdocs["nav"]


def test_release_guide_checks_tag_matches_package_version_before_tagging() -> None:
    text = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    required_snippets = [
        'RELEASE_TAG="v0.4.0"',
        'tag_version="${RELEASE_TAG#v}"',
        "pkg_version=$(uv run python -c 'import pydantic_studio as ps; print(ps.__version__)')",
        'if [ "$tag_version" != "$pkg_version" ]; then',
        'git tag "$RELEASE_TAG"',
    ]
    for snippet in required_snippets:
        assert snippet in text

    assert text.index('if [ "$tag_version" != "$pkg_version" ]; then') < text.index(
        'git tag "$RELEASE_TAG"'
    )


def test_release_guide_requires_clean_origin_main_before_tagging() -> None:
    text = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    fetch = "git fetch origin main:refs/remotes/origin/main"
    clean = 'if [ -n "$(git status --short)" ]; then'
    origin_main = 'if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then'
    tag = 'git tag "$RELEASE_TAG"'

    for snippet in (
        fetch,
        clean,
        "Worktree has uncommitted changes",
        origin_main,
        "HEAD does not match origin/main",
    ):
        assert snippet in text

    assert text.index(fetch) < text.index(clean) < text.index(origin_main) < text.index(tag)


def test_release_guide_verifies_main_ci_status_before_tagging() -> None:
    text = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    origin_main = 'if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then'
    ci_check = "gh run list"
    tag = 'git tag "$RELEASE_TAG"'

    for snippet in (
        "GitHub CLI",
        ci_check,
        "--workflow CI",
        "--branch main",
        '--commit "$(git rev-parse HEAD)"',
        "--json conclusion,status",
        "completed success",
        "CI is not green",
    ):
        assert snippet in text

    assert text.index(origin_main) < text.index(ci_check) < text.index(tag)


def test_release_guide_pushes_verified_release_tag_after_tagging() -> None:
    text = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    tag = 'git tag "$RELEASE_TAG"'
    push = 'git push origin "$RELEASE_TAG"'
    workflow = "Pushing `v0.4.0` starts `.github/workflows/publish.yml`"

    assert push in text
    assert text.index(tag) < text.index(push) < text.index(workflow)


def test_release_guide_installs_playwright_browser_before_e2e() -> None:
    text = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    install = "uv run playwright install --with-deps chromium"
    e2e = 'uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra"'

    assert install in text
    assert text.index(install) < text.index(e2e)


def test_release_guide_installs_frontend_dependencies_before_bundle_build() -> None:
    text = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    install = "pnpm install --frozen-lockfile"
    build = "pnpm build"

    assert install in text
    assert text.index(install) < text.index(build)


def test_release_guide_checks_committed_frontend_bundle_after_build() -> None:
    text = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")
    build = "pnpm build"
    drift_check = "git diff --exit-code -- src/pydantic_studio/renderers/html/static/dist"
    e2e = 'uv run python -m pytest tests/e2e -p playwright -o "addopts=-ra"'

    assert drift_check in text
    assert text.index(build) < text.index(drift_check) < text.index(e2e)


def test_release_guide_documents_independent_piesource_publish() -> None:
    text = (ROOT / "docs" / "site" / "release.md").read_text(encoding="utf-8")

    required_snippets = [
        "publish-pypi",
        "publish-piesource",
        "PIESOURCE_REPOSITORY_URL",
        "PIESOURCE_USERNAME",
        "PIESOURCE_PASSWORD",
        "PyPI publish failed",
        "piesource publish failed",
        "publish-result",
        "One or more registry publishes failed",
        "independent",
    ]
    for snippet in required_snippets:
        assert snippet in text


def test_docs_site_metadata_matches_project_source_url_without_placeholders() -> None:
    mkdocs = YAML(typ="safe").load(ROOT / "mkdocs.yml")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    source_url = pyproject["project"]["urls"]["Source"]

    assert mkdocs["repo_url"] == source_url
    assert mkdocs.get("site_url") != "https://pydantic-studio.example"
