import { Fragment, useState } from 'react';
import { Link } from 'react-router-dom';
import { categorizeEvent, categoryLabel, describeEvent } from '../../lib/eventCategory';
import type { CameraResponse } from '../../types/camera';
import type { DetectionEventResponse } from '../../types/analytics';

interface EventTableProps {
  events: DetectionEventResponse[];
  cameras: CameraResponse[];
}

const WINDOW_SECONDS = 30;

function recordingsDeepLink(event: DetectionEventResponse): string {
  const occurred = new Date(event.occurred_at).getTime();
  const start = new Date(occurred - WINDOW_SECONDS * 1000).toISOString();
  const end = new Date(occurred + WINDOW_SECONDS * 1000).toISOString();
  const params = new URLSearchParams({ camera: event.camera_id, start, end });
  return `/recordings?${params.toString()}`;
}

/** Event Center's main table (docs/UI_UX_DESIGN.md §6.8) — client-side
 * paginated per §5.11 (no backend `limit`/`offset` on `GET
 * /analytics/events`), row click expands full metadata + a deep link into
 * Recordings around that timestamp. */
function EventTable({ events, cameras }: EventTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(25);
  const cameraName = (id: string) => cameras.find((camera) => camera.id === id)?.name ?? id;
  const visible = events.slice(0, visibleCount);

  if (events.length === 0) {
    return <p className="text-sm text-slate-500">No events match these filters.</p>;
  }

  return (
    <div className="space-y-2">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
            <th className="py-2 pr-2">Time</th>
            <th className="py-2 pr-2">Camera</th>
            <th className="py-2 pr-2">Category</th>
            <th className="py-2 pr-2">Detail</th>
            <th className="py-2 pr-2">Confidence</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {visible.map((event) => {
            const isExpanded = expandedId === event.id;
            return (
              <Fragment key={event.id}>
                <tr
                  className="cursor-pointer hover:bg-slate-50"
                  onClick={() => setExpandedId(isExpanded ? null : event.id)}
                >
                  <td className="py-2 pr-2 text-slate-500">
                    {new Date(event.occurred_at).toLocaleString()}
                  </td>
                  <td className="py-2 pr-2 text-slate-700">{cameraName(event.camera_id)}</td>
                  <td className="py-2 pr-2">
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">
                      {categoryLabel(categorizeEvent(event.event_type))}
                    </span>
                  </td>
                  <td className="py-2 pr-2 text-slate-700">{describeEvent(event)}</td>
                  <td className="py-2 pr-2 text-slate-500">{(event.confidence * 100).toFixed(0)}%</td>
                </tr>
                {isExpanded && (
                  <tr className="bg-slate-50">
                    <td colSpan={5} className="px-2 py-3 text-xs text-slate-600">
                      <pre className="overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(event.metadata, null, 2)}
                      </pre>
                      <Link
                        to={recordingsDeepLink(event)}
                        className="mt-2 inline-block text-slate-700 underline"
                      >
                        View around this time in Recordings →
                      </Link>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>

      {visibleCount < events.length && (
        <button
          type="button"
          onClick={() => setVisibleCount((count) => count + 25)}
          className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700"
        >
          Load more ({events.length - visibleCount} remaining)
        </button>
      )}
    </div>
  );
}

export default EventTable;
