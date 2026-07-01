"""Smoke test: mkdocs builds without errors or broken links."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_mkdocs_strict_build(tmp_path: Path) -> None:
    """mkdocs build --strict succeeds (catches broken links + missing pages)."""
    site_dir = tmp_path / "site"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
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
        timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"mkdocs build --strict failed:\nSTDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )
    assert (site_dir / "index.html").exists()
