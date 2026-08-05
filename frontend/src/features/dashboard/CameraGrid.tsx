import { Link } from 'react-router-dom';
import AnalyticsToggle from '../../components/AnalyticsToggle';
import type { CameraResponse } from '../../types/camera';

interface CameraGridProps {
  cameras: CameraResponse[];
}

/** Dashboard camera cards (docs/UI_UX_DESIGN.md §6.1) — no live thumbnail is
 * fetched here: starting an MJPEG stream is a stateful side effect on the
 * backend (`streams.py`'s `/mjpeg` handler calls `use_case.execute()`), so
 * the dashboard must not silently start every camera's stream just to
 * render a preview image. Each card's `AnalyticsToggle` shows the real,
 * per-camera enabled state — the Dashboard's stat tile above only ever
 * showed an approximate derived count with no way to see *which* cameras
 * or act on it (a real gap, not by design; see AnalyticsToggle's docstring). */
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
        <div key={camera.id} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <span className="font-medium text-slate-900">{camera.name}</span>
            <span
              className={`h-2.5 w-2.5 rounded-full ${camera.is_online ? 'bg-emerald-500' : 'bg-slate-300'}`}
              title={camera.is_online ? 'Online' : 'Offline'}
            />
          </div>
          <p className="text-xs text-slate-500">
            {camera.manufacturer ?? 'Unknown manufacturer'} {camera.model ?? ''}
          </p>
          <div className="mt-3 flex items-center justify-between">
            <div className="flex gap-3 text-sm">
              <Link to={`/live/${camera.id}`} className="text-slate-700 underline">
                View live
              </Link>
              <Link to={`/cameras/${camera.id}`} className="text-slate-700 underline">
                Configure
              </Link>
            </div>
            <AnalyticsToggle sourceId={camera.id} label="" size="sm" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default CameraGrid;
