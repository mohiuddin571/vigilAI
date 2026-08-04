import pytest

from app.domain.entities.camera import Camera
from app.domain.exceptions import InvalidDomainStateError


def test_valid_camera() -> None:
    camera = Camera(name="Front Door", ip_address="192.168.1.10", username="admin")
    assert camera.name == "Front Door"
    assert camera.is_online is False
    assert camera.stream_profiles == []


def test_accepts_ipv6_address() -> None:
    camera = Camera(name="Front Door", ip_address="::1", username="admin")
    assert camera.ip_address == "::1"


def test_rejects_empty_name() -> None:
    with pytest.raises(InvalidDomainStateError):
        Camera(name="   ", ip_address="192.168.1.10", username="admin")


def test_rejects_invalid_ip_address() -> None:
    with pytest.raises(InvalidDomainStateError):
        Camera(name="Front Door", ip_address="not-an-ip", username="admin")


def test_rejects_empty_username() -> None:
    with pytest.raises(InvalidDomainStateError):
        Camera(name="Front Door", ip_address="192.168.1.10", username=" ")
