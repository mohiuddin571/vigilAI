// Mirrors backend/app/interfaces/schemas/stream.py — kept in sync manually for
// now (see docs/FOLDER_STRUCTURE.md's note on frontend/src/types/).

export type StreamState = 'connecting' | 'connected' | 'reconnecting' | 'failed' | 'stopped';

export interface StreamStatusResponse {
  state: StreamState;
  last_frame_at: string | null;
  consecutive_failures: number;
  last_error: string | null;
}
