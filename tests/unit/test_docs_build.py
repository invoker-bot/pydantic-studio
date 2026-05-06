"""Smoke test: mkdocs builds without errors or broken links."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_mkdocs_strict_build(tmp_path: Path) -> None:
    """mkdocs build --strict succeeds (catches broken links + missing pages)."""
    if shutil.which("mkdocs") is None:
        pytest.skip("mkdocs not on PATH (dev dep not synced)")

    site_dir = tmp_path / "site"
    result = subprocess.run(
        [
            "mkdocs",
            "build",
            "--strict",
            "-f",
            str(REPO_ROOT / "mkdocs.yml"),
            "-d",
            str(site_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        pytest.fail(
            f"mkdocs build --strict failed:\nSTDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )
    assert (site_dir / "index.html").exists()
