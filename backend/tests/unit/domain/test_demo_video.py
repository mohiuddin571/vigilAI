import pytest

from app.domain.entities.demo_video import DemoVideo
from app.domain.exceptions import InvalidDomainStateError


def test_valid_demo_video() -> None:
    video = DemoVideo(id="parking-lot-1", filename="parking-lot-1.mp4")
    assert video.id == "parking-lot-1"
    assert video.filename == "parking-lot-1.mp4"


def test_empty_id_is_rejected() -> None:
    with pytest.raises(InvalidDomainStateError):
        DemoVideo(id="", filename="clip.mp4")


def test_empty_filename_is_rejected() -> None:
    with pytest.raises(InvalidDomainStateError):
        DemoVideo(id="clip", filename="")
