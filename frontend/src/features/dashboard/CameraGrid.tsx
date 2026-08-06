import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import ConfirmDialog from '../../components/ConfirmDialog';
import LiveView from '../../components/LiveView';
import { ApiError, deleteCamera } from '../../services/camerasApi';
import type { CameraResponse } from '../../types/camera';

interface CameraGridProps {
  cameras: CameraResponse[];
}

/** Dashboard camera tiles (docs/UI_UX_DESIGN.md §6.1) — each tile auto-connects
 * its own `LiveView` (`autoStart`, `compact` icon controls) and disconnects on
 * unmount, so leaving the Dashboard stops every stream it started rather than
 * leaking Stream Workers. This intentionally starts one MJPEG stream per
 * onboarded camera whenever the Dashboard is open — see §6.1's note on the
 * resource tradeoff. Analytics enable/disable and per-type event-capture
 * settings live on Camera Detail's Settings tab (`CameraSettingsTab`), not
 * here — removed from this tile per explicit user direction. */
function CameraGrid({ cameras }: CameraGridProps) {
  if (cameras.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No cameras onboarded yet.{' '}
        <Link to="/cameras" className="text-slate-700 underline">
          Add your first camera
        </Link>
        .
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {cameras.map((camera) => (
        <CameraTile key={camera.id} camera={camera} />
      ))}
    </div>
  );
}

function CameraTile({ camera }: { camera: CameraResponse }) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => deleteCamera(camera.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['cameras'] });
      setConfirmingDelete(false);
    },
  });

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium text-slate-900">{camera.name}</span>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${camera.is_online ? 'bg-emerald-500' : 'bg-slate-300'}`}
            title={camera.is_online ? 'Online' : 'Offline'}
          />
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            aria-label={`Delete ${camera.name}`}
            title="Delete camera"
            className="text-slate-400 hover:text-red-600"
          >
            <TrashIcon />
          </button>
        </div>
      </div>
      <p className="text-xs text-slate-500">
        {camera.manufacturer ?? 'Unknown manufacturer'} {camera.model ?? ''}
      </p>

      <div className="mt-3">
        <LiveView cameraId={camera.id} cameraName={camera.name} autoStart compact />
      </div>

      <div className="mt-3">
        <Link to={`/cameras/${camera.id}`} className="text-sm text-slate-700 underline">
          Configure
        </Link>
      </div>

      {confirmingDelete && (
        <ConfirmDialog
          title="Delete camera"
          message={`Delete "${camera.name}"? This also permanently deletes its recordings (files and metadata), zones, and analytics events. This cannot be undone.`}
          isPending={deleteMutation.isPending}
          error={
            deleteMutation.error instanceof ApiError
              ? deleteMutation.error.message
              : deleteMutation.isError
                ? 'Failed to delete camera.'
                : null
          }
          onConfirm={() => deleteMutation.mutate()}
          onCancel={() => setConfirmingDelete(false)}
        />
      )}
    </div>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
      <path d="M3 4.5h10M6.5 4.5v-1a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1M4.5 4.5l.5 8a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1l.5-8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default CameraGrid;
