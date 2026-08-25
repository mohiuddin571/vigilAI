import Panel from '../../components/Panel';
import type { RtmpServerStatusResponse } from '../../types/rtmpDemo';
import { StateDot, StatusRow } from './shared';

interface ServerPanelProps {
  status: RtmpServerStatusResponse | null;
  /** Whether the Publisher is currently pushing to this server — a distinct
   * concern from the server *process* being up (`status.running`): the
   * server can run with nothing published to it. */
  publishing: boolean;
  isStarting: boolean;
  onStart: () => void;
  onStop: () => void;
}

/** RTMP Server panel (docs/RTMP_DEMO.md) — MediaMTX process status, host/port/app/stream name. */
function ServerPanel({ status, publishing, isStarting, onStart, onStop }: ServerPanelProps) {
  const running = status?.running ?? false;

  return (
    <Panel title="RTMP Server" description="MediaMTX — RTMP ingest + serving">
      <div className="space-y-3 text-sm">
        <StatusRow label="Server status">
          <StateDot ok={running} />
          <span>{running ? 'Running' : 'Stopped'}</span>
        </StatusRow>
        <StatusRow label="Host">
          <span>{status?.host ?? '—'}</span>
        </StatusRow>
        <StatusRow label="Port">
          <span>{status?.port ?? '—'}</span>
        </StatusRow>
        <StatusRow label="Application">
          <span>{status?.app_name ?? '—'}</span>
        </StatusRow>
        <StatusRow label="Stream name">
          <span>{status?.stream_key ?? '—'}</span>
        </StatusRow>
        <StatusRow label="Published">
          <StateDot ok={running && publishing} />
          <span>{running && publishing ? 'Published' : 'Not published'}</span>
        </StatusRow>

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            onClick={onStart}
            disabled={running || isStarting}
          >
            Start Server
          </button>
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 disabled:opacity-40"
            onClick={onStop}
            disabled={!running}
          >
            Stop Server
          </button>
        </div>
      </div>
    </Panel>
  );
}

export default ServerPanel;
