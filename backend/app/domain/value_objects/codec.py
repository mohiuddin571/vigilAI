from enum import StrEnum


class Codec(StrEnum):
    """Video compression formats reportable/configurable via ONVIF's encoder config."""

    H264 = "H264"
    H265 = "H265"
    MJPEG = "MJPEG"
    MPEG4 = "MPEG4"
