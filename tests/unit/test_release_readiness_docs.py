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
        "README.md": ("818", "795 default"),
        "CLAUDE.md": ("818", "795 default"),
    }
    for doc, snippets in expectations.items():
        text = (ROOT / doc).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, f"{doc} should mention {snippet!r}"


def test_workflow_jobs_have_timeout_limits() -> None:
    for workflow_name in ("ci.yml", "publish.yml"):
        workflow = YAML(typ="safe").load(ROOT / ".github" / "workflows" / workflow_name)
        for job_name, job in workflow["jobs"].items():
            assert "timeout-minutes" in job, f"{workflow_name}:{job_name} needs a timeout"
            assert isinstance(job["timeout-minutes"], int)
            assert 1 <= job["timeout-minutes"] <= 60


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
