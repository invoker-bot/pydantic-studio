"""Shared editing-session lifecycle for renderers."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from pydantic_studio.exceptions import ValidationFailedError
from pydantic_studio.outcome import EditOutcome
from pydantic_studio.tree.paths import Path as TreePath

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic_studio.tree.nodes import FormTree


@dataclass(frozen=True)
class SubmitResult:
    """Result of an explicit submit attempt."""

    ok: bool
    outcome: EditOutcome | None = None
    errors: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()


class EditSession:
    """Renderer-neutral edit session state.

    Renderers own pixels and input handling. This object owns the shared tree,
    readonly paths, dirty tracking, and submit/cancel outcome.
    """

    def __init__(
        self,
        tree: FormTree,
        save_path: str | Path | None = None,
        readonly_paths: Iterable[str] = (),
    ) -> None:
        self.tree = tree
        self.save_path = Path(save_path) if save_path is not None else None
        self.readonly_paths = _validate_readonly_paths(readonly_paths)
        self.outcome: EditOutcome | None = None
        self._initial_state = copy.deepcopy(tree.to_python())

    @property
    def dirty(self) -> bool:
        return self.tree.to_python() != self._initial_state

    @property
    def submitted(self) -> bool:
        return self.outcome == EditOutcome("submitted")

    @property
    def cancelled(self) -> bool:
        return self.outcome == EditOutcome("cancelled")

    @property
    def done(self) -> bool:
        return self.outcome is not None

    def submit(self) -> SubmitResult:
        """Validate and optionally persist the current tree."""
        from pydantic_studio import save_yaml

        try:
            if self.save_path is not None:
                try:
                    save_yaml(self.tree, self.save_path)
                except (OSError, ValueError) as exc:
                    return SubmitResult(
                        ok=False,
                        errors=(f"could not save to {self.save_path}: {exc}",),
                    )
            else:
                self.tree.to_instance()
        except ValidationFailedError as exc:
            return SubmitResult(
                ok=False,
                errors=tuple(exc.errors),
                paths=tuple(exc.paths),
            )
        except ValidationError as exc:
            errors = tuple(str(err) for err in exc.errors())
            paths = tuple(
                ".".join(str(part) for part in err.get("loc", ()))
                for err in exc.errors()
            )
            return SubmitResult(ok=False, errors=errors, paths=paths)

        self.outcome = EditOutcome("submitted")
        return SubmitResult(ok=True, outcome=self.outcome)

    def cancel(self) -> EditOutcome:
        if self.outcome is None:
            self.outcome = EditOutcome("cancelled")
        return self.outcome


def _validate_readonly_paths(readonly_paths: Iterable[str]) -> frozenset[str]:
    if isinstance(readonly_paths, str):
        msg = "read-only paths must be an iterable of path strings, not a string"
        raise ValueError(msg)
    validated: set[str] = set()
    for readonly_path in readonly_paths:
        if not isinstance(readonly_path, str):
            msg = f"read-only path must be a string, got {type(readonly_path).__name__}"
            raise ValueError(msg)
        try:
            TreePath.parse(readonly_path)
        except ValueError as exc:
            msg = f"invalid read-only path {readonly_path!r}: {exc}"
            raise ValueError(msg) from exc
        validated.add(readonly_path)
    return frozenset(validated)
