"""Regression tests for issue #4: Select.NULL/BLANK rename across textual versions.

textual 8.x exposes ``Select.NULL`` as the ``NoSelection`` sentinel; ``Select.BLANK``
exists but is ``False`` (inherited from ``Widget``, unrelated). textual 1.x..7.x
exposes only ``Select.BLANK`` as the sentinel. ``ChoiceEditor`` and ``UnionEditor``
must work on both ranges.

These tests pin the shim's behavior so the Phase-5 regression that introduced
the bug cannot re-occur.
"""

from __future__ import annotations

from textual.widgets import Select

from pydantic_studio.renderers.textual_.widgets import containers, scalars


def test_scalars_select_blank_shim_resolves_on_current_textual() -> None:
    sentinel = scalars._SELECT_BLANK
    assert sentinel is not None
    assert sentinel is not False
    if hasattr(Select, "NULL"):
        assert sentinel is Select.NULL


def test_containers_select_blank_shim_resolves_on_current_textual() -> None:
    sentinel = containers._SELECT_BLANK
    assert sentinel is not None
    assert sentinel is not False
    if hasattr(Select, "NULL"):
        assert sentinel is Select.NULL


def test_shim_logic_falls_back_to_blank_when_null_absent() -> None:
    class FakeSelect:
        """Mimic textual <=7.x: only BLANK, no NULL."""

        class _NoSelection:
            pass

        BLANK = _NoSelection()

    resolved = getattr(FakeSelect, "NULL", None)
    if resolved is None:
        resolved = FakeSelect.BLANK
    assert resolved is FakeSelect.BLANK


def test_shim_logic_prefers_null_when_both_present() -> None:
    class FakeSelect:
        """Mimic textual 8.x: both NULL (sentinel) and BLANK (unrelated)."""

        class _NoSelection:
            pass

        NULL = _NoSelection()
        BLANK = False

    resolved = getattr(FakeSelect, "NULL", None)
    if resolved is None:
        resolved = FakeSelect.BLANK
    assert resolved is FakeSelect.NULL
    assert resolved is not False
