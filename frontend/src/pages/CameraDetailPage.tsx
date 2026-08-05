import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, NavLink, Outlet, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import ConfirmDialog from '../components/ConfirmDialog';
import Dialog from '../components/Dialog';
import Panel from '../components/Panel';
import ZoneEditor from '../features/analytics-console/ZoneEditor';
import ConfigPanel from '../features/camera-onboarding/ConfigPanel';
import EditCameraForm from '../features/camera-onboarding/EditCameraForm';
import useCamera from '../hooks/useCamera';
import { ApiError, deleteCamera } from '../services/camerasApi';
import type { CameraResponse } from '../types/camera';

const tabLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-3 py-1.5 text-sm font-medium ${
    isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
  }`;

/**
 * `/cameras/:cameraId` layout route (docs/UI_UX_DESIGN.md §6.3–§6.5) — a
 * tabbed shell (Overview / Configuration / Zones) around the existing
 * per-feature components. Fetches the camera once here and hands it to the
 * active tab via `useOutletContext`, since `ConfigPanel`/`ZoneEditor` live in
 * different `features/` folders that must not import each other directly
 * (docs/FOLDER_STRUCTURE.md) — this page is the composition point, the same
 * role the pre-M14 `App.tsx` played for `LiveView`'s `overlay` slot.
 */
function CameraDetailPage() {
  const { cameraId } = useParams<{ cameraId: string }>();
  const { data: camera, isLoading, isError } = useCamera(cameraId);

  if (isLoading) return <p className="text-sm text-slate-500">Loading camera…</p>;
  if (isError || !camera) {
    return <p className="text-sm text-red-600">Failed to load this camera.</p>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <Link to="/cameras" className="text-sm text-slate-500 hover:underline">
          ← Cameras
        </Link>
        <h1 className="mt-1 text-2xl font-semibold text-slate-900">{camera.name}</h1>
      </div>

      <nav className="flex gap-2 border-b border-slate-200 pb-2">
        <NavLink to={`/cameras/${camera.id}`} end className={tabLinkClass}>
          Overview
        </NavLink>
        <NavLink to={`/cameras/${camera.id}/config`} className={tabLinkClass}>
          Configuration
        </NavLink>
        <NavLink to={`/cameras/${camera.id}/zones`} className={tabLinkClass}>
          Zones
        </NavLink>
      </nav>

      <Outlet context={camera} />
    </div>
  );
}

function useCameraContext(): CameraResponse {
  return useOutletContext<CameraResponse>();
}

export function CameraOverviewTab() {
  const camera = useCameraContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const deleteMutation = useMutation({
    mutationFn: () => deleteCamera(camera.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['cameras'] });
      navigate('/cameras');
    },
  });

  return (
    <Panel
      title="Overview"
      actions={
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            className="rounded border border-red-300 px-3 py-1.5 text-sm font-medium text-red-600"
          >
            Delete
          </button>
        </div>
      }
    >
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-slate-500">Status</dt>
        <dd className="text-slate-900">{camera.is_online ? 'Online' : 'Offline'}</dd>
        <dt className="text-slate-500">Address</dt>
        <dd className="text-slate-900">
          {camera.ip_address}:{camera.port}
        </dd>
        <dt className="text-slate-500">Manufacturer / model</dt>
        <dd className="text-slate-900">
          {camera.manufacturer ?? 'Unknown'} {camera.model ?? ''}
        </dd>
        <dt className="text-slate-500">Firmware</dt>
        <dd className="text-slate-900">{camera.firmware_version ?? 'Unknown'}</dd>
        <dt className="text-slate-500">Username</dt>
        <dd className="text-slate-900">{camera.username}</dd>
      </dl>

      <h3 className="mt-4 text-sm font-medium text-slate-700">Stream profiles</h3>
      <ul className="mt-1 space-y-1 text-xs text-slate-500">
        {camera.stream_profiles.map((profile) => (
          <li key={profile.id}>
            {profile.name}: {profile.resolution} @ {profile.fps}fps, {profile.bitrate_kbps}kbps (
            {profile.codec}){profile.is_primary ? ' — primary' : ''}
          </li>
        ))}
      </ul>

      <div className="mt-4 flex gap-3">
        <Link
          to={`/live/${camera.id}`}
          className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
        >
          View live
        </Link>
        <Link
          to={`/recordings?camera=${camera.id}`}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700"
        >
          View recordings
        </Link>
      </div>

      {editing && (
        <Dialog title={`Edit ${camera.name}`} onClose={() => setEditing(false)}>
          <EditCameraForm camera={camera} onSuccess={() => setEditing(false)} />
        </Dialog>
      )}

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
    </Panel>
  );
}

export function CameraConfigTab() {
  const camera = useCameraContext();
  const profilesWithToken = camera.stream_profiles.filter((profile) => profile.onvif_token);
  const [profileId, setProfileId] = useState(
    profilesWithToken.find((profile) => profile.is_primary)?.onvif_token ??
      profilesWithToken[0]?.onvif_token ??
      '',
  );

  if (profilesWithToken.length === 0) {
    return (
      <Panel title="Configuration">
        <p className="text-sm text-slate-500">
          This camera reported no ONVIF-configurable stream profiles.
        </p>
      </Panel>
    );
  }

  return (
    <Panel title="Configuration">
      {profilesWithToken.length > 1 && (
        <label className="mb-3 flex flex-col gap-1 text-sm text-slate-600">
          Profile
          <select
            className="w-full rounded border border-slate-300 px-2 py-1"
            value={profileId}
            onChange={(event) => setProfileId(event.target.value)}
          >
            {profilesWithToken.map((profile) => (
              <option key={profile.id} value={profile.onvif_token ?? ''}>
                {profile.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <ConfigPanel cameraId={camera.id} profileId={profileId} />
    </Panel>
  );
}

export function CameraZonesTab() {
  const camera = useCameraContext();
  return (
    <Panel
      title="Zones"
      description="Draw a zone on the camera view. A loitering event fires once an object dwells inside it past the configured threshold; an optional missing-object threshold flags a baseline-registered object's absence."
    >
      <ZoneEditor cameraId={camera.id} />
    </Panel>
  );
}

export default CameraDetailPage;
