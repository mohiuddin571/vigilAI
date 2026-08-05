import type { DetectionEventResponse } from '../types/analytics';

export type EventCategory =
  | 'object_detection'
  | 'color_detection'
  | 'loitering_detection'
  | 'missing_object_detection'
  | 'license_plate_recognition'
  | 'other';

const CATEGORY_LABELS: Record<EventCategory, string> = {
  object_detection: 'Detection',
  color_detection: 'Color',
  loitering_detection: 'Loitering',
  missing_object_detection: 'Missing Object',
  license_plate_recognition: 'License Plate',
  other: 'Other',
};

const KNOWN_CATEGORIES = new Set<EventCategory>([
  'object_detection',
  'color_detection',
  'loitering_detection',
  'missing_object_detection',
  'license_plate_recognition',
]);

/**
 * `event_type` is stored as `"{category}.{specific_value}"` by every
 * detector plugin (`yolo_detector.py`, `color_detector.py`,
 * `loitering_detector.py`, `missing_object_detector.py`,
 * `license_plate_recognizer.py`) — the repository's `event_type` filter is
 * an exact match, not a prefix (`event_repository.py:45`), so category-level
 * grouping/filtering happens here, client-side, on already-fetched events
 * (docs/UI_UX_DESIGN.md §5.10). Shared by the Dashboard and Event Center —
 * lives outside `features/` since both consume it and `features/` may not
 * import each other (docs/FOLDER_STRUCTURE.md).
 */
export function categorizeEvent(eventType: string): EventCategory {
  const prefix = eventType.split('.')[0] as EventCategory;
  return KNOWN_CATEGORIES.has(prefix) ? prefix : 'other';
}

export function categoryLabel(category: EventCategory): string {
  return CATEGORY_LABELS[category];
}

/** One-line human-readable detail for an event row, grounded in each
 * detector's actual `metadata` shape (see docs/UI_UX_DESIGN.md §6.8). */
export function describeEvent(event: DetectionEventResponse): string {
  const metadata = event.metadata;
  switch (categorizeEvent(event.event_type)) {
    case 'object_detection':
      return String(metadata.class_label ?? event.event_type);
    case 'color_detection':
      return `${metadata.color_label ?? '?'} ${metadata.class_label ?? ''}`.trim();
    case 'loitering_detection':
      return `${metadata.zone_name ?? 'zone'} — dwelled ${formatSeconds(metadata.dwell_seconds)} (threshold ${formatSeconds(metadata.threshold_seconds)})`;
    case 'missing_object_detection':
      return `${metadata.class_label ?? 'object'} missing from ${metadata.zone_name ?? 'zone'} for ${formatSeconds(metadata.absence_seconds)}`;
    case 'license_plate_recognition':
      return `Plate ${metadata.plate_text ?? '?'}`;
    default:
      return event.event_type;
  }
}

function formatSeconds(value: unknown): string {
  return typeof value === 'number' ? `${value.toFixed(1)}s` : '?';
}
