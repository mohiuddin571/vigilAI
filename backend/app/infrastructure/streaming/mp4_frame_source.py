import asyncio
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import cv2

from app.application.ports.frame_source import IFrameSource
from app.domain.entities.frame import Frame
from app.domain.exceptions import FrameSourceUnavailableError

_DEFAULT_FPS = 25.0

# See `infrastructure/streaming/rtsp_frame_source.py`'s top-of-file note:
# every `cap` call below runs on this instance's own dedicated single-worker
# executor, not the shared `asyncio.to_thread` pool, so `stop()`'s
# `cap.release()` can never race a still-in-flight `cap.read()`/`cap.set()`
# on a different OS thread.


class Mp4FileFrameSource(IFrameSource):
    """Reads frames from a local MP4 file via OpenCV `VideoCapture` (TD-04, TD-20).

    The primary development/demo frame source (docs/ARCHITECTURE.md §5) —
    proves `IFrameSource` end-to-end with no camera/network dependency, and
    is what CI runs analytics against.

    Constructor args are plain, picklable values only (str, bool, float)
    because a factory built from this class must cross a `multiprocessing`
    "spawn" boundary — see `infrastructure/streaming/stream_worker.py`.
    """

    def __init__(
        self,
        file_path: str,
        source_id: str,
        *,
        loop: bool = True,
        fps: float | None = None,
    ) -> None:
        self._file_path = file_path
        self._source_id = source_id
        self._loop = loop
        self._fps_override = fps
        self._cap: cv2.VideoCapture | None = None
        self._interval = 1.0 / _DEFAULT_FPS
        self._executor: ThreadPoolExecutor | None = None

    @property
    def source_id(self) -> str:
        return self._source_id

    async def start(self) -> None:
        executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_running_loop()
        cap = await loop.run_in_executor(executor, cv2.VideoCapture, self._file_path)
        if not cap.isOpened():
            await loop.run_in_executor(executor, cap.release)
            await asyncio.to_thread(executor.shutdown)
            raise FrameSourceUnavailableError(f"Could not open MP4 file: {self._file_path}")
        fps = self._fps_override or cap.get(cv2.CAP_PROP_FPS) or _DEFAULT_FPS
        self._interval = 1.0 / fps
        self._cap = cap
        self._executor = executor

    async def stop(self) -> None:
        if self._cap is not None and self._executor is not None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._cap.release)
            self._cap = None
        if self._executor is not None:
            executor = self._executor
            self._executor = None
            await asyncio.to_thread(executor.shutdown)

    async def frames(self) -> AsyncIterator[Frame]:
        if self._cap is None or self._executor is None:
            raise FrameSourceUnavailableError("start() must succeed before frames() is iterated")
        cap = self._cap
        executor = self._executor
        loop = asyncio.get_running_loop()
        sequence = 0
        while self._cap is not None:
            loop_start = time.monotonic()
            ok, image = await loop.run_in_executor(executor, cap.read)
            if not ok:
                if not self._loop:
                    return
                await loop.run_in_executor(executor, cap.set, cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            yield Frame(
                source_id=self._source_id,
                sequence=sequence,
                timestamp=datetime.now(UTC),
                image=image,
            )
            sequence += 1
            elapsed = time.monotonic() - loop_start
            await asyncio.sleep(max(0.0, self._interval - elapsed))
