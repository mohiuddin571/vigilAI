import { useEffect, useRef, useState } from 'react';
import { analyticsEventsWebSocketUrl } from '../../services/analyticsApi';
import type { DetectionEventResponse } from '../../types/analytics';

interface DetectionOverlayProps {
  cameraId: string;
}

/**
 * Renders YOLO detection boxes/labels over a live view (T-093).
 *
 * Rendered as a slot passed into `components/LiveView.tsx` from the
 * page/feature composing both, rather than imported by LiveView directly —
 * `features/` never import each other (docs/FOLDER_STRUCTURE.md).
 * `BoundingBox` is already normalized to
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
 *
 * `ColorDetector` (T-100/T-101) publishes its own `color_detection.*`
 * events alongside each frame's `object_detection.*` events rather than
 * mutating them (docs/TECHNICAL_DECISIONS.md TD-27) — one box is still
 * rendered per detected object; the color is merged into that box's label
 * by matching `color_detection.*` events back to their source detection via
 * `metadata.source_event_id`.
 *
 * Does *not* call `enableAnalytics` itself (M14 change) — Live View owns
 * that via an explicit toggle (`useAnalyticsStatus`, docs/UI_UX_DESIGN.md
 * §6.6) so the operator has a way to turn it back off, which an
 * unconditional enable-on-mount never allowed. Callers should only render
 * this component while analytics is known to be enabled for `cameraId`.
 */
function DetectionOverlay({ cameraId }: DetectionOverlayProps) {
  const [detections, setDetections] = useState<DetectionEventResponse[]>([]);
  const currentSequenceRef = useRef<number | null>(null);

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

  const objectDetections = detections.filter((detection) =>
    detection.event_type.startsWith('object_detection.'),
  );
  const colorLabelBySourceEventId = new Map<string, string>();
  for (const detection of detections) {
    if (!detection.event_type.startsWith('color_detection.')) continue;
    const sourceEventId = detection.metadata.source_event_id as string | undefined;
    const colorLabel = detection.metadata.color_label as string | undefined;
    if (sourceEventId && colorLabel) {
      colorLabelBySourceEventId.set(sourceEventId, colorLabel);
    }
  }

  return (
    <div className="pointer-events-none absolute inset-0">
      {objectDetections.map((detection) => {
        const box = detection.bounding_box;
        if (!box) return null;
        const classLabel =
          (detection.metadata.class_label as string | undefined) ?? detection.event_type;
        const colorLabel = colorLabelBySourceEventId.get(detection.id);
        const label = colorLabel ? `${colorLabel} ${classLabel}` : classLabel;
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
