import { useState } from 'react';
import Panel from '../../components/Panel';
import useRtmpDemoVideos from '../../hooks/useRtmpDemoVideos';
import type { RtmpPublisherStatusResponse } from '../../types/rtmpDemo';
import { StateDot, StatusRow } from './shared';

interface PublisherPanelProps {
  status: RtmpPublisherStatusResponse | null;
  rtmpUrl: string;
  isStarting: boolean;
  onStart: (videoId: string) => void;
  onStop: () => void;
}

/** Publisher panel (docs/RTMP_DEMO.md) — the simulated camera: a video file, looped and
 * re-encoded by ffmpeg, pushed to the RTMP Server. Video choices reuse the same
 * `storage/demo_videos/` library `/demo` already lists (`useRtmpDemoVideos`). */
function PublisherPanel({ status, rtmpUrl, isStarting, onStart, onStop }: PublisherPanelProps) {
  const { data: videos } = useRtmpDemoVideos();
  const [selectedVideoId, setSelectedVideoId] = useState('');
  const running = status?.running ?? false;
  const effectiveVideoId = selectedVideoId || status?.video_id || videos?.[0]?.id || '';

  return (
    <Panel title="Publisher" description="Video File → ffmpeg → RTMP PUSH">
      <div className="space-y-3 text-sm">
        <div>
          <label className="mb-1 block font-medium text-slate-700" htmlFor="rtmp-video-source">
            Video source (simulated camera)
          </label>
          <select
            id="rtmp-video-source"
            className="w-full rounded border border-slate-300 px-2 py-1.5 disabled:bg-slate-100"
            value={effectiveVideoId}
            onChange={(event) => setSelectedVideoId(event.target.value)}
            disabled={running}
          >
            {!videos?.length && <option value="">No demo videos found</option>}
            {videos?.map((video) => (
              <option key={video.id} value={video.id}>
                {video.filename}
              </option>
            ))}
          </select>
        </div>

        <StatusRow label="Publisher status">
          <StateDot ok={running} />
          <span>
            {running ? 'Publishing' : status?.exited_unexpectedly ? 'Stopped unexpectedly' : 'Stopped'}
          </span>
        </StatusRow>
        <StatusRow label="RTMP destination">
          <code className="max-w-[16rem] truncate rounded bg-slate-100 px-1.5 py-0.5">{rtmpUrl}</code>
        </StatusRow>
        {status?.publish_auth_required && (
          <p className="text-xs text-slate-500">
            Publish authentication required (RTMP_PUBLISH_USERNAME/PASSWORD).
          </p>
        )}
        {status?.error && <p className="text-xs text-red-600">{status.error}</p>}

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            onClick={() => onStart(effectiveVideoId)}
            disabled={running || isStarting || !effectiveVideoId}
          >
            Start Publishing
          </button>
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 disabled:opacity-40"
            onClick={onStop}
            disabled={!running}
          >
            Stop Publishing
          </button>
        </div>
      </div>
    </Panel>
  );
}

export default PublisherPanel;
