import useRecording from '../../hooks/useRecording';

interface RecordingControlProps {
  cameraId: string;
}

function formatSize(bytes: number | null): string {
  if (bytes === null) return '—';
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return 'in progress';
  return `${seconds.toFixed(0)}s`;
}

// Deliberately minimal (M6, docs/IMPLEMENTATION_PLAN.md §M6's Milestone
// Boundary note): start/stop control and a plain list, sufficient for AC #2
// ("recording metadata is queryable... immediately after stopping") — no
// player/seek, which is M7's (Playback) job.
function RecordingControl({ cameraId }: RecordingControlProps) {
  const { recordings, isLoading, isRecording, isStarting, isStopping, error, start, stop } =
    useRecording(cameraId);

  return (
    <div className="space-y-2 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <span
            className={`h-2.5 w-2.5 rounded-full ${isRecording ? 'bg-red-500' : 'bg-slate-300'}`}
          />
          <span>{isRecording ? 'Recording' : 'Not recording'}</span>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={start}
            disabled={isStarting || isRecording}
            className="rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
          >
            Start
          </button>
          <button
            type="button"
            onClick={stop}
            disabled={isStopping || !isRecording}
            className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 disabled:opacity-50"
          >
            Stop
          </button>
        </div>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      {isLoading ? (
        <p className="text-sm text-slate-400">Loading recordings…</p>
      ) : recordings.length === 0 ? (
        <p className="text-sm text-slate-400">No recordings yet.</p>
      ) : (
        <ul className="divide-y divide-slate-200 text-sm text-slate-600">
          {recordings.map((recording) => (
            <li key={recording.id} className="flex items-center justify-between py-1.5">
              <span className="truncate">{recording.file_path.split('/').pop()}</span>
              <span className="ml-2 shrink-0 text-xs text-slate-400">
                {formatDuration(recording.duration_seconds)} · {formatSize(recording.size_bytes)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default RecordingControl;
