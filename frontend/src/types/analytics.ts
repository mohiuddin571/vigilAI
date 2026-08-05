// Mirrors backend/app/interfaces/schemas/analytics.py — kept in sync manually
// for now (see docs/FOLDER_STRUCTURE.md's note on frontend/src/types/).

export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

export interface DetectionEventResponse {
  id: string;
  camera_id: string;
  event_type: string;
  occurred_at: string;
  confidence: number;
  bounding_box: BoundingBox | null;
  metadata: Record<string, unknown>;
}

export interface AnalyticsStatusResponse {
  source_id: string;
  enabled: boolean;
}

/** Filters for `GET /analytics/events` (T-085) — all optional. `eventType` must be an
 * exact stored `event_type` value (e.g. `"loitering_detection.dwell_exceeded"`), since
 * the backend filter is an exact match, not a prefix — category-level filtering (e.g.
 * "every loitering event regardless of outcome") is done client-side instead. */
export interface DetectionEventFilters {
  cameraId?: string;
  eventType?: string;
  start?: string;
  end?: string;
}

/** Response shape for `DELETE /analytics/events` (T-173) — how many rows were removed. */
export interface ClearEventsResponse {
  deleted_count: number;
}
