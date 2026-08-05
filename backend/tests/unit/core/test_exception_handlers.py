import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.exception_handlers import register_exception_handlers
from app.domain.exceptions import (
    AnalyticsZoneNotFoundError,
    CameraAuthenticationError,
    CameraNotFoundError,
    CameraUnreachableError,
    InvalidDomainStateError,
    UnsupportedConfigurationError,
)


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise/{exc_name}")
    def raise_error(exc_name: str) -> None:
        exceptions = {
            "auth": CameraAuthenticationError,
            "not_found": CameraNotFoundError,
            "unreachable": CameraUnreachableError,
            "unsupported": UnsupportedConfigurationError,
            "invalid_state": InvalidDomainStateError,
            "zone_not_found": AnalyticsZoneNotFoundError,
        }
        raise exceptions[exc_name]("boom")

    return app


@pytest.mark.parametrize(
    ("exc_name", "expected_status"),
    [
        ("auth", 401),
        ("not_found", 404),
        ("unreachable", 400),
        ("unsupported", 422),
        ("invalid_state", 422),
        ("zone_not_found", 404),
    ],
)
async def test_domain_exceptions_map_to_typed_4xx(exc_name: str, expected_status: int) -> None:
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/raise/{exc_name}")

    assert response.status_code == expected_status
    assert response.json() == {"detail": "boom"}
