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


def _write_sdist(dist: Path, filenames: tuple[str, ...]) -> None:
    with tarfile.open(dist / "pydantic_studio-0.4.0.tar.gz", "w:gz") as tf:
        for filename in filenames:
            source = dist / filename
            source.write_text(filename, encoding="utf-8")
            tf.add(source, arcname=f"pydantic_studio-0.4.0/{filename}")


def test_verify_distribution_metadata_accepts_expected_release_files(tmp_path: Path) -> None:
    verifier = _load_verifier()
    metadata = "\n".join(
        [
            "Project-URL: Changelog, https://github.com/invoker-bot/pydantic-studio/blob/main/CHANGELOG.md",
            "Project-URL: Security, https://github.com/invoker-bot/pydantic-studio/blob/main/SECURITY.md",
            "Project-URL: Contributing, https://github.com/invoker-bot/pydantic-studio/blob/main/CONTRIBUTING.md",
        ]
    )
    _write_wheel(tmp_path, metadata)
    _write_sdist(tmp_path, ("CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md"))

    verifier.verify_distribution_metadata(tmp_path)


def test_verify_distribution_metadata_rejects_missing_sdist_file(tmp_path: Path) -> None:
    verifier = _load_verifier()
    metadata = "\n".join(
        [
            "Project-URL: Changelog, https://github.com/invoker-bot/pydantic-studio/blob/main/CHANGELOG.md",
            "Project-URL: Security, https://github.com/invoker-bot/pydantic-studio/blob/main/SECURITY.md",
            "Project-URL: Contributing, https://github.com/invoker-bot/pydantic-studio/blob/main/CONTRIBUTING.md",
        ]
    )
    _write_wheel(tmp_path, metadata)
    _write_sdist(tmp_path, ("CHANGELOG.md", "SECURITY.md"))

    with pytest.raises(RuntimeError, match=r"CONTRIBUTING\.md"):
        verifier.verify_distribution_metadata(tmp_path)
