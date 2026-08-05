interface StatTilesProps {
  camerasOnline: number;
  camerasTotal: number;
  activeRecordings: number;
  eventsLast24h: number;
  analyticsEnabledApprox: number;
}

/** Dashboard stat tiles (docs/UI_UX_DESIGN.md §6.1) — every number here is
 * derived client-side from `GET /cameras`/`GET /recordings`/`GET
 * /analytics/events` (no dedicated stats endpoint exists). */
function StatTiles({
  camerasOnline,
  camerasTotal,
  activeRecordings,
  eventsLast24h,
  analyticsEnabledApprox,
}: StatTilesProps) {
  const tiles = [
    { label: 'Cameras online', value: `${camerasOnline}/${camerasTotal}` },
    { label: 'Recording now', value: String(activeRecordings) },
    { label: 'Analytics enabled (approx.)', value: String(analyticsEnabledApprox) },
    { label: 'Events (24h)', value: String(eventsLast24h) },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {tiles.map((tile) => (
        <div key={tile.label} className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-2xl font-semibold text-slate-900">{tile.value}</p>
          <p className="mt-1 text-xs text-slate-500">{tile.label}</p>
        </div>
      ))}
    </div>
  );
}

export default StatTiles;
