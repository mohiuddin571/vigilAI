// Mirrors backend/app/interfaces/schemas/camera.py — kept in sync manually for
// now (see docs/FOLDER_STRUCTURE.md's note on frontend/src/types/).

export interface CameraCreateRequest {
  ip_address: string;
  port?: number;
  username: string;
  password: string;
}

export interface StreamProfileResponse {
  id: string;
  name: string;
  resolution: string;
  codec: string;
  bitrate_kbps: number;
  fps: number;
  is_primary: boolean;
}

export interface CameraResponse {
  id: string;
  name: string;
  ip_address: string;
  port: number;
  username: string;
  manufacturer: string | null;
  model: string | null;
  firmware_version: string | null;
  is_online: boolean;
  stream_profiles: StreamProfileResponse[];
}
