"""Tests for the release distribution metadata verifier."""

from __future__ import annotations

import importlib.util
import tarfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load_verifier() -> ModuleType:
    script = ROOT / "scripts" / "verify_distribution_metadata.py"
    spec = importlib.util.spec_from_file_location("verify_distribution_metadata", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_wheel(dist: Path, metadata: str) -> None:
    with zipfile.ZipFile(dist / "pydantic_studio-0.4.0-py3-none-any.whl", "w") as zf:
        zf.writestr("pydantic_studio-0.4.0.dist-info/METADATA", metadata)


def _write_sdist(
    dist: Path,
    filenames: tuple[str, ...],
    *,
    metadata: str | None = None,
) -> None:
    with tarfile.open(dist / "pydantic_studio-0.4.0.tar.gz", "w:gz") as tf:
        if metadata is not None:
            pkg_info = dist / "PKG-INFO"
            pkg_info.write_text(metadata, encoding="utf-8")
            tf.add(pkg_info, arcname="pydantic_studio-0.4.0/PKG-INFO")
        for filename in filenames:
            source = dist / filename
            source.write_text(filename, encoding="utf-8")
            tf.add(source, arcname=f"pydantic_studio-0.4.0/{filename}")


def _write_pyproject(root: Path) -> None:
    root.joinpath("pyproject.toml").write_text(
        """[project.urls]
Changelog = "https://example.invalid/CHANGELOG.md"
Security = "https://example.invalid/SECURITY.md"
Contributing = "https://example.invalid/CONTRIBUTING.md"

[tool.uv.build-backend]
source-include = ["CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md"]
""",
        encoding="utf-8",
    )


def _metadata(*, include_contributing: bool = True) -> str:
    lines = [
        "Project-URL: Changelog, https://example.invalid/CHANGELOG.md",
        "Project-URL: Security, https://example.invalid/SECURITY.md",
    ]
    if include_contributing:
        lines.append("Project-URL: Contributing, https://example.invalid/CONTRIBUTING.md")
    return "\n".join(lines)


def test_verify_distribution_metadata_accepts_expected_release_files(tmp_path: Path) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_sdist_file(tmp_path: Path) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata)
    _write_sdist(dist, ("CHANGELOG.md", "SECURITY.md"), metadata=metadata)

    with pytest.raises(RuntimeError, match=r"CONTRIBUTING\.md"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_project_url(tmp_path: Path) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata(include_contributing=False)
    _write_wheel(dist, metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=_metadata(),
    )

    with pytest.raises(RuntimeError, match=r"Contributing"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_sdist_project_url(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    _write_wheel(dist, _metadata())
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=_metadata(include_contributing=False),
    )

    with pytest.raises(RuntimeError, match=r"Contributing"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)
