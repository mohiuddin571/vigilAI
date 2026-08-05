import { useState } from 'react';
import Dialog from '../components/Dialog';
import Panel from '../components/Panel';
import AddCameraForm from '../features/camera-onboarding/AddCameraForm';
import CameraList from '../features/camera-onboarding/CameraList';

/**
 * `/cameras` (docs/UI_UX_DESIGN.md §6.2). Composes the existing
 * `camera-onboarding` feature's form + list; "Add Camera" moves from the
 * always-open inline form the pre-M14 `App.tsx` used to a dismissible
 * dialog (§5.4), since this screen now has to share the viewport with a
 * search box instead of owning the whole page.
 */
function CameraListPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [nameFilter, setNameFilter] = useState('');

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Panel
        title="Cameras"
        description="Onboarded ONVIF cameras — click one to view, configure, or manage its zones."
        actions={
          <button
            type="button"
            onClick={() => setDialogOpen(true)}
            className="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white"
          >
            Add camera
          </button>
        }
      >
        <input
          className="mb-4 w-full rounded border border-slate-300 px-3 py-1.5 text-sm"
          placeholder="Search by name or IP…"
          value={nameFilter}
          onChange={(event) => setNameFilter(event.target.value)}
        />
        <CameraList nameFilter={nameFilter} />
      </Panel>

      {dialogOpen && (
        <Dialog title="Add camera" onClose={() => setDialogOpen(false)}>
          <AddCameraForm onSuccess={() => setDialogOpen(false)} />
        </Dialog>
      )}
    </div>
  );
}

export default CameraListPage;
