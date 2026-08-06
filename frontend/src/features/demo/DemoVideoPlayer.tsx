import { useEffect } from 'react';
import type { ReactNode } from 'react';
import useDemoStream from '../../hooks/useDemoStream';
import type { StreamState } from '../../types/stream';

interface DemoVideoPlayerProps {
  videoId: string;
  filename: string;
  overlay?: ReactNode;
}

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
 * Plays one demo video library entry (M17) — structurally the same
 * connect/disconnect/state-dot/`<img>`+overlay shape as
 * `components/LiveView.tsx`, but built on `useDemoStream` instead of
 * `useLiveStream`. Kept as its own small component under `features/demo/`
 * (per docs/FOLDER_STRUCTURE.md's convention: page-specific composition
 * lives in `features/`, not `components/`) rather than generalizing
 * `LiveView` itself to accept an injected hook — `LiveView` is shared by the
 * Dashboard, Camera Detail, and standalone Live View page today, and this
 * repo's own precedent (`StartDemoStreamUseCase` vs `StartLiveStreamUseCase`)
 * is small deliberate duplication over a cross-cutting abstraction here.
 *
 * Auto-connects on mount/video change and disconnects on unmount — there's
 * no separate camera-onboarding step to wait for, so unlike `LiveView`'s
 * default (explicit Connect button), starting playback immediately when a
 * clip is selected matches this page's "pick a clip, see it play" intent.
 */
function DemoVideoPlayer({ videoId, filename, overlay }: DemoVideoPlayerProps) {
  const { status, mjpegUrl, start, stop } = useDemoStream(videoId);
  const state = status?.state ?? 'stopped';
  const isStreaming = state !== 'stopped';

  useEffect(() => {
    start();
    return () => stop();
  }, [start, stop]);

  return (
    <div className="space-y-2 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <span className={`h-2.5 w-2.5 rounded-full ${STATE_DOT_CLASS[state]}`} />
        <span>{STATE_LABEL[state]}</span>
      </div>

      {isStreaming ? (
        <div className="relative">
          <img src={mjpegUrl} alt={`Demo playback for ${filename}`} className="w-full rounded" />
          {overlay}
        </div>
      ) : (
        <p className="text-sm text-slate-400">Starting playback…</p>
      )}

      {status?.last_error && <p className="text-xs text-red-600">{status.last_error}</p>}
    </div>
  );
}

export default DemoVideoPlayer;
