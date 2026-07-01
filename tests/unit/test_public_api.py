from __future__ import annotations

from pathlib import Path

import pydantic_studio as ps

ROOT = Path(__file__).resolve().parents[2]


def test_version_string_present():
    assert isinstance(ps.__version__, str)
    assert ps.__version__.count(".") >= 1


def test_top_level_imports():
    """Most-used names are re-exported at top level."""
    assert hasattr(ps, "build_form_tree")
    assert hasattr(ps, "FormTree")
    assert hasattr(ps, "GroupNode")
    assert hasattr(ps, "register_builder")
    assert hasattr(ps, "PydanticStudioError")
    assert hasattr(ps, "NoBuilderError")
    assert hasattr(ps, "CancelledByUser")
    assert hasattr(ps, "ValidationFailedError")


def test_top_level_io_format_helpers():
    assert ps.format_for_path("config.yaml") == "yaml"
    assert ps.supported_extensions() == (".json", ".toml", ".yaml", ".yml")


def test_embeddable_session_exports():
    assert hasattr(ps, "EditSession")
    assert hasattr(ps, "SubmitResult")


def test_web_embedding_exports():
    assert hasattr(ps, "mount_html_app")


def test_tui_embedding_exports():
    assert hasattr(ps, "StudioScreen")


def test_register_builder_is_callable_and_affects_default_registry():
    from pydantic_studio.tree.builder import default_registry

    class _Dummy:
        def matches(self, type_):
            return False

        def build(self, type_, field_info, existing):
            raise NotImplementedError

    before = len(default_registry())
    ps.register_builder(_Dummy())
    assert len(default_registry()) == before + 1


def test_source_docs_do_not_reference_retired_phase_markers():
    retired_markers = ("v0.0.3", "Plan 4", "only the ``show`` subcommand")

    offenders = {
        str(path.relative_to(ROOT)): marker
        for path in ROOT.joinpath("src", "pydantic_studio").rglob("*.py")
        for marker in retired_markers
        if marker in path.read_text(encoding="utf-8")
    }

    assert offenders == {}
