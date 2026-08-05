// Mirrors backend/app/interfaces/schemas/zones.py — kept in sync manually for
// now (see docs/FOLDER_STRUCTURE.md's note on frontend/src/types/).

export type ZonePoint = [number, number];

export interface ZoneResponse {
  id: string;
  camera_id: string;
  name: string;
  polygon: ZonePoint[];
  dwell_threshold_seconds: number;
  missing_object_threshold_seconds: number | null;
}

export interface ZoneCreateRequest {
  camera_id: string;
  name: string;
  polygon: ZonePoint[];
  dwell_threshold_seconds: number;
  missing_object_threshold_seconds?: number | null;
}

/** PATCH /zones/{id} body — every field optional, an omitted field keeps its current value. */
export interface ZoneUpdateRequest {
  name?: string;
  polygon?: ZonePoint[];
  dwell_threshold_seconds?: number;
  missing_object_threshold_seconds?: number | null;
}
