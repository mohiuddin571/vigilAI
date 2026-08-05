import type { ReactNode } from 'react';
import useLiveStream from '../../hooks/useLiveStream';
import type { StreamState } from '../../types/stream';

interface LiveViewProps {
  cameraId: string;
  cameraName: string;
  /**
   * Rendered over the `<img>` inside the same `relative` wrapper (e.g. a
   * `DetectionOverlay` from `analytics-console/`, T-093). A generic slot
   * rather than a direct import, since `features/` never import each other
   * (docs/FOLDER_STRUCTURE.md) — the composition happens in `App.tsx`.
   */
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

function LiveView({ cameraId, cameraName, overlay }: LiveViewProps) {
  const { status, mjpegUrl, isConnecting, start, stop } = useLiveStream(cameraId);
  const state = status?.state ?? 'stopped';
  const isStreaming = state !== 'stopped';

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

export default LiveView;
