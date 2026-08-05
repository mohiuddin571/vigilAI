import { useEffect, useRef, useState } from 'react';
import { analyticsEventsWebSocketUrl, enableAnalytics } from '../../services/analyticsApi';
import type { DetectionEventResponse } from '../../types/analytics';

interface DetectionOverlayProps {
  cameraId: string;
}

/**
 * Renders YOLO detection boxes/labels over a live view (T-093).
 *
 * Rendered as a slot passed into `live-view/LiveView.tsx` from `App.tsx`
 * rather than imported by LiveView directly — `features/` never import each
 * other (docs/FOLDER_STRUCTURE.md). `BoundingBox` is already normalized to
 * `[0, 1]`, so boxes are positioned with plain percentages against this
 * component's `inset-0` parent (the same relative wrapper LiveView renders
 * its `<img>` in) — no pixel/DOM-measurement math needed.
 *
 * `/ws/analytics/events` is one global channel (no per-source server-side
 * filtering yet — docs/TECHNICAL_DECISIONS.md TD-25); this component filters
 * client-side on `camera_id`. Events for one YOLO inference pass share the
 * same `metadata.frame_sequence` and are published back-to-back, in order,
 * by the single-threaded pipeline — so grouping by "did frame_sequence
 * change since the last event" reconstructs "this frame's full box set"
 * without the backend needing to batch them itself.
 */
function DetectionOverlay({ cameraId }: DetectionOverlayProps) {
  const [detections, setDetections] = useState<DetectionEventResponse[]>([]);
  const currentSequenceRef = useRef<number | null>(null);

  useEffect(() => {
    enableAnalytics(cameraId).catch(() => {
      // Best-effort: this source may not be analytics-enableable (yet), or
      // may already be enabled — the overlay simply stays empty either way.
    });
  }, [cameraId]);

  useEffect(() => {
    const socket = new WebSocket(analyticsEventsWebSocketUrl());
    socket.onmessage = (event: MessageEvent<string>) => {
      const detection = JSON.parse(event.data) as DetectionEventResponse;
      if (detection.camera_id !== cameraId || !detection.bounding_box) {
        return;
      }
      const sequence = detection.metadata.frame_sequence as number | undefined;
      setDetections((previous) => {
        if (sequence === undefined || sequence !== currentSequenceRef.current) {
          currentSequenceRef.current = sequence ?? null;
          return [detection];
        }
        return [...previous, detection];
      });
    };
    return () => socket.close();
  }, [cameraId]);

  return (
    <div className="pointer-events-none absolute inset-0">
      {detections.map((detection) => {
        const box = detection.bounding_box;
        if (!box) return null;
        const label = (detection.metadata.class_label as string | undefined) ?? detection.event_type;
        return (
          <div
            key={detection.id}
            className="absolute border-2 border-emerald-400"
            style={{
              left: `${box.x_min * 100}%`,
              top: `${box.y_min * 100}%`,
              width: `${(box.x_max - box.x_min) * 100}%`,
              height: `${(box.y_max - box.y_min) * 100}%`,
            }}
          >
            <span className="absolute -top-5 left-0 whitespace-nowrap rounded bg-emerald-500 px-1 text-[10px] font-medium text-white">
              {label} {(detection.confidence * 100).toFixed(0)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default DetectionOverlay;
