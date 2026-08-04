import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { listCameras } from '../../services/camerasApi';
import LiveView from './LiveView';

// Fetches its own camera list via `services/` (shared) rather than importing
// `camera-onboarding/` directly — FOLDER_STRUCTURE.md: "Features do not
// import from each other." A single combined dashboard is M14's job.
function LiveViewPage() {
  const { data, isLoading, isError } = useQuery({ queryKey: ['cameras'], queryFn: listCameras });
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);

  if (isLoading) return <p className="text-sm text-slate-500">Loading cameras…</p>;
  if (isError) return <p className="text-sm text-red-600">Failed to load cameras.</p>;
  if (!data || data.length === 0) {
    return <p className="text-sm text-slate-500">No cameras onboarded yet.</p>;
  }

  const selected = data.find((camera) => camera.id === selectedCameraId) ?? data[0];

  return (
    <div className="space-y-3">
      <label className="flex flex-col gap-1 text-sm text-slate-600">
        Camera
        <select
          className="rounded border border-slate-300 px-2 py-1"
          value={selected.id}
          onChange={(event) => setSelectedCameraId(event.target.value)}
        >
          {data.map((camera) => (
            <option key={camera.id} value={camera.id}>
              {camera.name}
            </option>
          ))}
        </select>
      </label>
      <LiveView cameraId={selected.id} cameraName={selected.name} />
    </div>
  );
}

export default LiveViewPage;
