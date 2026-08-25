# RTMP Push/Consume Demo

A standalone demo page proving a real RTMP publish → ingest → consume round trip, since the project has no physical RTMP camera. **Not part of the graded assignment scope** (see `docs/AI_PROJECT_CONTEXT.md`'s required-scope list — ONVIF/RTSP/MJPEG only) and not tracked in `docs/TASK_BACKLOG.md`; see `docs/IMPLEMENTATION_PLAN.md`'s "Addendum: RTMP Push/Consume Demo" and `docs/TECHNICAL_DECISIONS.md` TD-33 for how it fits alongside the rest of this codebase.

Isolated deliberately: its own backend package (`backend/app/infrastructure/rtmp_demo/`), its own `/rtmp-demo` API prefix and `/ws/rtmp-demo/status` WebSocket, its own frontend feature folder (`frontend/src/features/rtmp-demo/`) and route (`/rtmp-demo`). It reuses the existing `IFrameSource`/`StreamWorker`/`ReconnectSupervisor` streaming machinery and the M17 demo video library (`storage/demo_videos/`) rather than duplicating either.

---

## Architecture

```text
MP4 (storage/demo_videos/*.mp4)
   |
   | ffmpeg (re-encode: libx264)
   | RTMP PUSH
   v
MediaMTX  (rtmp://localhost:1935/live/demo-camera)
   |
   | RTMP CONSUME
   v
RtmpFrameSource (ffmpeg subprocess, via StreamWorker + ReconnectSupervisor)
   |
   v
MJPEG-over-HTTP  (/rtmp-demo/consumer/mjpeg)
   |
   v
<img> in the browser (frontend/src/features/rtmp-demo/RtmpVideoPlayer.tsx)
```

Three independently controllable lifecycles, each its own use case/API surface:

| Lifecycle | Backend | Port name |
|---|---|---|
| **Server** | `MediaMtxServerController` (subprocess) | `infrastructure/rtmp_demo/mediamtx_server.py` |
| **Publisher** | `FfmpegRtmpPublisher` (subprocess) | `infrastructure/rtmp_demo/ffmpeg_publisher.py` |
| **Consumer** | `RtmpFrameSource` (wrapped by `StreamWorker`) | `infrastructure/rtmp_demo/rtmp_frame_source.py` |

The displayed video is never the original MP4 loaded directly — it is decoded by `RtmpFrameSource` from frames pulled over RTMP from MediaMTX, then re-encoded to JPEG and streamed to the browser as MJPEG, the same transport every other view in this app (`streams.py`, `demo_videos.py`) already uses. The Video panel's "Sourced via RTMP Consume — not the original file" badge and the observed-resolution/observed-FPS diagnostics (measured from the actually-decoded frames, not the source file) are how the UI makes that verifiable rather than just asserted.

---

## Terminology

| Term | Meaning here |
|---|---|
| **RTMP Publisher** | The client pushing a stream *to* an RTMP server. Here: `ffmpeg -re -stream_loop -1 -i <file> ... -f flv rtmp://.../live/demo-camera` — reads the MP4 in real time (`-re`), loops it (`-stream_loop -1`) to simulate a continuous camera, re-encodes to H.264 (`libx264`), and pushes as an FLV-muxed RTMP stream. |
| **RTMP Server** | The process that accepts a publisher's incoming stream (ingest) and makes it available to consumers (serving). Here: [MediaMTX](https://github.com/bluenviron/mediamtx), a single Go binary. |
| **RTMP Ingest** | The server-side act of *receiving* a publisher's stream — the "push" endpoint. |
| **RTMP Consumer** | The client pulling the stream *from* the RTMP server. Here: `RtmpFrameSource`, decoding via a system `ffmpeg` subprocess piping raw frames on its stdout — not `cv2.VideoCapture` (the pattern `RawRtspFrameSource` uses for RTSP), which turned out not to be reliable enough for RTMP specifically; see [Reconnection behavior](#reconnection-behavior) and TD-33. |
| **Stream Key** | The path segment identifying *which* stream on the server (`demo-camera` by default) — analogous to a "channel name." Combined with the **Application** name (`live` by default) to form the full path `live/demo-camera`. |
| **Authentication** | Enforced entirely by MediaMTX (`authInternalUsers`, checked on publish and on read/play), never by application code — see [Authentication](#authentication) below. |
| **RTMP URL** | `rtmp://[user:pass@]host:port/app/stream_key` — e.g. `rtmp://localhost:1935/live/demo-camera`. The publisher and consumer both derive this from the same `Settings` fields, via `build_rtmp_url()` (`ffmpeg_publisher.py`). |
| **Media codec** | The video *compression format* — always H.264 (`libx264`) here, since the publisher always re-encodes to it. |
| **Container format** | The *wrapper* around encoded audio/video, distinct from the codec — here, FLV (`-f flv`), the standard RTMP payload container. |
| **Bitrate** | Encoded data rate, in kbps — configured on the publisher (`rtmp_publish_video_bitrate_kbps`, default 2000). |
| **FPS** | Frames per second — configured on the publisher (`rtmp_publish_fps`, default 25) and independently *measured* on the consumer from decoded-frame arrival timestamps. |

### RTMP PUSH vs. RTMP CONSUME

- **RTMP PUSH** — a publisher *sends* a stream to the server (`ffmpeg` → MediaMTX). The server is passive; the publisher initiates.
- **RTMP CONSUME** — a client *pulls* an already-published stream from the server (MediaMTX → `RtmpFrameSource`). The consumer initiates a *separate* connection; it never talks to the publisher directly. This is what proves the round trip is real: starting the Consumer before the Publisher (or after it stops) fails to connect exactly as it should, and recovers automatically once a stream is actually there — see [Reconnection](#reconnection-behavior) below.

---

## Authentication

- **Enforced by**: MediaMTX alone (`authInternalUsers` in the config `MediaMtxServerController` generates at `server/start`), checked during the RTMP handshake for both the `publish` and `read` actions. Application code (the publisher, the consumer, the API layer) never validates credentials itself — it only supplies them in the connection URL.
- **Publisher authentication**: if `RTMP_PUBLISH_USERNAME`/`RTMP_PUBLISH_PASSWORD` are both set, `ffmpeg` embeds them in the RTMP URL it connects to (`rtmp://user:pass@host:port/...`); MediaMTX rejects the publish attempt otherwise.
- **Consumer authentication**: same mechanism, independently, via `RTMP_READ_USERNAME`/`RTMP_READ_PASSWORD` — the consumer can require different credentials than the publisher, or none.
- **Local demo default**: both pairs unset, i.e. **auth disabled** — intentionally simplified for a local, single-developer demo. `MediaMtxServerController` handles a partially-configured pair (e.g. publish credentials set, read left unset) by adding an MediaMTX `any`-user fallback for whichever side wasn't configured, so setting one side never accidentally locks out the other.
- **Where credentials live**: `.env` at the repo root only, via `RTMP_PUBLISH_USERNAME`/`RTMP_PUBLISH_PASSWORD`/`RTMP_READ_USERNAME`/`RTMP_READ_PASSWORD` (see `.env.example`) — read exclusively through `app/core/config.py`'s `Settings`, per this repo's own "no `os.environ` outside `config.py`" rule. Never hardcoded, never logged (the RTMP URL is credential-bearing and is deliberately excluded from every log line and from the UI's displayed "RTMP destination"/"Stream URL", which show a credential-free form).

---

## Configuration

All in `backend/app/core/config.py`'s `Settings` (env var names in `.env.example`) — nothing is hardcoded outside it:

| Setting | Default | Purpose |
|---|---|---|
| `mediamtx_binary_path` | `mediamtx` | Binary name/path, same pattern as `ffmpeg_binary_path`. |
| `rtmp_server_host` / `rtmp_server_port` | `localhost` / `1935` | Where the server listens. |
| `rtmp_app_name` / `rtmp_stream_key` | `live` / `demo-camera` | The RTMP path, `app/stream_key`. |
| `rtmp_publish_username`/`password`, `rtmp_read_username`/`password` | unset | See [Authentication](#authentication). |
| `rtmp_publish_video_bitrate_kbps` | `2000` | Publisher encode bitrate. |
| `rtmp_publish_resolution` | `1280x720` | Publisher encode resolution. |
| `rtmp_publish_fps` | `25` | Publisher encode frame rate. |
| `rtmp_open_timeout_ms` / `rtmp_read_timeout_ms` | `12000` / `5000` | Consumer's first-frame-confirmation and per-frame stall timeouts (see [Reconnection behavior](#reconnection-behavior)). |
| `rtmp_demo_runtime_dir` | `storage/rtmp_demo/` (gitignored) | Where the generated `mediamtx.yml` is written. |

---

## Installation

Requires [MediaMTX](https://github.com/bluenviron/mediamtx) on `PATH`, in addition to the `ffmpeg`/`ffprobe` this project already requires:

```bash
brew install mediamtx
```

No further setup — the backend generates its own `mediamtx.yml` on `server/start` from `Settings` (see TD-33).

---

## Using the demo

1. Start the backend and frontend as usual (README's "Getting Started").
2. Open **http://localhost:5173/rtmp-demo**.
3. **Server** panel → *Start Server*.
4. **Publisher** panel → pick a video (from `storage/demo_videos/`) → *Start Publishing*.
5. **Consumer** panel → *Start Consumer*.
6. The **Video** panel shows the decoded stream, plus live diagnostics.

### Local test flow (matches the request's 12-step flow)

1. Start the application (backend + frontend).
2. Start the RTMP server (`POST /rtmp-demo/server/start`) → `GET /rtmp-demo/server/status` reports `running: true`.
3. Select a sample MP4 (`GET /rtmp-demo/videos`).
4. Start RTMP publishing (`POST /rtmp-demo/publisher/start`) → `publisher/status` reports `running: true`.
5. Verify the server received the stream → `server/status`'s implied "published" state in the UI (Server panel cross-references Publisher status).
6. Start the consumer (`POST /rtmp-demo/consumer/start`).
7. Verify the consumer connects → `consumer/status`'s `state` reaches `connected`, with non-null `observed_resolution`/`observed_fps`.
8. See the consumed video on `/rtmp-demo` (the Video panel's `<img>`, fed by `/rtmp-demo/consumer/mjpeg`).
9. Stop the publisher (`POST /rtmp-demo/publisher/stop`).
10. Verify the app detects the lost stream → `consumer/status`'s `state` moves to `reconnecting`, `consecutive_failures` increments.
11. Restart the publisher.
12. Verify the consumer reconnects → `state` returns to `connected` without any consumer-side action.

This exact flow (steps 6–12) is what `backend/tests/integration/rtmp_demo/test_rtmp_demo_integration.py` exercises against the real `mediamtx`/`ffmpeg` binaries — see [Testing](#testing) below.

---

## Reconnection behavior

The Consumer's `RtmpFrameSource` is wrapped by the same `StreamWorker`/`ReconnectSupervisor` every other video source in this codebase uses (`stream_worker_reconnect_backoff_seconds` in `Settings`, default `[1, 2, 4, 8, 16, 30]`, capped rather than exhausted-and-give-up) — no new reconnect logic was written for this demo. This is what makes starting the Consumer before the Publisher, or after it stops, self-heal automatically once a stream becomes available, rather than requiring a manual retry.

**History** (see TD-33 for the full writeup): the Consumer originally decoded via `cv2.VideoCapture` (`RawRtspFrameSource`'s pattern). In practice, `opencv-python-headless`'s bundled FFmpeg — older than this machine's system `ffmpeg` — periodically lost sync with MediaMTX a few seconds into a session (`RTMP packet size mismatch` / `frame stream ended unexpectedly`), causing frequent, continuous reconnect cycling (each failed attempt costing several seconds of frozen video) rather than an occasional blip. Switching the Consumer to a system-`ffmpeg` subprocess (piping raw frames, this module's current implementation) resolved it: the real bug was ffmpeg's *default* probe window being too short for MediaMTX's RTMP output ("could not find codec parameters" on the very first connection) — `RtmpFrameSource` now passes explicit `-analyzeduration`/`-probesize` values wide enough to cover that, confirmed stable in repeated testing. `rtmp_open_timeout_ms` (default `12000`) is sized to comfortably cover that wider probe window without falsely timing out a normal connection.

---

## Error handling

| Scenario | How it surfaces |
|---|---|
| 1. RTMP server unavailable | `server/start` raises `RtmpServerUnavailableError` → `503`; publisher/consumer connect attempts fail and are retried/reported per below. |
| 2. Publisher cannot connect | `ffmpeg` exits non-zero quickly; `publisher/status` reports `exited_unexpectedly: true` with an error message (never raw ffmpeg stderr — TD-15). |
| 3. Invalid RTMP URL | Same as #2 — a malformed destination fails to open at the `ffmpeg` level. |
| 4. Invalid authentication | MediaMTX rejects the RTMP handshake; surfaces identically to #2 (publisher) or #6 (consumer) — there is no separate "auth failed" signal at the RTMP protocol level, by design of the protocol itself. |
| 5. Stream does not exist (consumer starts first) | `RtmpFrameSource.start()` raises `FrameSourceUnavailableError`; `ReconnectSupervisor` retries with backoff — `consumer/status.state` shows `reconnecting`. |
| 6. Consumer cannot connect | Same as #5. |
| 7. Publisher stops unexpectedly | `publisher/status.exited_unexpectedly` becomes `true`; the Consumer independently notices the dropped stream and moves to `reconnecting` — proven by `test_rtmp_demo_integration.py`. |
| 8. RTMP server restarts | Publisher's next push fails (connection reset) → #2; Consumer's next read fails → #5/#6. Both recover once the server (and publisher) are back. |
| 9. Video file does not exist | `ManageRtmpPublisherUseCase` resolves `video_id` via the same `IDemoVideoRepository` M17 uses — an unknown/deleted id raises the existing `DemoVideoNotFoundError` → `404`. |
| 10. Unsupported/corrupt video file | `ffmpeg` exits non-zero — same as #2. |

Nothing above logs a credential-bearing RTMP URL or raw subprocess stderr (TD-15) — publisher/server failures report a status code or a generic message only.

---

## Testing

- **Unit** (fakes, no I/O): `backend/tests/unit/application/test_manage_rtmp_server.py`, `test_manage_rtmp_publisher.py`, `test_start_rtmp_consumer.py`.
- **Integration** (real `mediamtx` + `ffmpeg`, skipped automatically if either isn't on `PATH`): `backend/tests/integration/rtmp_demo/test_rtmp_demo_integration.py` — publishes the committed `sample.mp4` fixture, consumes it over a real RTMP round trip, stops the publisher, and confirms the consumer reconnects once it restarts.

```bash
cd backend
uv run pytest tests/unit/application/test_manage_rtmp_server.py tests/unit/application/test_manage_rtmp_publisher.py tests/unit/application/test_start_rtmp_consumer.py
uv run pytest tests/integration/rtmp_demo/
```
