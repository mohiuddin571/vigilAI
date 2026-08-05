import CameraPicker from '../../components/CameraPicker';
import { categoryLabel, type EventCategory } from '../../lib/eventCategory';
import type { CameraResponse } from '../../types/camera';

const CATEGORIES: EventCategory[] = [
  'object_detection',
  'color_detection',
  'loitering_detection',
  'missing_object_detection',
  'license_plate_recognition',
];

export interface EventFilterState {
  cameraId: string;
  start: string;
  end: string;
  category: EventCategory | '';
  plateSearch: string;
}

interface EventFiltersProps {
  cameras: CameraResponse[];
  value: EventFilterState;
  onChange: (value: EventFilterState) => void;
  live: boolean;
  onToggleLive: () => void;
}

/** Event Center's filter bar (docs/UI_UX_DESIGN.md §6.8). Camera + time range
 * are forwarded to `GET /analytics/events` server-side (§5.10); category and
 * plate-text search are client-side over the already-fetched/live-merged
 * result set — no matching backend capability exists for either. */
function EventFilters({ cameras, value, onChange, live, onToggleLive }: EventFiltersProps) {
  const set = (patch: Partial<EventFilterState>) => onChange({ ...value, ...patch });

  return (
    <div className="flex flex-wrap items-end gap-3">
      <CameraPicker
        cameras={cameras}
        value={value.cameraId}
        onChange={(cameraId) => set({ cameraId })}
        includeAllOption
      />
      <label className="flex flex-col gap-1 text-sm text-slate-600">
        From
        <input
          type="datetime-local"
          className="rounded border border-slate-300 px-2 py-1"
          value={value.start}
          onChange={(event) => set({ start: event.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-600">
        To
        <input
          type="datetime-local"
          className="rounded border border-slate-300 px-2 py-1"
          value={value.end}
          onChange={(event) => set({ end: event.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-600">
        Category
        <select
          className="rounded border border-slate-300 px-2 py-1"
          value={value.category}
          onChange={(event) => set({ category: event.target.value as EventCategory | '' })}
        >
          <option value="">All categories</option>
          {CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {categoryLabel(category)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm text-slate-600">
        Plate text
        <input
          className="rounded border border-slate-300 px-2 py-1"
          placeholder="Search recognized plates…"
          value={value.plateSearch}
          onChange={(event) => set({ plateSearch: event.target.value })}
        />
      </label>
      <button
        type="button"
        onClick={onToggleLive}
        className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
          live ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
        }`}
      >
        <span className={`h-1.5 w-1.5 rounded-full ${live ? 'bg-emerald-500' : 'bg-slate-400'}`} />
        {live ? 'Live' : 'Paused'}
      </button>
    </div>
  );
}

export default EventFilters;
