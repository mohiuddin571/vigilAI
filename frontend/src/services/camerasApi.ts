import type {
  CameraConfigResponse,
  CameraConfigUpdateRequest,
  CameraCreateRequest,
  CameraResponse,
} from '../types/camera';

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? `Request failed with status ${response.status}`;
  } catch {
    return `Request failed with status ${response.status}`;
  }
}

export async function listCameras(): Promise<CameraResponse[]> {
  const response = await fetch('/cameras');
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as CameraResponse[];
}

export async function createCamera(payload: CameraCreateRequest): Promise<CameraResponse> {
  const response = await fetch('/cameras', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as CameraResponse;
}

export async function getCamera(cameraId: string): Promise<CameraResponse> {
  const response = await fetch(`/cameras/${cameraId}`);
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as CameraResponse;
}

export async function updateCameraRtspUrl(
  cameraId: string,
  rtspUrlOverride: string | null,
): Promise<CameraResponse> {
  const response = await fetch(`/cameras/${cameraId}/rtsp-url`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rtsp_url_override: rtspUrlOverride }),
  });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as CameraResponse;
}

export async function getCameraConfig(
  cameraId: string,
  profileId: string,
): Promise<CameraConfigResponse> {
  const params = new URLSearchParams({ profile_id: profileId });
  const response = await fetch(`/cameras/${cameraId}/config?${params.toString()}`);
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as CameraConfigResponse;
}

export async function updateCameraConfig(
  cameraId: string,
  profileId: string,
  payload: CameraConfigUpdateRequest,
): Promise<CameraConfigResponse> {
  const params = new URLSearchParams({ profile_id: profileId });
  const response = await fetch(`/cameras/${cameraId}/config?${params.toString()}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as CameraConfigResponse;
}
