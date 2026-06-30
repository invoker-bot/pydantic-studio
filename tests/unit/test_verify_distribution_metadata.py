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


def _write_wheel(
    dist: Path,
    metadata: str,
    *,
    metadata_name: str = "pydantic_studio-0.4.0.dist-info/METADATA",
    entry_points_name: str = "pydantic_studio-0.4.0.dist-info/entry_points.txt",
    entry_points: str = "[console_scripts]\npydantic-studio = pydantic_studio.cli:app\n",
) -> None:
    with zipfile.ZipFile(dist / "pydantic_studio-0.4.0-py3-none-any.whl", "w") as zf:
        zf.writestr(metadata_name, metadata)
        if entry_points:
            zf.writestr(entry_points_name, entry_points)


def _write_sdist(
    dist: Path,
    filenames: tuple[str, ...],
    *,
    metadata: str | None = None,
    metadata_name: str = "pydantic_studio-0.4.0/PKG-INFO",
) -> None:
    with tarfile.open(dist / "pydantic_studio-0.4.0.tar.gz", "w:gz") as tf:
        if metadata is not None:
            pkg_info = dist / "PKG-INFO"
            pkg_info.write_text(metadata, encoding="utf-8")
            tf.add(pkg_info, arcname=metadata_name)
        for filename in filenames:
            source = dist / filename
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(filename, encoding="utf-8")
            tf.add(source, arcname=f"pydantic_studio-0.4.0/{filename}")


def _write_pyproject(
    root: Path,
    *,
    extra_source_include: tuple[str, ...] = (),
) -> None:
    source_include = (
        '"CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md"'
        + "".join(f', "{filename}"' for filename in extra_source_include)
    )
    root.joinpath("pyproject.toml").write_text(
        f"""[project]
name = "pydantic-studio"
version = "0.4.0"
requires-python = ">=3.11"
license = "MIT"
license-files = ["LICENSE"]
keywords = ["config", "editor", "fastapi", "pydantic", "textual"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "License :: OSI Approved :: MIT License",
  "Typing :: Typed",
]
dependencies = [
  "pydantic>=2.7",
  "typer>=0.12",
]

[project.scripts]
pydantic-studio = "pydantic_studio.cli:app"

[project.optional-dependencies]
email = ["email-validator>=2"]

[project.urls]
Source = "https://example.invalid/pydantic-studio"
Documentation = "https://example.invalid/docs"
Issues = "https://example.invalid/issues"
Changelog = "https://example.invalid/CHANGELOG.md"
Security = "https://example.invalid/SECURITY.md"
Contributing = "https://example.invalid/CONTRIBUTING.md"

[tool.uv.build-backend]
source-include = [{source_include}]
""",
        encoding="utf-8",
    )


def _metadata(*, omit: str | None = None) -> str:
    lines = [
        ("Name", "pydantic-studio"),
        ("Version", "0.4.0"),
        ("Requires-Python", ">=3.11"),
        ("Keywords", "config,editor,fastapi,pydantic,textual"),
        ("License-Expression", "MIT"),
        ("License-File", "LICENSE"),
        ("Classifier", "Development Status :: 3 - Alpha"),
        ("Classifier", "License :: OSI Approved :: MIT License"),
        ("Classifier", "Typing :: Typed"),
        ("Requires-Dist", "pydantic>=2.7"),
        ("Requires-Dist", "typer>=0.12"),
        ("Requires-Dist", "email-validator>=2 ; extra == 'email'"),
        ("Provides-Extra", "email"),
        ("Source", "https://example.invalid/pydantic-studio"),
        ("Documentation", "https://example.invalid/docs"),
        ("Issues", "https://example.invalid/issues"),
        ("Changelog", "https://example.invalid/CHANGELOG.md"),
        ("Security", "https://example.invalid/SECURITY.md"),
        ("Contributing", "https://example.invalid/CONTRIBUTING.md"),
    ]
    return "\n".join(
        f"{label}: {url}"
        if label
        in {
            "Name",
            "Version",
            "Requires-Python",
            "Keywords",
            "License-Expression",
            "License-File",
            "Classifier",
            "Requires-Dist",
            "Provides-Extra",
        }
        else f"Project-URL: {label}, {url}"
        for label, url in lines
        if label != omit
    )


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


def test_verify_distribution_metadata_rejects_wheel_metadata_decoy_path(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata, metadata_name="pydantic_studio/METADATA")
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"METADATA"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_nested_wheel_dist_info_metadata_decoy(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(
        dist,
        metadata,
        metadata_name="pydantic_studio/nested.dist-info/METADATA",
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"METADATA"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_nested_wheel_dist_info_entry_point_decoy(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(
        dist,
        metadata,
        entry_points_name="pydantic_studio/nested.dist-info/entry_points.txt",
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"pydantic-studio"):
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


def test_verify_distribution_metadata_rejects_sdist_pkg_info_decoy_path(
    tmp_path: Path,
) -> None:
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
        metadata_name="pydantic_studio-0.4.0/docs/PKG-INFO",
    )

    with pytest.raises(RuntimeError, match=r"PKG-INFO"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_nested_sdist_file_decoy(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata)
    _write_sdist(
        dist,
        ("docs/CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"CHANGELOG\.md"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_declared_source_include(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path, extra_source_include=("NOTICE.md",))
    metadata = _metadata()
    _write_wheel(dist, metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"NOTICE\.md"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_project_url(tmp_path: Path) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata(omit="Contributing")
    _write_wheel(dist, metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=_metadata(),
    )

    with pytest.raises(RuntimeError, match=r"Contributing"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_declared_project_url(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata(omit="Source")
    _write_wheel(dist, metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=_metadata(),
    )

    with pytest.raises(RuntimeError, match=r"Source"):
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
        metadata=_metadata(omit="Contributing"),
    )

    with pytest.raises(RuntimeError, match=r"Contributing"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [("Name", "wrong-name"), ("Version", "9.9.9")],
)
@pytest.mark.parametrize("drifted_file", ["wheel", "sdist"])
def test_verify_distribution_metadata_rejects_identity_metadata_drift(
    tmp_path: Path,
    field_name: str,
    bad_value: str,
    drifted_file: str,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    expected_metadata = _metadata()
    old_line = next(line for line in expected_metadata.splitlines() if line.startswith(field_name))
    drifted_metadata = expected_metadata.replace(old_line, f"{field_name}: {bad_value}")
    _write_wheel(dist, drifted_metadata if drifted_file == "wheel" else expected_metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=drifted_metadata if drifted_file == "sdist" else expected_metadata,
    )

    with pytest.raises(RuntimeError, match=field_name):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


@pytest.mark.parametrize("drifted_file", ["wheel", "sdist"])
def test_verify_distribution_metadata_rejects_requires_python_metadata_drift(
    tmp_path: Path,
    drifted_file: str,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    expected_metadata = _metadata()
    drifted_metadata = expected_metadata.replace(
        "Requires-Python: >=3.11",
        "Requires-Python: >=3.12",
    )
    _write_wheel(dist, drifted_metadata if drifted_file == "wheel" else expected_metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=drifted_metadata if drifted_file == "sdist" else expected_metadata,
    )

    with pytest.raises(RuntimeError, match=r"Requires-Python"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


@pytest.mark.parametrize(
    "missing_line",
    [
        "Keywords: config,editor,fastapi,pydantic,textual",
        "Classifier: Typing :: Typed",
        "License-Expression: MIT",
        "License-File: LICENSE",
    ],
)
@pytest.mark.parametrize("drifted_file", ["wheel", "sdist"])
def test_verify_distribution_metadata_rejects_registry_metadata_drift(
    tmp_path: Path,
    missing_line: str,
    drifted_file: str,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    expected_metadata = _metadata()
    drifted_metadata = "\n".join(
        line for line in expected_metadata.splitlines() if line != missing_line
    )
    _write_wheel(dist, drifted_metadata if drifted_file == "wheel" else expected_metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=drifted_metadata if drifted_file == "sdist" else expected_metadata,
    )

    with pytest.raises(RuntimeError, match=missing_line.split(":", 1)[0]):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


@pytest.mark.parametrize(
    "missing_line",
    [
        "Requires-Dist: pydantic>=2.7",
        "Requires-Dist: email-validator>=2 ; extra == 'email'",
        "Provides-Extra: email",
    ],
)
@pytest.mark.parametrize("drifted_file", ["wheel", "sdist"])
def test_verify_distribution_metadata_rejects_dependency_metadata_drift(
    tmp_path: Path,
    missing_line: str,
    drifted_file: str,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    expected_metadata = _metadata()
    drifted_metadata = "\n".join(
        line for line in expected_metadata.splitlines() if line != missing_line
    )
    _write_wheel(dist, drifted_metadata if drifted_file == "wheel" else expected_metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=drifted_metadata if drifted_file == "sdist" else expected_metadata,
    )

    with pytest.raises(RuntimeError, match=missing_line.split(":", 1)[0]):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


@pytest.mark.parametrize("drifted_file", ["wheel", "sdist"])
def test_verify_distribution_metadata_ignores_metadata_mentions_in_description(
    tmp_path: Path,
    drifted_file: str,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    expected_metadata = _metadata()
    missing_line = "Requires-Dist: pydantic>=2.7"
    drifted_metadata = "\n".join(
        line for line in expected_metadata.splitlines() if line != missing_line
    )
    drifted_metadata = (
        f"{drifted_metadata}\n\n"
        "The long description can mention release metadata examples such as "
        f"{missing_line} without declaring the header."
    )
    _write_wheel(dist, drifted_metadata if drifted_file == "wheel" else expected_metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=drifted_metadata if drifted_file == "sdist" else expected_metadata,
    )

    with pytest.raises(RuntimeError, match=r"Requires-Dist"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


@pytest.mark.parametrize(
    "entry_points",
    [
        "",
        "[console_scripts]\npydantic-studio = wrong.module:app\n",
    ],
)
def test_verify_distribution_metadata_rejects_console_script_entry_point_drift(
    tmp_path: Path,
    entry_points: str,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata, entry_points=entry_points)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"pydantic-studio"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)
