import { useMutation, useQueryClient } from '@tanstack/react-query';
import { type MouseEvent, useEffect, useState } from 'react';
import { mjpegStreamUrl, startStream } from '../../services/streamsApi';
import { createZone, deleteZone, updateZone } from '../../services/zonesApi';
import type { ZonePoint, ZoneResponse, ZoneUpdateRequest } from '../../types/zone';
import useZones from '../../hooks/useZones';

interface ZoneEditorProps {
  cameraId: string;
}

/**
 * Draws a loitering-detection zone polygon over the live MJPEG view and
 * persists it via `POST /zones` (T-112).
 *
 * Reuses the existing `/streams/{cameraId}/mjpeg` `<img>` as the drawing
 * backdrop — the same visual surface `LiveView`/`DetectionOverlay` already
 * render against — rather than adding a new "capture a still frame"
 * endpoint; the only new backend surface this milestone needs is `/zones`
 * itself (docs/TECHNICAL_DECISIONS.md TD-28).
 *
 * Coordinate-space reconciliation (the mismatch noted in
 * docs/IMPLEMENTATION_PLAN.md §M11's Deliverables): clicked points are
 * captured as normalized `[0, 1]` fractions of the image element's own
 * rendered box (`event.clientX/Y` minus the element's `getBoundingClientRect()`,
 * divided by its width/height) — the same space `BoundingBox` already uses —
 * so no conversion is needed on the backend; normalization happens here, on
 * save, entirely on the frontend. The overlay SVG uses `viewBox="0 0 1 1"`
 * with `preserveAspectRatio="none"`, so it always maps 1:1 onto that same
 * rendered box regardless of the image's actual pixel size.
 *
 * M14 addition: an optional missing-object threshold field (the backend's
 * `ZoneCreateRequest`/`ZoneResponse` supported `missing_object_threshold_seconds`
 * since M12, but this editor never surfaced it — a gap found during
 * docs/UI_UX_DESIGN.md's Phase 2 review, §6.5) plus in-place editing of an
 * existing zone's fields via `PATCH /zones/{id}` (previously create+delete only).
 */
function ZoneEditor({ cameraId }: ZoneEditorProps) {
  const queryClient = useQueryClient();
  const { data: zones } = useZones(cameraId);
  const [points, setPoints] = useState<ZonePoint[]>([]);
  const [name, setName] = useState('');
  const [dwellThresholdSeconds, setDwellThresholdSeconds] = useState(5);
  const [missingObjectThresholdSeconds, setMissingObjectThresholdSeconds] = useState('');
  const [editingZoneId, setEditingZoneId] = useState<string | null>(null);
  const [editState, setEditState] = useState<{
    name: string;
    dwellThresholdSeconds: string;
    missingObjectThresholdSeconds: string;
  } | null>(null);

  useEffect(() => {
    startStream(cameraId).catch(() => {
      // Best-effort, mirroring DetectionOverlay's `enableAnalytics` call —
      // the stream may already be running, or this source may not be
      // startable yet; the editor simply has no backdrop image either way.
    });
  }, [cameraId]);

  const createZoneMutation = useMutation({
    mutationFn: createZone,
    onSuccess: () => {
      setPoints([]);
      setName('');
      setMissingObjectThresholdSeconds('');
      queryClient.invalidateQueries({ queryKey: ['zones', cameraId] });
    },
  });

  const updateZoneMutation = useMutation({
    mutationFn: ({ zoneId, payload }: { zoneId: string; payload: ZoneUpdateRequest }) =>
      updateZone(zoneId, payload),
    onSuccess: () => {
      setEditingZoneId(null);
      setEditState(null);
      queryClient.invalidateQueries({ queryKey: ['zones', cameraId] });
    },
  });

  const deleteZoneMutation = useMutation({
    mutationFn: deleteZone,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['zones', cameraId] }),
  });

  function startEditing(zone: ZoneResponse) {
    setEditingZoneId(zone.id);
    setEditState({
      name: zone.name,
      dwellThresholdSeconds: String(zone.dwell_threshold_seconds),
      missingObjectThresholdSeconds:
        zone.missing_object_threshold_seconds != null
          ? String(zone.missing_object_threshold_seconds)
          : '',
    });
  }

  function saveEditing(zoneId: string) {
    if (!editState) return;
    updateZoneMutation.mutate({
      zoneId,
      payload: {
        name: editState.name.trim(),
        dwell_threshold_seconds: Number(editState.dwellThresholdSeconds),
        missing_object_threshold_seconds: editState.missingObjectThresholdSeconds
          ? Number(editState.missingObjectThresholdSeconds)
          : null,
      },
    });
  }

  function handleOverlayClick(event: MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1);
    const y = Math.min(Math.max((event.clientY - rect.top) / rect.height, 0), 1);
    setPoints((previous) => [...previous, [x, y]]);
  }

  function handleSave() {
    if (points.length < 3 || !name.trim()) return;
    createZoneMutation.mutate({
      camera_id: cameraId,
      name: name.trim(),
      polygon: points,
      dwell_threshold_seconds: dwellThresholdSeconds,
      missing_object_threshold_seconds: missingObjectThresholdSeconds
        ? Number(missingObjectThresholdSeconds)
        : null,
    });
  }

  const polygonAttr = points.map(([x, y]) => `${x},${y}`).join(' ');

  return (
    <div className="space-y-3 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="relative">
        <img
          src={mjpegStreamUrl(cameraId)}
          alt="Camera view for drawing a loitering zone"
          className="w-full rounded"
        />
        <svg
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          onClick={handleOverlayClick}
          className="absolute inset-0 h-full w-full cursor-crosshair"
        >
          {zones?.map((zone) => (
            <polygon
              key={zone.id}
              points={zone.polygon.map(([x, y]) => `${x},${y}`).join(' ')}
              fill="rgba(56, 189, 248, 0.15)"
              stroke="rgb(56, 189, 248)"
              strokeWidth={0.003}
            />
          ))}
          {points.length > 0 && (
            <polygon
              points={polygonAttr}
              fill="rgba(16, 185, 129, 0.2)"
              stroke="rgb(16, 185, 129)"
              strokeWidth={0.004}
            />
          )}
          {points.map(([x, y], index) => (
            <circle key={index} cx={x} cy={y} r={0.006} fill="rgb(16, 185, 129)" />
          ))}
        </svg>
      </div>

      <p className="text-xs text-slate-500">
        Click on the image to add polygon points ({points.length} placed, 3+ required).
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          Zone name
          <input
            className="rounded border border-slate-300 px-2 py-1"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          Dwell threshold (seconds)
          <input
            type="number"
            min={0.1}
            step={0.1}
            className="w-28 rounded border border-slate-300 px-2 py-1"
            value={dwellThresholdSeconds}
            onChange={(event) => setDwellThresholdSeconds(Number(event.target.value))}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          Missing-object threshold (seconds, optional)
          <input
            type="number"
            min={0.1}
            step={0.1}
            placeholder="Not monitored"
            className="w-40 rounded border border-slate-300 px-2 py-1"
            value={missingObjectThresholdSeconds}
            onChange={(event) => setMissingObjectThresholdSeconds(event.target.value)}
          />
        </label>
        <button
          type="button"
          onClick={() => setPoints([])}
          className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700"
        >
          Clear points
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={points.length < 3 || !name.trim() || createZoneMutation.isPending}
          className="rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
        >
          Save zone
        </button>
      </div>

      {zones && zones.length > 0 && (
        <ul className="space-y-2 text-sm text-slate-600">
          {zones.map((zone) =>
            editingZoneId === zone.id && editState ? (
              <li key={zone.id} className="flex flex-wrap items-end gap-2 rounded border border-slate-200 bg-white p-2">
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  Name
                  <input
                    className="rounded border border-slate-300 px-2 py-1 text-sm"
                    value={editState.name}
                    onChange={(event) => setEditState({ ...editState, name: event.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  Dwell (s)
                  <input
                    type="number"
                    min={0.1}
                    step={0.1}
                    className="w-24 rounded border border-slate-300 px-2 py-1 text-sm"
                    value={editState.dwellThresholdSeconds}
                    onChange={(event) =>
                      setEditState({ ...editState, dwellThresholdSeconds: event.target.value })
                    }
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  Missing-object (s)
                  <input
                    type="number"
                    min={0.1}
                    step={0.1}
                    placeholder="Not monitored"
                    className="w-32 rounded border border-slate-300 px-2 py-1 text-sm"
                    value={editState.missingObjectThresholdSeconds}
                    onChange={(event) =>
                      setEditState({
                        ...editState,
                        missingObjectThresholdSeconds: event.target.value,
                      })
                    }
                  />
                </label>
                <button
                  type="button"
                  onClick={() => saveEditing(zone.id)}
                  disabled={!editState.name.trim() || updateZoneMutation.isPending}
                  className="rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEditingZoneId(null);
                    setEditState(null);
                  }}
                  className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700"
                >
                  Cancel
                </button>
              </li>
            ) : (
              <li key={zone.id} className="flex items-center justify-between gap-2">
                <span>
                  {zone.name} — {zone.dwell_threshold_seconds}s dwell threshold
                  {' · '}
                  {zone.missing_object_threshold_seconds != null
                    ? `${zone.missing_object_threshold_seconds}s missing-object threshold`
                    : 'not monitored for missing objects'}
                </span>
                <span className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    onClick={() => startEditing(zone)}
                    className="text-xs text-slate-600 hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteZoneMutation.mutate(zone.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </span>
              </li>
            ),
          )}
        </ul>
      )}
    </div>
  );
}

export default ZoneEditor;
