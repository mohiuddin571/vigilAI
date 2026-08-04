import type { StreamStatusResponse } from '../types/stream';
import { ApiError, parseErrorDetail } from './camerasApi';

export function mjpegStreamUrl(cameraId: string): string {
  return `/streams/${cameraId}/mjpeg`;
}

export function streamStatusWebSocketUrl(cameraId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/streams/${cameraId}/status`;
}

export async function startStream(cameraId: string): Promise<StreamStatusResponse> {
  const response = await fetch(`/streams/${cameraId}/start`, { method: 'POST' });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as StreamStatusResponse;
}

export async function stopStream(cameraId: string): Promise<StreamStatusResponse> {
  const response = await fetch(`/streams/${cameraId}/stop`, { method: 'POST' });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as StreamStatusResponse;
}
