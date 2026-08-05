import { useMemo, useState } from 'react';
import Panel from '../components/Panel';
import EventFilters, { type EventFilterState } from '../features/event-center/EventFilters';
import EventTable from '../features/event-center/EventTable';
import useAnalyticsEvents from '../hooks/useAnalyticsEvents';
import useAnalyticsEventsFeed from '../hooks/useAnalyticsEventsFeed';
import useCameras from '../hooks/useCameras';
import { categorizeEvent } from '../lib/eventCategory';
import type { DetectionEventResponse } from '../types/analytics';

/** `datetime-local` input value -> ISO 8601, or undefined if empty. */
function toIsoOrUndefined(localDateTime: string): string | undefined {
  if (!localDateTime) return undefined;
  const date = new Date(localDateTime);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

/**
 * Defaults the "From" filter to one hour ago rather than leaving it empty.
 * `GET /analytics/events` has no server-side pagination (docs/UI_UX_DESIGN.md
 * §5.11/§11) — an unfiltered load pulls the *entire* historical event table,
 * confirmed against this project's own real demo camera during M14's manual
 * walkthrough (six figures of accumulated events). A sane recent-window
 * default keeps the common case fast; the filter bar still lets an operator
 * widen or clear the range explicitly.
 */
function defaultStartLocalDateTime(): string {
  const date = new Date(Date.now() - 60 * 60 * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function initialFilters(): EventFilterState {
  return { cameraId: '', start: defaultStartLocalDateTime(), end: '', category: '', plateSearch: '' };
}

/**
 * `/events` (docs/UI_UX_DESIGN.md §6.8) — the console tying M9–M13's
 * detectors together into one filterable, live-updating feed. Historical
 * events come from `GET /analytics/events` (server-filtered by camera/time,
 * §5.10); the "Live" pill merges in new events from `/ws/analytics/events`
 * as they arrive, deduped by id.
 */
function EventsPage() {
  const [filters, setFilters] = useState(initialFilters);
  const [live, setLive] = useState(true);

  const { data: cameras } = useCameras();
  const { data: historicalEvents, isLoading, isError } = useAnalyticsEvents({
    cameraId: filters.cameraId || undefined,
    start: toIsoOrUndefined(filters.start),
    end: toIsoOrUndefined(filters.end),
  });
  const liveEvents = useAnalyticsEventsFeed(live);

  const merged = useMemo(() => {
    const byId = new Map<string, DetectionEventResponse>();
    for (const event of historicalEvents ?? []) byId.set(event.id, event);
    for (const event of liveEvents) byId.set(event.id, event);
    return [...byId.values()].sort(
      (a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at),
    );
  }, [historicalEvents, liveEvents]);

  const filtered = useMemo(() => {
    const plateNeedle = filters.plateSearch.trim().toLowerCase();
    return merged.filter((event) => {
      if (filters.category && categorizeEvent(event.event_type) !== filters.category) return false;
      if (plateNeedle) {
        const plateText = String(event.metadata.plate_text ?? '').toLowerCase();
        if (!plateText.includes(plateNeedle)) return false;
      }
      return true;
    });
  }, [merged, filters.category, filters.plateSearch]);

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Panel
        title="Event Center"
        description="Every analytics finding across every camera — filterable, live-updating."
      >
        <div className="space-y-4">
          <EventFilters
            cameras={cameras ?? []}
            value={filters}
            onChange={setFilters}
            live={live}
            onToggleLive={() => setLive((current) => !current)}
          />

          {isLoading && <p className="text-sm text-slate-500">Loading events…</p>}
          {isError && <p className="text-sm text-red-600">Failed to load events.</p>}
          {!isLoading && !isError && <EventTable events={filtered} cameras={cameras ?? []} />}
        </div>
      </Panel>
    </div>
  );
}

export default EventsPage;
