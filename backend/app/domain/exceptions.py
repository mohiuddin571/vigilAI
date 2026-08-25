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


class FrameSourceUnavailableError(DomainError):
    """An `IFrameSource` could not be opened or stopped producing frames.

    Deliberately not `CameraUnreachableError`: a frame source can be a local
    MP4 file with no camera involved at all (M2's `Mp4FileFrameSource`), so a
    camera-specific exception name would be misleading here.
    """


class RecordingNotInProgressError(DomainError):
    """A stop/observe operation was requested for a camera with no active recording session."""


class RecordingNotFoundError(DomainError):
    """No recording exists for the given identifier, or its segment file is missing from disk."""


class RecordingInProgressError(DomainError):
    """A destructive/mutating operation was requested on a recording that's still being written
    (`ended_at is None`) — e.g. deleting it while its segment file is actively being appended to
    by a running Recording Worker would corrupt or race the in-progress write."""


class AnalyticsZoneNotFoundError(DomainError):
    """No `AnalyticsZone` exists for the given identifier."""


class DemoVideoNotFoundError(DomainError):
    """No demo video exists for the given id in the configured demo videos directory."""


class RtmpServerUnavailableError(DomainError):
    """The RTMP demo server (MediaMTX) could not be started, or refused a publish/read
    connection (e.g. not running, or an auth check failed)."""


class RtmpPublisherError(DomainError):
    """The RTMP demo publisher (ffmpeg) could not be started, or exited unexpectedly."""
