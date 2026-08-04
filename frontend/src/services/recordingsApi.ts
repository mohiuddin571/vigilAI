import type { RecordingFilters, RecordingResponse } from '../types/recording';
import { ApiError, parseErrorDetail } from './camerasApi';

export async function startRecording(cameraId: string): Promise<RecordingResponse> {
  const response = await fetch(`/cameras/${cameraId}/recording/start`, { method: 'POST' });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as RecordingResponse;
}

export async function stopRecording(cameraId: string): Promise<RecordingResponse[]> {
  const response = await fetch(`/cameras/${cameraId}/recording/stop`, { method: 'POST' });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as RecordingResponse[];
}

/** `GET /recordings`, filterable by camera and/or time range (T-071) — every filter is optional. */
export async function listRecordings(filters: RecordingFilters = {}): Promise<RecordingResponse[]> {
  const params = new URLSearchParams();
  if (filters.cameraId) params.set('camera_id', filters.cameraId);
  if (filters.start) params.set('start', filters.start);
  if (filters.end) params.set('end', filters.end);
  const query = params.toString();
  const response = await fetch(query ? `/recordings?${query}` : '/recordings');
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as RecordingResponse[];
}

/** URL for a recording's MP4 file, playable directly by a native `<video>` element (T-070/T-072). */
export function recordingMediaUrl(recordingId: string): string {
  return `/recordings/${recordingId}/media`;
}
