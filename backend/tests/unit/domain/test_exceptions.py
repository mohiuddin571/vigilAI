import pytest

from app.domain.exceptions import (
    CameraAuthenticationError,
    CameraNotFoundError,
    CameraUnreachableError,
    DomainError,
    InvalidDomainStateError,
    UnsupportedConfigurationError,
)


def test_domain_error_is_the_common_base() -> None:
    assert issubclass(CameraUnreachableError, DomainError)
    assert issubclass(CameraAuthenticationError, DomainError)
    assert issubclass(CameraNotFoundError, DomainError)
    assert issubclass(UnsupportedConfigurationError, DomainError)
    assert issubclass(InvalidDomainStateError, DomainError)


def test_invalid_domain_state_error_is_also_a_value_error() -> None:
    assert issubclass(InvalidDomainStateError, ValueError)


@pytest.mark.parametrize(
    "exc_type",
    [
        DomainError,
        CameraUnreachableError,
        CameraAuthenticationError,
        CameraNotFoundError,
        UnsupportedConfigurationError,
        InvalidDomainStateError,
    ],
)
def test_raises_and_carries_message(exc_type: type[DomainError]) -> None:
    with pytest.raises(exc_type, match="boom"):
        raise exc_type("boom")
