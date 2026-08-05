import { useMemo } from 'react';
import Panel from '../components/Panel';
import CameraGrid from '../features/dashboard/CameraGrid';
import RecentEvents from '../features/dashboard/RecentEvents';
import StatTiles from '../features/dashboard/StatTiles';
import useAnalyticsEvents from '../hooks/useAnalyticsEvents';
import useCameras from '../hooks/useCameras';
import useRecordingsList from '../hooks/useRecordingsList';

/**
 * `/` (docs/UI_UX_DESIGN.md §6.1) — the front door: system-state stat
 * tiles, a camera grid, and a recent-events preview. Every widget's own
 * fetch failure is shown in that widget's spot rather than blanking the
 * whole page (§5.7).
 */
function DashboardPage() {
  const last24hStart = useMemo(() => new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), []);

  const { data: cameras, isLoading: camerasLoading, isError: camerasError } = useCameras();
  const { data: recordings, isError: recordingsError } = useRecordingsList({});
  const {
    data: recentEvents,
    isError: eventsError,
  } = useAnalyticsEvents({ start: last24hStart });

  const camerasOnline = cameras?.filter((camera) => camera.is_online).length ?? 0;
  const activeRecordings = recordings?.filter((recording) => recording.ended_at === null).length ?? 0;
  const analyticsEnabledApprox = new Set((recentEvents ?? []).map((event) => event.camera_id)).size;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>

      {camerasError || recordingsError || eventsError ? (
        <p className="text-sm text-red-600">Some dashboard data failed to load.</p>
      ) : null}

      {!camerasLoading && cameras && (
        <StatTiles
          camerasOnline={camerasOnline}
          camerasTotal={cameras.length}
          activeRecordings={activeRecordings}
          eventsLast24h={recentEvents?.length ?? 0}
          analyticsEnabledApprox={analyticsEnabledApprox}
        />
      )}

      <Panel title="Cameras">
        {camerasLoading ? (
          <p className="text-sm text-slate-500">Loading cameras…</p>
        ) : (
          <CameraGrid cameras={cameras ?? []} />
        )}
      </Panel>

      <Panel title="Recent events">
        <RecentEvents events={recentEvents ?? []} cameras={cameras ?? []} />
      </Panel>
    </div>
  );
}

export default DashboardPage;
