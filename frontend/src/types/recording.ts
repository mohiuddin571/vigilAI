// Mirrors backend/app/interfaces/schemas/recording.py — kept in sync manually
// for now (see docs/FOLDER_STRUCTURE.md's note on frontend/src/types/).

export interface RecordingResponse {
  id: string;
  camera_id: string;
  file_path: string;
  started_at: string;
  ended_at: string | null;
  size_bytes: number | null;
  duration_seconds: number | null;
}

/** Browse filters for `GET /recordings` (T-071) — all optional. */
export interface RecordingFilters {
  cameraId?: string;
  start?: string;
  end?: string;
}
