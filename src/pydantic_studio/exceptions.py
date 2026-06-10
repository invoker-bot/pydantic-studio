"""Exception hierarchy for pydantic-studio."""

from __future__ import annotations


class PydanticStudioError(Exception):
    """Base class for all pydantic-studio errors."""


class NoBuilderError(PydanticStudioError):
    """Raised when no NodeBuilder matches a given Python type."""

    def __init__(self, type_: type) -> None:
        self.type_ = type_
        super().__init__(f"No NodeBuilder registered for type: {type_!r}")


class CancelledByUser(PydanticStudioError):
    """Raised when the user cancels the editing session (Ctrl+C, browser close, etc.)."""


class ValidationFailedError(PydanticStudioError):
    """Raised when materializing the form tree into an instance fails validation.

    ``errors`` are human-readable ``"dotted.path: message"`` lines.
    ``paths`` carries just the dotted locations, parallel to ``errors``
    where available — renderers use them to jump the cursor to the first
    offending field instead of leaving a detached wall of text.
    """

    def __init__(self, errors: list[str], paths: list[str] | None = None) -> None:
        self.errors = list(errors)
        self.paths = list(paths) if paths is not None else []
        if errors:
            msg = "Validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        else:
            msg = "Validation failed"
        super().__init__(msg)
