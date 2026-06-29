"""Validation result type returned by tree mutations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a node-local or tree-wide validation pass.

    ``ok`` is True iff ``errors`` is empty. The dataclass is frozen so
    callers can store results without worrying about mutation. ``errors``
    is a tuple to prevent in-place mutation through the frozen wrapper.
    """

    ok: bool  # pyright: ignore[reportRedeclaration]
    errors: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def success(cls) -> ValidationResult:
        return cls(ok=True, errors=())

    # Convenience alias. Instances expose ``result.ok`` as a boolean; the
    # class exposes ``ValidationResult.ok()`` as a factory. Runtime lookup
    # handles that because instance attributes shadow the classmethod.
    @classmethod
    def ok(  # noqa: A003, RUF100 - intentional bool/factory alias
        cls,
    ) -> ValidationResult:  # pyright: ignore[reportRedeclaration]
        return cls.success()

    @classmethod
    def fail(cls, errors: list[str]) -> ValidationResult:
        return cls(ok=False, errors=tuple(errors))

    def __bool__(self) -> bool:
        return self.ok  # pyright: ignore[reportReturnType]
