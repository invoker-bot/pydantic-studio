"""Verify release distribution metadata and source archive support files."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

EXPECTED_PROJECT_URLS = (
    "Project-URL: Changelog, https://github.com/invoker-bot/pydantic-studio/blob/main/CHANGELOG.md",
    "Project-URL: Security, https://github.com/invoker-bot/pydantic-studio/blob/main/SECURITY.md",
    "Project-URL: Contributing, https://github.com/invoker-bot/pydantic-studio/blob/main/CONTRIBUTING.md",
)

EXPECTED_SDIST_FILES = ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md")


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


def verify_distribution_metadata(dist_dir: Path) -> None:
    wheel = _single_file(dist_dir, "*.whl")
    sdist = _single_file(dist_dir, "*.tar.gz")

    metadata = _wheel_metadata(wheel)
    missing_urls = [url for url in EXPECTED_PROJECT_URLS if url not in metadata]
    if missing_urls:
        raise RuntimeError(f"{wheel} missing project URL metadata: {missing_urls!r}")

    names = _sdist_names(sdist)
    missing_files = [
        filename
        for filename in EXPECTED_SDIST_FILES
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
    args = parser.parse_args(argv)
    verify_distribution_metadata(args.dist_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
