"""Smoke test for theme.tcss: file must exist and declare the
variables the M1 widgets depend on. Renderable styling is verified
indirectly by the widget tests that mount under a theme-loading
ConfigScreen.
"""

from __future__ import annotations

from pathlib import Path


def test_theme_tcss_file_exists() -> None:
    here = Path(__file__).parent.parent.parent / "src" / "pydantic_studio"
    theme = here / "renderers" / "textual_" / "theme.tcss"
    assert theme.exists(), f"missing theme.tcss at {theme}"
    body = theme.read_text(encoding="utf-8")
    for var in ("$surface", "$text", "$text-muted", "$accent", "$error"):
        assert var in body, f"theme.tcss missing variable {var}"
