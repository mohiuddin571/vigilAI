from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    AnalyticsZoneNotFoundError,
    CameraAuthenticationError,
    CameraNotFoundError,
    CameraUnreachableError,
    DemoVideoNotFoundError,
    DomainError,
    InvalidDomainStateError,
    RecordingInProgressError,
    RecordingNotFoundError,
    RecordingNotInProgressError,
    UnsupportedConfigurationError,
)

logger = structlog.get_logger(__name__)

# Domain exception -> HTTP status. Every entry is a clear, typed 4xx — never a
# raw SOAP fault or stack trace (docs/ARCHITECTURE.md §7). Starlette's
# exception dispatch walks the *raised* exception's own MRO looking for a
# registered handler, so e.g. a `CameraAuthenticationError` always matches its
# own entry before falling back to the generic `DomainError` one below,
# regardless of this dict's iteration order.
_STATUS_BY_EXCEPTION: dict[type[DomainError], int] = {
    CameraAuthenticationError: status.HTTP_401_UNAUTHORIZED,
    CameraNotFoundError: status.HTTP_404_NOT_FOUND,
    CameraUnreachableError: status.HTTP_400_BAD_REQUEST,
    UnsupportedConfigurationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidDomainStateError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RecordingNotInProgressError: status.HTTP_409_CONFLICT,
    RecordingInProgressError: status.HTTP_409_CONFLICT,
    RecordingNotFoundError: status.HTTP_404_NOT_FOUND,
    AnalyticsZoneNotFoundError: status.HTTP_404_NOT_FOUND,
    DemoVideoNotFoundError: status.HTTP_404_NOT_FOUND,
    DomainError: status.HTTP_400_BAD_REQUEST,
}


def register_exception_handlers(app: FastAPI) -> None:
    for exc_type, http_status in _STATUS_BY_EXCEPTION.items():
        app.add_exception_handler(exc_type, _make_handler(http_status))


def _make_handler(http_status: int) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        logger.warning(
            "request.domain_error",
            path=request.url.path,
            exception_type=type(exc).__name__,
            detail=str(exc),
        )
        return JSONResponse(status_code=http_status, content={"detail": str(exc)})

    return handler
