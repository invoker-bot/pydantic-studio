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
    """Raised when materializing the form tree into an instance fails validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("Validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
