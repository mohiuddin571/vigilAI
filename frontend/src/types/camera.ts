// Mirrors backend/app/interfaces/schemas/camera.py — kept in sync manually for
// now (see docs/FOLDER_STRUCTURE.md's note on frontend/src/types/).

export interface CameraCreateRequest {
  ip_address: string;
  port?: number;
  username: string;
  password: string;
  rtsp_url_override?: string | null;
}

/** PATCH /cameras/{id} body (T-170) — every field optional, an omitted field is left at its
 * current persisted value. Distinct from the RTSP-override and encoder-config PATCH endpoints. */
export interface CameraUpdateRequest {
  name?: string;
  ip_address?: string;
  port?: number;
  username?: string;
  password?: string;
}

export interface StreamProfileResponse {
  id: string;
  name: string;
  resolution: string;
  codec: string;
  bitrate_kbps: number;
  fps: number;
  is_primary: boolean;
  onvif_token: string | null;
}

export interface CameraResponse {
  id: string;
  name: string;
  ip_address: string;
  port: number;
  username: string;
  rtsp_url_override: string | null;
  manufacturer: string | null;
  model: string | null;
  firmware_version: string | null;
  is_online: boolean;
  stream_profiles: StreamProfileResponse[];
}

export interface VideoEncoderCapabilitiesResponse {
  resolutions: string[];
  fps_min: number;
  fps_max: number;
  bitrate_min_kbps: number | null;
  bitrate_max_kbps: number | null;
}

export interface CameraConfigResponse {
  profile_id: string;
  name: string;
  resolution: string;
  codec: string;
  bitrate_kbps: number;
  fps: number;
  capabilities: VideoEncoderCapabilitiesResponse | null;
}

export interface ResolutionUpdate {
  width: number;
  height: number;
}

export interface CameraConfigUpdateRequest {
  resolution?: ResolutionUpdate;
  bitrate_kbps?: number;
  fps?: number;
}
