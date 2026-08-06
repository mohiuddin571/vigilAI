import type { DemoVideoResponse } from '../types/demoVideo';
import type { StreamStatusResponse } from '../types/stream';
import { ApiError, parseErrorDetail } from './camerasApi';

// Mirrors `streamsApi.ts`'s shape (M17), keyed by `video_id: string` (a
// `DemoVideo.id` slug) instead of a camera UUID.

export async function listDemoVideos(): Promise<DemoVideoResponse[]> {
  const response = await fetch('/demo/videos');
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as DemoVideoResponse[];
}

export function mjpegDemoStreamUrl(videoId: string): string {
  return `/demo/videos/${videoId}/mjpeg`;
}

export function demoStreamStatusWebSocketUrl(videoId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/demo/videos/${videoId}/status`;
}

export async function startDemoStream(videoId: string): Promise<StreamStatusResponse> {
  const response = await fetch(`/demo/videos/${videoId}/start`, { method: 'POST' });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as StreamStatusResponse;
}

export async function stopDemoStream(videoId: string): Promise<StreamStatusResponse> {
  const response = await fetch(`/demo/videos/${videoId}/stop`, { method: 'POST' });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as StreamStatusResponse;
}
