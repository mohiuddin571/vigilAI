import { useEffect } from 'react';
import type { ReactNode } from 'react';
import useLiveStream from '../hooks/useLiveStream';
import type { StreamState } from '../types/stream';

interface LiveViewProps {
  cameraId: string;
  cameraName: string;
  /**
   * Rendered over the `<img>` inside the same `relative` wrapper (e.g. a
   * `DetectionOverlay` from `analytics-console/`, T-093). A generic slot
   * rather than a direct import, since `features/` never import each other
   * (docs/FOLDER_STRUCTURE.md) — the composition happens in the page/feature
   * that renders both.
   */
  overlay?: ReactNode;
  /**
   * Connect as soon as this mounts and disconnect on unmount, instead of
   * waiting for the Connect button (docs/UI_UX_DESIGN.md §6.1 — Dashboard
   * camera tiles). Default off, so the standalone `/live/:id` page keeps its
   * documented explicit-connect behavior.
   */
  autoStart?: boolean;
  /**
   * Icon-only Connect/Disconnect controls instead of labeled buttons, for
   * tight spaces (Dashboard camera tiles). Default off, so the standalone
   * `/live/:id` page and Camera Detail's Live View tab keep labeled buttons.
   */
  compact?: boolean;
}

/**
 * Minimum time between an `autoStart` stop and the next start for the same
 * mount. Real cameras here decode HEVC over RTSP via OpenCV's bundled
 * FFmpeg, whose multithreaded decoder has a known teardown race — starting
 * a new decode session before the previous one's threads have fully wound
 * down can trip `Assertion fctx->async_lock failed` in
 * `libavcodec/pthread_frame.c`, which aborts the whole Stream Worker
 * subprocess (a native crash, unrecoverable from Python). Two things send
 * start/stop back-to-back without this delay: React's `StrictMode`
 * (`main.tsx`) deliberately double-invokes every effect in dev — mount,
 * cleanup, mount again — so every `autoStart` mount would otherwise fire a
 * real start/stop/start in immediate succession; and a user genuinely
 * navigating away and back within a couple seconds. Delaying the *start*
 * (never the stop, so resources still free promptly) means the
 * `StrictMode` double-invoke's first start never actually fires — its
 * timeout is cleared by cleanup before it elapses — and a real navigate-away
 * gets a clean gap before reconnecting.
 */
const AUTO_START_DEBOUNCE_MS = 2000;

const STATE_LABEL: Record<StreamState, string> = {
  connecting: 'Connecting…',
  connected: 'Connected',
  reconnecting: 'Reconnecting…',
  failed: 'Failed',
  stopped: 'Stopped',
};

const STATE_DOT_CLASS: Record<StreamState, string> = {
  connecting: 'bg-amber-400',
  connected: 'bg-emerald-500',
  reconnecting: 'bg-amber-400',
  failed: 'bg-red-500',
  stopped: 'bg-slate-300',
};

/**
 * Live MJPEG view for one camera (T-055). Extracted from `features/live-view/`
 * into `components/` (shared, feature-agnostic — docs/FOLDER_STRUCTURE.md)
 * once the Dashboard camera grid and the standalone Live View page both
 * needed it — same move already made for `AnalyticsToggle`.
 */
function LiveView({ cameraId, cameraName, overlay, autoStart = false, compact = false }: LiveViewProps) {
  const { status, mjpegUrl, isConnecting, start, stop } = useLiveStream(cameraId);
  const state = status?.state ?? 'stopped';
  const isStreaming = state !== 'stopped';

  useEffect(() => {
    if (!autoStart) return;
    const timeoutId = window.setTimeout(start, AUTO_START_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timeoutId);
      stop();
    };
  }, [autoStart, start, stop]);

  return (
    <div className="space-y-2 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <span className={`h-2.5 w-2.5 rounded-full ${STATE_DOT_CLASS[state]}`} />
          <span>{STATE_LABEL[state]}</span>
          {status?.consecutive_failures ? (
            <span className="text-xs text-slate-400">
              ({status.consecutive_failures} failed attempt
              {status.consecutive_failures === 1 ? '' : 's'})
            </span>
          ) : null}
        </div>
        <div className="flex gap-2">
          {compact ? (
            <>
              <button
                type="button"
                onClick={start}
                disabled={isConnecting || isStreaming}
                aria-label="Connect"
                title="Connect"
                className="rounded bg-slate-900 p-1.5 text-white disabled:opacity-50"
              >
                <PlayIcon />
              </button>
              <button
                type="button"
                onClick={stop}
                disabled={!isStreaming}
                aria-label="Disconnect"
                title="Disconnect"
                className="rounded border border-slate-300 p-1.5 text-slate-700 disabled:opacity-50"
              >
                <StopIcon />
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={start}
                disabled={isConnecting || isStreaming}
                className="rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
              >
                Connect
              </button>
              <button
                type="button"
                onClick={stop}
                disabled={!isStreaming}
                className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 disabled:opacity-50"
              >
                Disconnect
              </button>
            </>
          )}
        </div>
      </div>

      {isStreaming ? (
        <div className="relative">
          <img src={mjpegUrl} alt={`Live view for ${cameraName}`} className="w-full rounded" />
          {overlay}
        </div>
      ) : (
        <p className="text-sm text-slate-400">Not connected.</p>
      )}

      {status?.last_error && (
        <p className="text-xs text-red-600">{status.last_error}</p>
      )}
    </div>
  );
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor" aria-hidden="true">
      <path d="M4 2.5v11l10-5.5z" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor" aria-hidden="true">
      <rect x="3.5" y="3.5" width="9" height="9" />
    </svg>
  );
}

export default LiveView;
