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
