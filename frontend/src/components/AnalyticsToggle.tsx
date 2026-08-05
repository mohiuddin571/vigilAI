import useAnalyticsStatus from '../hooks/useAnalyticsStatus';

interface AnalyticsToggleProps {
  sourceId: string;
  label?: string;
  size?: 'sm' | 'md';
}

/**
 * Real per-camera analytics on/off, backed by the existing
 * `GET/POST /analytics/{id}/{status,enable,disable}` endpoints (no new
 * backend). Extracted into `components/` (shared, feature-agnostic —
 * `docs/FOLDER_STRUCTURE.md`) once Live View and the Dashboard both needed
 * it: previously the Dashboard's only signal was an approximate, read-only
 * derived count with no way to see *which* cameras or act on it — a real
 * design gap (docs/UI_UX_DESIGN.md §6.1's note), fixed here without adding
 * any new API surface.
 */
function AnalyticsToggle({ sourceId, label = 'Analytics', size = 'md' }: AnalyticsToggleProps) {
  const analytics = useAnalyticsStatus(sourceId);
  const track = size === 'sm' ? 'h-4 w-7' : 'h-5 w-9';
  const knob = size === 'sm' ? 'h-3 w-3 translate-y-0.5' : 'h-4 w-4 translate-y-0.5';
  const knobOn = size === 'sm' ? 'translate-x-3.5' : 'translate-x-4';
  const knobOff = size === 'sm' ? 'translate-x-0.5' : 'translate-x-0.5';

  return (
    <label className={`flex items-center gap-2 ${size === 'sm' ? 'text-xs' : 'text-sm'} text-slate-600`}>
      {label}
      <button
        type="button"
        role="switch"
        aria-checked={analytics.enabled}
        disabled={analytics.isLoading || analytics.isToggling}
        onClick={(event) => {
          event.preventDefault();
          if (analytics.enabled) {
            analytics.disable();
          } else {
            analytics.enable();
          }
        }}
        className={`${track} rounded-full transition-colors ${
          analytics.enabled ? 'bg-emerald-500' : 'bg-slate-300'
        } disabled:opacity-50`}
      >
        <span
          className={`block ${knob} rounded-full bg-white transition-transform ${
            analytics.enabled ? knobOn : knobOff
          }`}
        />
      </button>
    </label>
  );
}

export default AnalyticsToggle;
