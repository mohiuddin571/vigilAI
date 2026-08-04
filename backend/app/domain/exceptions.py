"""Domain-level exception hierarchy.

Raised by domain entities/value objects on invalid state, and by future
infrastructure adapters (behind their ports) to surface camera-facing
failures without leaking library-specific exception types (e.g. a SOAP
fault or a `cv2` error) past the application boundary.
"""


class DomainError(Exception):
    """Base type for every exception raised by the domain layer."""


class InvalidDomainStateError(DomainError, ValueError):
    """An entity or value object was constructed in an invalid state."""


class CameraUnreachableError(DomainError):
    """A camera could not be reached over the network."""


class CameraAuthenticationError(DomainError):
    """A camera rejected the supplied credentials."""


class CameraNotFoundError(DomainError):
    """No onboarded camera exists for the given identifier."""


class UnsupportedConfigurationError(DomainError):
    """A requested camera configuration change is not supported by the camera."""
