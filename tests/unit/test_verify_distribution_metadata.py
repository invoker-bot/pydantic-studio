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
    wheel_name: str = "pydantic_studio-0.4.0-py3-none-any.whl",
    metadata_name: str = "pydantic_studio-0.4.0.dist-info/METADATA",
    entry_points_name: str = "pydantic_studio-0.4.0.dist-info/entry_points.txt",
    entry_points: str = "[console_scripts]\npydantic-studio = pydantic_studio.cli:app\n",
    license_files: tuple[str, ...] = ("LICENSE",),
    package_init: str | None = "pydantic_studio/__init__.py",
    package_init_content: str = "__version__ = '0.4.0'\n",
    cli_module: str | None = "pydantic_studio/cli.py",
    cli_module_content: str = "app = object()\n",
    typed_marker: str | None = "pydantic_studio/py.typed",
    static_bundle: tuple[str, ...] = (
        "pydantic_studio/renderers/html/static/dist/index.html",
        "pydantic_studio/renderers/html/static/dist/assets/index-test.css",
        "pydantic_studio/renderers/html/static/dist/assets/index-test.js",
    ),
    static_index_html: str = (
        '<script type="module" src="/static/dist/assets/index-test.js"></script>\n'
        '<link rel="stylesheet" href="/static/dist/assets/index-test.css">\n'
    ),
    wheel_metadata: str | None = "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    record: str | None = (
        "pydantic_studio/__init__.py,,\n"
        "pydantic_studio/cli.py,,\n"
        "pydantic_studio/py.typed,,\n"
        "pydantic_studio/renderers/html/static/dist/index.html,,\n"
        "pydantic_studio/renderers/html/static/dist/assets/index-test.css,,\n"
        "pydantic_studio/renderers/html/static/dist/assets/index-test.js,,\n"
        "pydantic_studio-0.4.0.dist-info/METADATA,,\n"
        "pydantic_studio-0.4.0.dist-info/WHEEL,,\n"
        "pydantic_studio-0.4.0.dist-info/entry_points.txt,,\n"
        "pydantic_studio-0.4.0.dist-info/licenses/LICENSE,,\n"
        "pydantic_studio-0.4.0.dist-info/RECORD,,\n"
    ),
) -> None:
    with zipfile.ZipFile(dist / wheel_name, "w") as zf:
        zf.writestr(metadata_name, metadata)
        if package_init is not None:
            zf.writestr(package_init, package_init_content)
        if cli_module is not None:
            zf.writestr(cli_module, cli_module_content)
        if typed_marker is not None:
            zf.writestr(typed_marker, "")
        for filename in static_bundle:
            content = static_index_html if filename.endswith("/index.html") else filename
            zf.writestr(filename, content)
        if entry_points:
            zf.writestr(entry_points_name, entry_points)
        for filename in license_files:
            zf.writestr(f"pydantic_studio-0.4.0.dist-info/licenses/{filename}", filename)
        if wheel_metadata is not None:
            zf.writestr("pydantic_studio-0.4.0.dist-info/WHEEL", wheel_metadata)
        if record is not None:
            zf.writestr("pydantic_studio-0.4.0.dist-info/RECORD", record)


def _write_sdist(
    dist: Path,
    filenames: tuple[str, ...],
    *,
    sdist_name: str = "pydantic_studio-0.4.0.tar.gz",
    sdist_root: str = "pydantic_studio-0.4.0",
    pyproject: str | None = "pyproject.toml",
    readme: str | None = "README.md",
    license_files: tuple[str, ...] = ("LICENSE",),
    package_init: str | None = "src/pydantic_studio/__init__.py",
    package_init_content: str = "__version__ = '0.4.0'\n",
    cli_module: str | None = "src/pydantic_studio/cli.py",
    cli_module_content: str = "app = object()\n",
    typed_marker: str | None = "src/pydantic_studio/py.typed",
    static_bundle: tuple[str, ...] = (
        "src/pydantic_studio/renderers/html/static/dist/index.html",
        "src/pydantic_studio/renderers/html/static/dist/assets/index-test.css",
        "src/pydantic_studio/renderers/html/static/dist/assets/index-test.js",
    ),
    static_index_html: str = (
        '<script type="module" src="/static/dist/assets/index-test.js"></script>\n'
        '<link rel="stylesheet" href="/static/dist/assets/index-test.css">\n'
    ),
    metadata: str | None = None,
    metadata_name: str | None = None,
) -> None:
    root_pkg_info = metadata_name if metadata_name is not None else f"{sdist_root}/PKG-INFO"
    with tarfile.open(dist / sdist_name, "w:gz") as tf:
        if metadata is not None:
            pkg_info = dist / "PKG-INFO"
            pkg_info.write_text(metadata, encoding="utf-8")
            tf.add(pkg_info, arcname=root_pkg_info)
        for filename in filenames:
            source = dist / filename
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(filename, encoding="utf-8")
            tf.add(source, arcname=f"{sdist_root}/{filename}")
        if pyproject is not None:
            source = dist / pyproject
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(pyproject, encoding="utf-8")
            tf.add(source, arcname=f"{sdist_root}/{pyproject}")
        if readme is not None:
            source = dist / readme
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(readme, encoding="utf-8")
            tf.add(source, arcname=f"{sdist_root}/{readme}")
        for filename in license_files:
            source = dist / filename
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(filename, encoding="utf-8")
            tf.add(source, arcname=f"{sdist_root}/{filename}")
        if package_init is not None:
            source = dist / package_init
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(package_init_content, encoding="utf-8")
            tf.add(source, arcname=f"{sdist_root}/{package_init}")
        if cli_module is not None:
            source = dist / cli_module
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(cli_module_content, encoding="utf-8")
            tf.add(source, arcname=f"{sdist_root}/{cli_module}")
        if typed_marker is not None:
            source = dist / typed_marker
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("", encoding="utf-8")
            tf.add(source, arcname=f"{sdist_root}/{typed_marker}")
        for filename in static_bundle:
            source = dist / filename
            source.parent.mkdir(parents=True, exist_ok=True)
            content = static_index_html if filename.endswith("/index.html") else filename
            source.write_text(content, encoding="utf-8")
            tf.add(source, arcname=f"{sdist_root}/{filename}")


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
description = "Interactive editor for Pydantic models"
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
license-files = ["LICENSE"]
authors = [{{ name = "pydantic-studio contributors" }}]
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
        ("Summary", "Interactive editor for Pydantic models"),
        ("Author", "pydantic-studio contributors"),
        ("Description-Content-Type", "text/markdown"),
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
            "Summary",
            "Author",
            "Description-Content-Type",
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


def test_verify_distribution_metadata_rejects_wrong_wheel_filename_identity(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata, wheel_name="wrong_name-0.4.0-py3-none-any.whl")
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"wheel filename.*pydantic_studio-0\.4\.0"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_wrong_sdist_filename_identity(
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
        sdist_name="wrong_name-0.4.0.tar.gz",
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"sdist filename.*pydantic_studio-0\.4\.0"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_wrong_sdist_archive_root_identity(
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
        sdist_root="wrong_name-0.4.0",
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"sdist archive root.*pydantic_studio-0\.4\.0"):
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


def test_verify_distribution_metadata_rejects_wrong_wheel_dist_info_metadata_dir(
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
        metadata_name="wrong_name-0.4.0.dist-info/METADATA",
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"pydantic_studio-0\.4\.0\.dist-info"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_wrong_wheel_dist_info_entry_points_dir(
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
        entry_points_name="wrong_name-0.4.0.dist-info/entry_points.txt",
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"pydantic_studio-0\.4\.0\.dist-info"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


@pytest.mark.parametrize(
    ("missing_filename", "kwargs"),
    [
        ("WHEEL", {"wheel_metadata": None}),
        ("RECORD", {"record": None}),
    ],
)
def test_verify_distribution_metadata_rejects_missing_wheel_structure_files(
    tmp_path: Path,
    missing_filename: str,
    kwargs: dict[str, str | None],
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata, **kwargs)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=missing_filename):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_wrong_wheel_compatibility_tag(
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
        wheel_metadata=(
            "Wheel-Version: 1.0\n"
            "Root-Is-Purelib: true\n"
            "Tag: cp313-cp313-macosx_14_0_arm64\n"
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"Tag"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_wrong_wheel_purelib_flag(
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
        wheel_metadata=(
            "Wheel-Version: 1.0\n"
            "Root-Is-Purelib: false\n"
            "Tag: py3-none-any\n"
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"Root-Is-Purelib"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_record_entry(
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
        record=(
            "pydantic_studio/__init__.py,,\n"
            "pydantic_studio-0.4.0.dist-info/METADATA,,\n"
            "pydantic_studio-0.4.0.dist-info/WHEEL,,\n"
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"RECORD"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_typed_marker(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata, typed_marker=None)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"py\.typed"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_package_init(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata, package_init=None)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"__init__\.py"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_wheel_package_version_drift(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata, package_init_content='__version__ = "9.9.9"\n')
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"__version__.*9\.9\.9"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_package_init_record_entry(
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
        record=(
            "pydantic_studio/py.typed,,\n"
            "pydantic_studio/renderers/html/static/dist/index.html,,\n"
            "pydantic_studio/renderers/html/static/dist/assets/index-test.css,,\n"
            "pydantic_studio/renderers/html/static/dist/assets/index-test.js,,\n"
            "pydantic_studio-0.4.0.dist-info/METADATA,,\n"
            "pydantic_studio-0.4.0.dist-info/WHEEL,,\n"
            "pydantic_studio-0.4.0.dist-info/entry_points.txt,,\n"
            "pydantic_studio-0.4.0.dist-info/licenses/LICENSE,,\n"
            "pydantic_studio-0.4.0.dist-info/RECORD,,\n"
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"__init__\.py"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_console_script_module(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata, cli_module=None)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"cli\.py"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_console_script_module_record_entry(
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
        record=(
            "pydantic_studio/__init__.py,,\n"
            "pydantic_studio/py.typed,,\n"
            "pydantic_studio/renderers/html/static/dist/index.html,,\n"
            "pydantic_studio/renderers/html/static/dist/assets/index-test.css,,\n"
            "pydantic_studio/renderers/html/static/dist/assets/index-test.js,,\n"
            "pydantic_studio-0.4.0.dist-info/METADATA,,\n"
            "pydantic_studio-0.4.0.dist-info/WHEEL,,\n"
            "pydantic_studio-0.4.0.dist-info/entry_points.txt,,\n"
            "pydantic_studio-0.4.0.dist-info/licenses/LICENSE,,\n"
            "pydantic_studio-0.4.0.dist-info/RECORD,,\n"
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"cli\.py"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_wheel_console_script_missing_target_object(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata, cli_module_content="other = object()\n")
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"app"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_extra_wheel_console_script_entry_point(
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
        entry_points=(
            "[console_scripts]\n"
            "pydantic-studio = pydantic_studio.cli:app\n"
            "pydantic-studio-debug = pydantic_studio.cli:app\n"
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"unexpected console script entry points"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_typed_marker_record_entry(
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
        record=(
            "pydantic_studio/__init__.py,,\n"
            "pydantic_studio-0.4.0.dist-info/METADATA,,\n"
            "pydantic_studio-0.4.0.dist-info/WHEEL,,\n"
            "pydantic_studio-0.4.0.dist-info/entry_points.txt,,\n"
            "pydantic_studio-0.4.0.dist-info/licenses/LICENSE,,\n"
            "pydantic_studio-0.4.0.dist-info/RECORD,,\n"
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"py\.typed"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_static_bundle_index(
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
        static_bundle=(
            "pydantic_studio/renderers/html/static/dist/assets/index-test.css",
            "pydantic_studio/renderers/html/static/dist/assets/index-test.js",
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"static.*index\.html"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_static_bundle_script(
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
        static_bundle=(
            "pydantic_studio/renderers/html/static/dist/index.html",
            "pydantic_studio/renderers/html/static/dist/assets/index-test.css",
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"static.*\.js"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_static_bundle_record_entry(
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
        record=(
            "pydantic_studio/__init__.py,,\n"
            "pydantic_studio/py.typed,,\n"
            "pydantic_studio-0.4.0.dist-info/METADATA,,\n"
            "pydantic_studio-0.4.0.dist-info/WHEEL,,\n"
            "pydantic_studio-0.4.0.dist-info/entry_points.txt,,\n"
            "pydantic_studio-0.4.0.dist-info/licenses/LICENSE,,\n"
            "pydantic_studio-0.4.0.dist-info/RECORD,,\n"
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"RECORD.*static"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_wheel_static_bundle_missing_referenced_script(
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
        static_index_html=(
            '<script type="module" src="/static/dist/assets/missing.js"></script>\n'
            '<link rel="stylesheet" href="/static/dist/assets/index-test.css">\n'
        ),
    )
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"missing\.js"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_wheel_license_file(
    tmp_path: Path,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    metadata = _metadata()
    _write_wheel(dist, metadata, license_files=())
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"LICENSE"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_sdist_license_file(
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
        license_files=(),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"LICENSE"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_sdist_readme_file(
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
        readme=None,
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"README\.md"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_sdist_pyproject_file(
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
        pyproject=None,
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"pyproject\.toml"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_sdist_typed_marker(
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
        typed_marker=None,
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"py\.typed"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_sdist_package_init(
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
        package_init=None,
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"__init__\.py"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_sdist_package_version_drift(
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
        package_init_content='__version__ = "9.9.9"\n',
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"__version__.*9\.9\.9"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_sdist_console_script_module(
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
        cli_module=None,
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"cli\.py"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_sdist_console_script_missing_target_object(
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
        cli_module_content="other = object()\n",
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"app"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_missing_sdist_static_bundle_stylesheet(
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
        static_bundle=(
            "src/pydantic_studio/renderers/html/static/dist/index.html",
            "src/pydantic_studio/renderers/html/static/dist/assets/index-test.js",
        ),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"static.*\.css"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


def test_verify_distribution_metadata_rejects_sdist_static_bundle_missing_referenced_stylesheet(
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
        static_index_html=(
            '<script type="module" src="/static/dist/assets/index-test.js"></script>\n'
            '<link rel="stylesheet" href="/static/dist/assets/missing.css">\n'
        ),
        metadata=metadata,
    )

    with pytest.raises(RuntimeError, match=r"missing\.css"):
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


@pytest.mark.parametrize("drifted_file", ["wheel", "sdist"])
def test_verify_distribution_metadata_rejects_summary_metadata_drift(
    tmp_path: Path,
    drifted_file: str,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    expected_metadata = _metadata()
    drifted_metadata = expected_metadata.replace(
        "Summary: Interactive editor for Pydantic models",
        "Summary: Wrong summary",
    )
    _write_wheel(dist, drifted_metadata if drifted_file == "wheel" else expected_metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=drifted_metadata if drifted_file == "sdist" else expected_metadata,
    )

    with pytest.raises(RuntimeError, match=r"Summary"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


@pytest.mark.parametrize("drifted_file", ["wheel", "sdist"])
def test_verify_distribution_metadata_rejects_author_metadata_drift(
    tmp_path: Path,
    drifted_file: str,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    expected_metadata = _metadata()
    drifted_metadata = expected_metadata.replace(
        "Author: pydantic-studio contributors",
        "Author: Wrong Author",
    )
    _write_wheel(dist, drifted_metadata if drifted_file == "wheel" else expected_metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=drifted_metadata if drifted_file == "sdist" else expected_metadata,
    )

    with pytest.raises(RuntimeError, match=r"Author"):
        verifier.verify_distribution_metadata(dist, project_root=tmp_path)


@pytest.mark.parametrize("drifted_file", ["wheel", "sdist"])
def test_verify_distribution_metadata_rejects_description_content_type_drift(
    tmp_path: Path,
    drifted_file: str,
) -> None:
    verifier = _load_verifier()
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_pyproject(tmp_path)
    expected_metadata = _metadata()
    drifted_metadata = expected_metadata.replace(
        "Description-Content-Type: text/markdown",
        "Description-Content-Type: text/plain",
    )
    _write_wheel(dist, drifted_metadata if drifted_file == "wheel" else expected_metadata)
    _write_sdist(
        dist,
        ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"),
        metadata=drifted_metadata if drifted_file == "sdist" else expected_metadata,
    )

    with pytest.raises(RuntimeError, match=r"Description-Content-Type"):
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
