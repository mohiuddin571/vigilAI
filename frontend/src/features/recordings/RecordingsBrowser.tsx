import { useState } from 'react';
import useRecordingsList from '../../hooks/useRecordingsList';
import { recordingMediaUrl } from '../../services/recordingsApi';
import type { CameraResponse } from '../../types/camera';
import type { RecordingResponse } from '../../types/recording';

interface RecordingsBrowserProps {
  cameras: CameraResponse[];
}

function formatSize(bytes: number | null): string {
  if (bytes === null) return '—';
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return 'in progress';
  return `${seconds.toFixed(0)}s`;
}

/** `datetime-local` input value (local time, no timezone) -> ISO 8601 for the API, or undefined if empty. */
function toIsoOrUndefined(localDateTime: string): string | undefined {
  if (!localDateTime) return undefined;
  const date = new Date(localDateTime);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

// M7 (Playback): camera/time-range filter controls + a native <video> player
// with seek, composing alongside (not replacing) RecordingControl.tsx's
// existing start/stop control and list.
function RecordingsBrowser({ cameras }: RecordingsBrowserProps) {
  const [cameraId, setCameraId] = useState<string>('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [selectedRecording, setSelectedRecording] = useState<RecordingResponse | null>(null);

  const { data, isLoading, isError } = useRecordingsList({
    cameraId: cameraId || undefined,
    start: toIsoOrUndefined(start),
    end: toIsoOrUndefined(end),
  });
  const recordings = data ?? [];

  const cameraName = (id: string): string =>
    cameras.find((camera) => camera.id === id)?.name ?? id;

  return (
    <div className="space-y-3 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          Camera
          <select
            className="rounded border border-slate-300 px-2 py-1"
            value={cameraId}
            onChange={(event) => setCameraId(event.target.value)}
          >
            <option value="">All cameras</option>
            {cameras.map((camera) => (
              <option key={camera.id} value={camera.id}>
                {camera.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          From
          <input
            type="datetime-local"
            className="rounded border border-slate-300 px-2 py-1"
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          To
          <input
            type="datetime-local"
            className="rounded border border-slate-300 px-2 py-1"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
          />
        </label>
      </div>

      {isError && <p className="text-xs text-red-600">Failed to load recordings.</p>}

      {isLoading ? (
        <p className="text-sm text-slate-400">Loading recordings…</p>
      ) : recordings.length === 0 ? (
        <p className="text-sm text-slate-400">No recordings match these filters.</p>
      ) : (
        <ul className="divide-y divide-slate-200 rounded border border-slate-200 bg-white text-sm text-slate-600">
          {recordings.map((recording) => (
            <li key={recording.id}>
              <button
                type="button"
                onClick={() => setSelectedRecording(recording)}
                className={`flex w-full items-center justify-between px-2 py-1.5 text-left hover:bg-slate-50 ${
                  selectedRecording?.id === recording.id ? 'bg-slate-100' : ''
                }`}
              >
                <span className="truncate">
                  {cameraName(recording.camera_id)} · {new Date(recording.started_at).toLocaleString()}
                </span>
                <span className="ml-2 shrink-0 text-xs text-slate-400">
                  {formatDuration(recording.duration_seconds)} · {formatSize(recording.size_bytes)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {selectedRecording && (
        <video
          key={selectedRecording.id}
          controls
          className="w-full rounded"
          src={recordingMediaUrl(selectedRecording.id)}
        />
      )}
    </div>
  );
}

export default RecordingsBrowser;
