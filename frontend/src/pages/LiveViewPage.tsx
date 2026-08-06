import { useEffect } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import AnalyticsToggle from '../components/AnalyticsToggle';
import CameraPicker from '../components/CameraPicker';
import LiveView from '../components/LiveView';
import Panel from '../components/Panel';
import DetectionOverlay from '../features/analytics-console/DetectionOverlay';
import RecordingControl from '../features/recordings/RecordingControl';
import useAnalyticsStatus from '../hooks/useAnalyticsStatus';
import useCameras from '../hooks/useCameras';
import useUiStore from '../store/uiStore';
import type { CameraResponse } from '../types/camera';

/**
 * `/live` and `/live/:cameraId` (docs/UI_UX_DESIGN.md §6.6) — the
 * operational hub: live MJPEG view, an explicit analytics on/off toggle
 * (new — DetectionOverlay used to enable analytics unconditionally with no
 * way to turn it back off), and recording start/stop, composed exactly as
 * they were grouped in the pre-M14 `App.tsx`'s "Camera Monitor" section.
 */
function LiveViewPage() {
  const { cameraId } = useParams<{ cameraId: string }>();
  const { data: cameras, isLoading, isError } = useCameras();
  const lastViewedCameraId = useUiStore((state) => state.lastViewedCameraId);

  if (isLoading) return <p className="text-sm text-slate-500">Loading cameras…</p>;
  if (isError) return <p className="text-sm text-red-600">Failed to load cameras.</p>;
  if (!cameras || cameras.length === 0) {
    return (
      <Panel title="Live View">
        <p className="text-sm text-slate-500">
          No cameras onboarded yet.{' '}
          <Link to="/cameras" className="text-slate-700 underline">
            Add one
          </Link>
          .
        </p>
      </Panel>
    );
  }

  if (!cameraId) {
    const fallback = cameras.find((camera) => camera.id === lastViewedCameraId) ?? cameras[0];
    return <Navigate to={`/live/${fallback.id}`} replace />;
  }

  const selected = cameras.find((camera) => camera.id === cameraId);
  if (!selected) {
    return <p className="text-sm text-red-600">Unknown camera.</p>;
  }

  return <LiveViewSelected cameras={cameras} selected={selected} />;
}

function LiveViewSelected({
  cameras,
  selected,
}: {
  cameras: CameraResponse[];
  selected: CameraResponse;
}) {
  const navigate = useNavigate();
  const setLastViewedCameraId = useUiStore((state) => state.setLastViewedCameraId);
  const analytics = useAnalyticsStatus(selected.id);

  useEffect(() => {
    setLastViewedCameraId(selected.id);
  }, [selected.id, setLastViewedCameraId]);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <CameraPicker cameras={cameras} value={selected.id} onChange={(id) => navigate(`/live/${id}`)} />

      <Panel title={selected.name} actions={<AnalyticsToggle sourceId={selected.id} />}>
        <div className="space-y-3">
          <LiveView
            cameraId={selected.id}
            cameraName={selected.name}
            overlay={analytics.enabled ? <DetectionOverlay cameraId={selected.id} /> : undefined}
          />
          <RecordingControl cameraId={selected.id} />
        </div>
      </Panel>
    </div>
  );
}

export default LiveViewPage;
