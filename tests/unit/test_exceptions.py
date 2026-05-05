from __future__ import annotations

import pytest

from pydantic_studio.exceptions import (
    CancelledByUser,
    NoBuilderError,
    PydanticStudioError,
    ValidationFailedError,
)


def test_pydantic_studio_error_is_base():
    """All custom exceptions inherit from PydanticStudioError."""
    assert issubclass(NoBuilderError, PydanticStudioError)
    assert issubclass(CancelledByUser, PydanticStudioError)
    assert issubclass(ValidationFailedError, PydanticStudioError)


def test_no_builder_error_carries_type():
    err = NoBuilderError(int)
    assert err.type_ is int
    assert "int" in str(err)


def test_cancelled_by_user_is_default_constructible():
    err = CancelledByUser()
    assert isinstance(err, PydanticStudioError)


def test_validation_failed_error_carries_errors():
    err = ValidationFailedError(["name: required", "age: must be > 0"])
    assert err.errors == ["name: required", "age: must be > 0"]
    assert "name: required" in str(err)


def test_pydantic_studio_error_can_be_caught_generically():
    """Anyone who catches PydanticStudioError catches all our errors."""
    with pytest.raises(PydanticStudioError):
        raise NoBuilderError(int)
    with pytest.raises(PydanticStudioError):
        raise CancelledByUser()
    with pytest.raises(PydanticStudioError):
        raise ValidationFailedError([])
