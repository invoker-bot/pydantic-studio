"""Verify release distribution metadata and source archive support files."""

from __future__ import annotations

import argparse
import tarfile
import tomllib
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Sequence

SUPPORT_PROJECT_URL_LABELS = ("Changelog", "Security", "Contributing")


def _single_file(dist_dir: Path, pattern: str) -> Path:
    matches = sorted(dist_dir.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {pattern} in {dist_dir}, found {matches!r}")
    return matches[0]


def _wheel_metadata(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as zf:
        metadata_names = [name for name in zf.namelist() if name.endswith("METADATA")]
        if len(metadata_names) != 1:
            raise RuntimeError(
                f"expected exactly one METADATA file in {wheel}, got {metadata_names!r}"
            )
        return zf.read(metadata_names[0]).decode("utf-8")


def _sdist_names(sdist: Path) -> list[str]:
    with tarfile.open(sdist) as tf:
        return tf.getnames()


def _sdist_metadata(sdist: Path) -> str:
    with tarfile.open(sdist) as tf:
        metadata_members = [
            member for member in tf.getmembers() if member.name.endswith("/PKG-INFO")
        ]
        if len(metadata_members) != 1:
            raise RuntimeError(
                f"expected exactly one PKG-INFO file in {sdist}, got {metadata_members!r}"
            )
        metadata_file = tf.extractfile(metadata_members[0])
        if metadata_file is None:
            raise RuntimeError(f"could not read PKG-INFO file in {sdist}")
        return metadata_file.read().decode("utf-8")


def _load_pyproject(project_root: Path) -> dict[str, object]:
    return tomllib.loads(project_root.joinpath("pyproject.toml").read_text(encoding="utf-8"))


def _table(table: dict[str, object], key: str, path: str) -> dict[str, object]:
    value = table.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"pyproject.toml missing table [{path}]")
    return value


def _project_urls(pyproject: dict[str, object]) -> dict[str, str]:
    project = _table(pyproject, "project", "project")
    urls = _table(project, "urls", "project.urls")

    missing = [label for label in SUPPORT_PROJECT_URL_LABELS if label not in urls]
    if missing:
        raise RuntimeError(f"pyproject.toml missing project URLs: {missing!r}")

    invalid = [label for label, url in urls.items() if not isinstance(url, str)]
    if invalid:
        raise RuntimeError(f"pyproject.toml project URLs must be strings: {invalid!r}")

    project_urls: dict[str, str] = {}
    for label, value in urls.items():
        if isinstance(value, str):
            project_urls[label] = value
    return project_urls


def _source_include(pyproject: dict[str, object]) -> tuple[str, ...]:
    tool = _table(pyproject, "tool", "tool")
    uv = _table(tool, "uv", "tool.uv")
    build_backend = _table(uv, "build-backend", "tool.uv.build-backend")
    source_include = build_backend.get("source-include")
    if not isinstance(source_include, list) or not all(
        isinstance(filename, str) for filename in source_include
    ):
        raise RuntimeError("pyproject.toml [tool.uv.build-backend] source-include must be strings")
    return tuple(source_include)


def _filename_from_url(label: str, url: str) -> str:
    filename = Path(urlsplit(url).path).name
    if not filename:
        raise RuntimeError(f"pyproject.toml project URL {label!r} does not name a file")
    return filename


def _expected_project_urls(pyproject: dict[str, object]) -> tuple[str, ...]:
    urls = _project_urls(pyproject)
    return tuple(f"Project-URL: {label}, {url}" for label, url in urls.items())


def _expected_sdist_files(pyproject: dict[str, object]) -> tuple[str, ...]:
    urls = _project_urls(pyproject)
    filenames = tuple(
        _filename_from_url(label, urls[label]) for label in SUPPORT_PROJECT_URL_LABELS
    )
    source_include = _source_include(pyproject)
    missing_source_include = [
        filename for filename in filenames if filename not in source_include
    ]
    if missing_source_include:
        raise RuntimeError(
            "pyproject.toml source-include missing support files: "
            f"{missing_source_include!r}"
        )
    return filenames


def verify_distribution_metadata(dist_dir: Path, *, project_root: Path | None = None) -> None:
    project_root = project_root or Path.cwd()
    pyproject = _load_pyproject(project_root)
    wheel = _single_file(dist_dir, "*.whl")
    sdist = _single_file(dist_dir, "*.tar.gz")

    metadata = _wheel_metadata(wheel)
    missing_urls = [url for url in _expected_project_urls(pyproject) if url not in metadata]
    if missing_urls:
        raise RuntimeError(f"{wheel} missing project URL metadata: {missing_urls!r}")

    sdist_metadata = _sdist_metadata(sdist)
    missing_sdist_urls = [
        url for url in _expected_project_urls(pyproject) if url not in sdist_metadata
    ]
    if missing_sdist_urls:
        raise RuntimeError(f"{sdist} missing project URL metadata: {missing_sdist_urls!r}")

    names = _sdist_names(sdist)
    missing_files = [
        filename
        for filename in _expected_sdist_files(pyproject)
        if not any(name.endswith(f"/{filename}") for name in names)
    ]
    if missing_files:
        raise RuntimeError(f"{sdist} missing source files: {missing_files!r}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dist_dir",
        nargs="?",
        default="dist",
        type=Path,
        help="Directory containing one wheel and one source distribution.",
    )
    parser.add_argument(
        "--project-root",
        default=Path.cwd(),
        type=Path,
        help="Project root containing pyproject.toml.",
    )
    args = parser.parse_args(argv)
    verify_distribution_metadata(args.dist_dir, project_root=args.project_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
