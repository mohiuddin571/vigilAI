"""Benchmark `YoloObjectDetector.process()`'s throughput on this machine (T-092).

Measures wall-clock FPS against either the committed MP4 fixture (default)
or a real onboarded camera's live RTSP stream (`--camera-id`), using the
exact same `YoloObjectDetector`/`Settings` the running application would use.
The model-load call is excluded from the timed loop (a one-time cold-start
cost, not a per-frame one). Findings are recorded in
docs/TECHNICAL_DECISIONS.md TD-25, per T-092's Definition of Done.

Usage (from `backend/`):
    uv run python ../scripts/benchmark_yolo_fps.py --frames 30
    uv run python ../scripts/benchmark_yolo_fps.py --frames 30 --camera-id <uuid>
"""

import argparse
import asyncio
import time
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.core.container import Container
from app.domain.entities.frame import Frame
from app.infrastructure.analytics.yolo_detector import YoloObjectDetector
from app.infrastructure.streaming.mp4_frame_source import Mp4FileFrameSource

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "sample.mp4"
)


async def _collect_frames_from_mp4(count: int) -> list[Frame]:
    source = Mp4FileFrameSource(file_path=str(_FIXTURE_PATH), source_id="benchmark-mp4", loop=True)
    await source.start()
    try:
        frames: list[Frame] = []
        async for frame in source.frames():
            frames.append(frame)
            if len(frames) >= count:
                return frames
        return frames
    finally:
        await source.stop()


async def _collect_frames_from_camera(camera_id: UUID, count: int) -> list[Frame]:
    # `_build_analytics_frame_source` is the container's private wiring
    # method, deliberately reused here (rather than reimplemented) so this
    # benchmark measures the exact same frame-source path the running
    # application uses for a camera-backed analytics source.
    container = Container(settings)
    source = await container._build_analytics_frame_source(str(camera_id))  # noqa: SLF001
    await source.start()
    try:
        frames: list[Frame] = []
        async for frame in source.frames():
            frames.append(frame)
            if len(frames) >= count:
                return frames
        return frames
    finally:
        await source.stop()


async def main(frame_count: int, camera_id: UUID | None) -> None:
    frames = (
        await _collect_frames_from_camera(camera_id, frame_count)
        if camera_id is not None
        else await _collect_frames_from_mp4(frame_count)
    )
    if not frames:
        raise SystemExit("No frames collected — check the source is reachable.")

    detector = YoloObjectDetector(
        model_path=str(settings.yolo_model_path),
        confidence_threshold=settings.yolo_confidence_threshold,
        iou_threshold=settings.yolo_iou_threshold,
        device=settings.yolo_device,
    )
    await detector.process(frames[0], context={})  # cold-start load, excluded from timing

    start = time.perf_counter()
    total_detections = 0
    for frame in frames:
        total_detections += len(await detector.process(frame, context={}))
    elapsed = time.perf_counter() - start

    print(f"source: {'camera ' + str(camera_id) if camera_id else 'mp4 fixture'}")
    print(f"frames: {len(frames)}")
    print(f"elapsed: {elapsed:.2f}s")
    print(f"fps: {len(frames) / elapsed:.2f}")
    print(f"total detections: {total_detections}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--camera-id", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.frames, UUID(args.camera_id) if args.camera_id else None))
