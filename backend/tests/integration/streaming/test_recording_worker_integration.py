"""T-060: `FfmpegRecordingWorker` against a real `ffmpeg` subprocess.

Neither a physical camera nor a local RTSP test server is available in this
environment, and (per docs/TECHNICAL_DECISIONS.md TD-22, mirroring TD-21's
prior finding for M5) `ffmpeg`/`ffprobe` themselves are not installed here
either — skip-guarded rather than silently omitted, so this runs for real
wherever both binaries are present. Pointed at the local MP4 fixture path
exactly like `RawRtspFrameSource`'s integration tests do (T-050/T-051):
`ffmpeg -i <path>` treats a local file identically to an `rtsp://` URL for
the purposes of this test.
"""

import asyncio
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from app.infrastructure.streaming.recording_worker import FfmpegRecordingWorker

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed in this environment (docs/TECHNICAL_DECISIONS.md TD-22)",
)

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "sample.mp4"


async def _probe_duration(path: Path) -> float:
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    assert process.returncode == 0
    return float(stdout.decode().strip())


async def test_start_stop_produces_one_ffprobe_verifiable_segment(tmp_path: Path) -> None:
    worker = FfmpegRecordingWorker(
        camera_id=uuid4(),
        rtsp_url=str(_FIXTURE_PATH),
        output_dir=tmp_path,
        segment_duration_seconds=300,
        ffmpeg_binary_path="ffmpeg",
        ffprobe_binary_path="ffprobe",
    )

    in_progress = await worker.start()
    assert in_progress.ended_at is None
    await asyncio.sleep(1.0)
    segments = await worker.stop()

    assert len(segments) == 1
    segment = segments[0]
    assert segment.id == in_progress.id
    assert Path(segment.file_path).exists()
    assert segment.size_bytes is not None and segment.size_bytes > 0
    assert segment.duration_seconds is not None and segment.duration_seconds > 0

    real_duration = await _probe_duration(Path(segment.file_path))
    assert real_duration > 0
