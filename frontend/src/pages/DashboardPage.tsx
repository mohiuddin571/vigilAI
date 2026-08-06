import { useState } from 'react';
import Dialog from '../components/Dialog';
import Panel from '../components/Panel';
import AddCameraForm from '../features/camera-onboarding/AddCameraForm';
import CameraGrid from '../features/dashboard/CameraGrid';
import useCameras from '../hooks/useCameras';

/**
 * `/` (docs/UI_UX_DESIGN.md §6.1) — the front door: just the camera grid.
 * "Add Camera" reuses the same dialog + form as `CameraListPage`.
 */
function DashboardPage() {
  const [addCameraOpen, setAddCameraOpen] = useState(false);

  const { data: cameras, isLoading: camerasLoading, isError: camerasError } = useCameras();

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Cameras</h1>

      {camerasError ? <p className="text-sm text-red-600">Failed to load cameras.</p> : null}

      <Panel
        title="Cameras"
        actions={
          <button
            type="button"
            onClick={() => setAddCameraOpen(true)}
            className="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white"
          >
            Add camera
          </button>
        }
      >
        {camerasLoading ? (
          <p className="text-sm text-slate-500">Loading cameras…</p>
        ) : (
          <CameraGrid cameras={cameras ?? []} />
        )}
      </Panel>

      {addCameraOpen && (
        <Dialog title="Add camera" onClose={() => setAddCameraOpen(false)}>
          <AddCameraForm onSuccess={() => setAddCameraOpen(false)} />
        </Dialog>
      )}
    </div>
  );
}

export default DashboardPage;
