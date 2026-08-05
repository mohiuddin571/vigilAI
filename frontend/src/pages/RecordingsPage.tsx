import { useSearchParams } from 'react-router-dom';
import Panel from '../components/Panel';
import RecordingsBrowser from '../features/recordings/RecordingsBrowser';
import useCameras from '../hooks/useCameras';

/**
 * `/recordings` (docs/UI_UX_DESIGN.md §6.7). Reads `?camera=&start=&end=`
 * so Camera Detail's "View recordings" shortcut and Event Center's
 * "view around this time" link (§7 Flow D) can deep-link into a preset
 * filter — falls back to the existing unfiltered/all-cameras default when
 * absent, exactly as this screen already behaved before M14.
 */
function RecordingsPage() {
  const [searchParams] = useSearchParams();
  const { data: cameras, isLoading, isError } = useCameras();

  return (
    <div className="mx-auto max-w-3xl">
      <Panel
        title="Recordings"
        description="Browse and play back recorded footage, filterable by camera and time range."
      >
        {isLoading && <p className="text-sm text-slate-500">Loading cameras…</p>}
        {isError && <p className="text-sm text-red-600">Failed to load cameras.</p>}
        {cameras && (
          <RecordingsBrowser
            cameras={cameras}
            initialCameraId={searchParams.get('camera') ?? undefined}
            initialStartIso={searchParams.get('start') ?? undefined}
            initialEndIso={searchParams.get('end') ?? undefined}
          />
        )}
      </Panel>
    </div>
  );
}

export default RecordingsPage;
