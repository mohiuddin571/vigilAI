import Panel from '../../components/Panel';
import type { RtmpConsumerStatusResponse } from '../../types/rtmpDemo';
import type { StreamState } from '../../types/stream';
import { StateDot, StatusRow } from './shared';

const STATE_LABEL: Record<StreamState, string> = {
  connecting: 'Connecting…',
  connected: 'Connected',
  reconnecting: 'Reconnecting…',
  failed: 'Failed',
  stopped: 'Stopped',
};

interface ConsumerPanelProps {
  status: RtmpConsumerStatusResponse | null;
  isStarting: boolean;
  onStart: () => void;
  onStop: () => void;
}

/** Consumer panel (docs/RTMP_DEMO.md) — the application's own RTMP client, connecting to the
 * RTMP Server independently of the Publisher (this is what request scenario #5/#6 — connecting
 * before/without a publisher — makes visible via `Reconnecting…`). */
function ConsumerPanel({ status, isStarting, onStart, onStop }: ConsumerPanelProps) {
  const state = status?.state ?? 'stopped';
  const running = state !== 'stopped';

  return (
    <Panel title="Consumer" description="RTMP Server → RTMP CONSUME → Application">
      <div className="space-y-3 text-sm">
        <StatusRow label="Connection status">
          <StateDot ok={state === 'connected'} />
          <span>{STATE_LABEL[state]}</span>
        </StatusRow>
        <StatusRow label="Stream URL">
          <code className="max-w-[16rem] truncate rounded bg-slate-100 px-1.5 py-0.5">
            {status?.rtmp_url ?? '—'}
          </code>
        </StatusRow>
        <StatusRow label="Authentication status">
          <span>{status?.read_auth_required ? 'Required (configured)' : 'Disabled (local demo default)'}</span>
        </StatusRow>
        {status && status.consecutive_failures > 0 && (
          <StatusRow label="Reconnect attempts">
            <span>{status.consecutive_failures}</span>
          </StatusRow>
        )}
        {status?.last_error && <p className="text-xs text-red-600">{status.last_error}</p>}

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            onClick={onStart}
            disabled={running || isStarting}
          >
            Start Consumer
          </button>
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 disabled:opacity-40"
            onClick={onStop}
            disabled={!running}
          >
            Stop Consumer
          </button>
        </div>
      </div>
    </Panel>
  );
}

export default ConsumerPanel;
