import Panel from '../../components/Panel';
import type { RtmpConsumerStatusResponse } from '../../types/rtmpDemo';

interface RtmpVideoPlayerProps {
  status: RtmpConsumerStatusResponse | null;
  mjpegUrl: string;
}

/** Video panel (docs/RTMP_DEMO.md) — the `<img>`-over-MJPEG player every other view in this app
 * already uses (`LiveView`/`DemoVideoPlayer`), pointed at `/rtmp-demo/consumer/mjpeg`: frames
 * that traveled through the full RTMP publish → ingest → consume round trip, never the original
 * file directly (the request's core requirement — see the badge below). Diagnostics distinguish
 * what's actually measured (`observed_*`, from decoded frames) from what's only known from the
 * publisher's own encode configuration (`configured_*` — see `start_rtmp_consumer.py`'s
 * docstring for why codec/bitrate can't be reliably measured here). */
function RtmpVideoPlayer({ status, mjpegUrl }: RtmpVideoPlayerProps) {
  const state = status?.state ?? 'stopped';
  const isStreaming = state === 'connected' || state === 'reconnecting';

  return (
    <Panel title="Video" description="Decoded from the RTMP Consumer">
      <div className="space-y-3">
        <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          Sourced via RTMP Consume — not the original file
        </div>

        {isStreaming ? (
          <img
            src={mjpegUrl}
            alt="RTMP demo consumer playback"
            className="w-full rounded border border-slate-200 bg-black"
          />
        ) : (
          <div className="flex h-56 items-center justify-center rounded border border-dashed border-slate-300 text-sm text-slate-400">
            No video — start the Consumer above.
          </div>
        )}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-t border-slate-100 pt-3 text-sm sm:grid-cols-3">
          <DiagnosticItem
            label="Resolution (observed)"
            value={
              status?.observed_resolution
                ? `${status.observed_resolution[0]}×${status.observed_resolution[1]}`
                : '—'
            }
          />
          <DiagnosticItem
            label="FPS (observed)"
            value={status?.observed_fps ? status.observed_fps.toFixed(1) : '—'}
          />
          <DiagnosticItem label="Codec (configured)" value={status?.configured_codec ?? '—'} />
          <DiagnosticItem
            label="Bitrate (configured)"
            value={status ? `${status.configured_video_bitrate_kbps} kbps` : '—'}
          />
          <DiagnosticItem label="Connection" value={state} />
          <DiagnosticItem
            label="Reconnect attempts"
            value={String(status?.consecutive_failures ?? 0)}
          />
        </dl>
        {status?.last_error && <p className="text-xs text-red-600">Error: {status.last_error}</p>}
      </div>
    </Panel>
  );
}

function DiagnosticItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="text-slate-800">{value}</dd>
    </div>
  );
}

export default RtmpVideoPlayer;
