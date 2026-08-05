import { Link } from 'react-router-dom';
import { categorizeEvent, categoryLabel, describeEvent } from '../../lib/eventCategory';
import type { CameraResponse } from '../../types/camera';
import type { DetectionEventResponse } from '../../types/analytics';

interface RecentEventsProps {
  events: DetectionEventResponse[];
  cameras: CameraResponse[];
}

/** Dashboard "recent events" widget (docs/UI_UX_DESIGN.md §6.1) — the last
 * ~8 events across all cameras, newest first, linking into Event Center. */
function RecentEvents({ events, cameras }: RecentEventsProps) {
  const cameraName = (id: string) => cameras.find((camera) => camera.id === id)?.name ?? id;
  const sorted = [...events]
    .sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at))
    .slice(0, 8);

  if (sorted.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No analytics events yet — enable analytics on a camera's{' '}
        <Link to="/live" className="text-slate-700 underline">
          Live View
        </Link>{' '}
        to start seeing events here.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-slate-200 text-sm">
      {sorted.map((event) => (
        <li key={event.id} className="flex items-center justify-between gap-2 py-2">
          <div className="min-w-0">
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">
              {categoryLabel(categorizeEvent(event.event_type))}
            </span>
            <span className="ml-2 truncate text-slate-700">{describeEvent(event)}</span>
          </div>
          <span className="shrink-0 text-xs text-slate-400">
            {cameraName(event.camera_id)} · {new Date(event.occurred_at).toLocaleTimeString()}
          </span>
        </li>
      ))}
      <li className="pt-2 text-right">
        <Link to="/events" className="text-xs text-slate-500 underline">
          View all events →
        </Link>
      </li>
    </ul>
  );
}

export default RecentEvents;
