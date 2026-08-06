import { useState } from 'react';
import AnalyticsToggle from '../components/AnalyticsToggle';
import Panel from '../components/Panel';
import DetectionOverlay from '../features/analytics-console/DetectionOverlay';
import DemoVideoPlayer from '../features/demo/DemoVideoPlayer';
import useAnalyticsStatus from '../hooks/useAnalyticsStatus';
import useDemoVideos from '../hooks/useDemoVideos';
import type { DemoVideoResponse } from '../types/demoVideo';

/**
 * `/demo` (M17) — play a pre-recorded clip from `storage/demo_videos/` with
 * no camera or network video source involved, to demo an analytics
 * capability (starting with License Plate Recognition) on cue. Lists every
 * file an operator has dropped into that directory (no upload flow — see
 * docs/IMPLEMENTATION_PLAN.md §M17's Explicitly Out of Scope) and composes
 * the same `AnalyticsToggle`/`DetectionOverlay` every camera view already
 * uses, unchanged.
 */
function DemoPage() {
  const { data: videos, isLoading, isError } = useDemoVideos();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (isLoading) return <p className="text-sm text-slate-500">Loading demo videos…</p>;
  if (isError) return <p className="text-sm text-red-600">Failed to load demo videos.</p>;
  if (!videos || videos.length === 0) {
    return (
      <Panel title="Demo Videos">
        <p className="text-sm text-slate-500">
          No demo videos found. Drop a video file (.mp4, .mov, .mkv) into{' '}
          <code className="rounded bg-slate-100 px-1 py-0.5">storage/demo_videos/</code> and reload
          this page.
        </p>
      </Panel>
    );
  }

  const selected = videos.find((video) => video.id === selectedId) ?? videos[0];

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Panel title="Demo Videos" description="Play a pre-recorded clip and enable analytics on it.">
        <ul className="grid gap-2 sm:grid-cols-2">
          {videos.map((video) => (
            <VideoListItem
              key={video.id}
              video={video}
              selected={video.id === selected.id}
              onSelect={() => setSelectedId(video.id)}
            />
          ))}
        </ul>
      </Panel>

      <DemoVideoPanel key={selected.id} video={selected} />
    </div>
  );
}

function VideoListItem({
  video,
  selected,
  onSelect,
}: {
  video: DemoVideoResponse;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left text-sm ${
          selected
            ? 'border-slate-900 bg-slate-900 text-white'
            : 'border-slate-300 text-slate-700 hover:bg-slate-100'
        }`}
      >
        <span className="truncate">{video.filename}</span>
        <PlayIcon />
      </button>
    </li>
  );
}

function DemoVideoPanel({ video }: { video: DemoVideoResponse }) {
  const analytics = useAnalyticsStatus(video.id);

  return (
    <Panel title={video.filename} actions={<AnalyticsToggle sourceId={video.id} />}>
      <DemoVideoPlayer
        videoId={video.id}
        filename={video.filename}
        overlay={analytics.enabled ? <DetectionOverlay sourceId={video.id} /> : undefined}
      />
    </Panel>
  );
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 shrink-0" fill="currentColor" aria-hidden="true">
      <path d="M4 2.5v11l10-5.5z" />
    </svg>
  );
}

export default DemoPage;
