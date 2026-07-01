from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, Field

from pydantic_studio import build_form_tree, load_yaml
from pydantic_studio.outcome import EditOutcome
from pydantic_studio.session import EditSession, SubmitResult

if TYPE_CHECKING:
    from pathlib import Path


class _ValidSchema(BaseModel):
    name: str = "alpha"
    debug: bool = False


class _RequiredSchema(BaseModel):
    api_key: str = Field(...)
    timeout: int = 30


def test_submit_result_shape() -> None:
    result = SubmitResult(ok=False, errors=("missing",), paths=("api_key",))
    assert result.ok is False
    assert result.outcome is None
    assert result.errors == ("missing",)
    assert result.paths == ("api_key",)


def test_submit_without_save_path_sets_submitted_outcome() -> None:
    tree = build_form_tree(_ValidSchema)
    session = EditSession(tree=tree)
    result = session.submit()
    assert result == SubmitResult(ok=True, outcome=EditOutcome("submitted"))
    assert session.submitted is True
    assert session.cancelled is False
    assert session.done is True


def test_submit_with_save_path_writes_yaml(tmp_path: Path) -> None:
    out = tmp_path / "config.yaml"
    tree = build_form_tree(_ValidSchema)
    session = EditSession(tree=tree, save_path=out)
    result = session.submit()
    assert result.ok is True
    assert out.exists()
    assert load_yaml(out, _ValidSchema).to_instance().name == "alpha"


def test_submit_success_resets_dirty_baseline() -> None:
    tree = build_form_tree(_ValidSchema)
    session = EditSession(tree=tree)
    assert tree.set_value("name", "changed").ok is True
    assert session.dirty is True

    result = session.submit()

    assert result == SubmitResult(ok=True, outcome=EditOutcome("submitted"))
    assert session.dirty is False


def test_submit_after_success_is_idempotent_and_does_not_rewrite(
    tmp_path: Path,
) -> None:
    out = tmp_path / "config.yaml"
    tree = build_form_tree(_ValidSchema)
    session = EditSession(tree=tree, save_path=out)
    first = session.submit()
    assert first == SubmitResult(ok=True, outcome=EditOutcome("submitted"))

    blocked_path = tmp_path / "directory-target"
    blocked_path.mkdir()
    session.save_path = blocked_path

    second = session.submit()

    assert second == SubmitResult(ok=True, outcome=EditOutcome("submitted"))
    assert session.submitted is True
    assert session.cancelled is False


def test_submit_validation_failure_leaves_outcome_unset(tmp_path: Path) -> None:
    out = tmp_path / "config.yaml"
    tree = build_form_tree(_RequiredSchema)
    session = EditSession(tree=tree, save_path=out)
    result = session.submit()
    assert result.ok is False
    assert result.outcome is None
    assert result.errors
    assert result.paths == ("api_key",)
    assert session.outcome is None
    assert session.done is False
    assert not out.exists()


def test_submit_write_failure_leaves_outcome_unset(tmp_path: Path) -> None:
    out = tmp_path / "config.yaml"
    out.mkdir()
    tree = build_form_tree(_ValidSchema)
    session = EditSession(tree=tree, save_path=out)

    result = session.submit()

    assert result.ok is False
    assert result.outcome is None
    assert result.paths == ()
    assert result.errors
    assert "could not save" in result.errors[0]
    assert session.outcome is None
    assert session.done is False


def test_cancel_sets_cancelled_and_is_idempotent() -> None:
    session = EditSession(tree=build_form_tree(_ValidSchema))
    first = session.cancel()
    second = session.cancel()
    assert first == EditOutcome("cancelled")
    assert second == EditOutcome("cancelled")
    assert session.cancelled is True
    assert session.submitted is False
    assert session.done is True


def test_submit_after_cancel_does_not_overwrite_cancelled_outcome(tmp_path: Path) -> None:
    out = tmp_path / "config.yaml"
    session = EditSession(tree=build_form_tree(_ValidSchema), save_path=out)
    session.cancel()

    result = session.submit()

    assert result == SubmitResult(
        ok=False,
        outcome=EditOutcome("cancelled"),
        errors=("session already cancelled",),
    )
    assert session.cancelled is True
    assert session.submitted is False
    assert not out.exists()


def test_dirty_tracks_tree_changes() -> None:
    tree = build_form_tree(_ValidSchema)
    session = EditSession(tree=tree)
    assert session.dirty is False
    tree.set_value("name", "changed")
    assert session.dirty is True


@pytest.mark.parametrize("readonly_path", ["name.", "tags[+0]", "tags.0foo"])
def test_session_rejects_invalid_readonly_path(readonly_path: str) -> None:
    tree = build_form_tree(_ValidSchema)
    with pytest.raises(ValueError, match="invalid read-only path"):
        EditSession(tree=tree, readonly_paths={readonly_path})


def test_session_rejects_readonly_paths_string_container() -> None:
    tree = build_form_tree(_ValidSchema)
    with pytest.raises(ValueError, match="read-only paths must be an iterable"):
        EditSession(tree=tree, readonly_paths="name")  # type: ignore[arg-type]
