import type { ZoneCreateRequest, ZoneResponse } from '../types/zone';
import { ApiError, parseErrorDetail } from './camerasApi';

export async function listZonesByCamera(cameraId: string): Promise<ZoneResponse[]> {
  const params = new URLSearchParams({ camera_id: cameraId });
  const response = await fetch(`/zones?${params.toString()}`);
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as ZoneResponse[];
}

export async function createZone(payload: ZoneCreateRequest): Promise<ZoneResponse> {
  const response = await fetch('/zones', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as ZoneResponse;
}

export async function deleteZone(zoneId: string): Promise<void> {
  const response = await fetch(`/zones/${zoneId}`, { method: 'DELETE' });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
}
