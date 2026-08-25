import type { DemoVideoResponse } from '../types/demoVideo';
import type {
  RtmpConsumerStatusResponse,
  RtmpPublisherStatusResponse,
  RtmpServerStatusResponse,
} from '../types/rtmpDemo';
import { ApiError, parseErrorDetail } from './camerasApi';

// Isolated from `streamsApi.ts`/`demoApi.ts` — see docs/RTMP_DEMO.md.
// Mirrors their shape (POST start/stop, GET status) three times over, one
// per independently controllable lifecycle (server/publisher/consumer).

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    ...(body !== undefined
      ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
      : {}),
  });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as T;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as T;
}

export async function listRtmpDemoVideos(): Promise<DemoVideoResponse[]> {
  return get<DemoVideoResponse[]>('/rtmp-demo/videos');
}

export async function startRtmpServer(): Promise<RtmpServerStatusResponse> {
  return post<RtmpServerStatusResponse>('/rtmp-demo/server/start');
}

export async function stopRtmpServer(): Promise<RtmpServerStatusResponse> {
  return post<RtmpServerStatusResponse>('/rtmp-demo/server/stop');
}

export async function getRtmpServerStatus(): Promise<RtmpServerStatusResponse> {
  return get<RtmpServerStatusResponse>('/rtmp-demo/server/status');
}

export async function startRtmpPublisher(videoId: string): Promise<RtmpPublisherStatusResponse> {
  return post<RtmpPublisherStatusResponse>('/rtmp-demo/publisher/start', { video_id: videoId });
}

export async function stopRtmpPublisher(): Promise<RtmpPublisherStatusResponse> {
  return post<RtmpPublisherStatusResponse>('/rtmp-demo/publisher/stop');
}

export async function getRtmpPublisherStatus(): Promise<RtmpPublisherStatusResponse> {
  return get<RtmpPublisherStatusResponse>('/rtmp-demo/publisher/status');
}

export async function startRtmpConsumer(): Promise<RtmpConsumerStatusResponse> {
  return post<RtmpConsumerStatusResponse>('/rtmp-demo/consumer/start');
}

export async function stopRtmpConsumer(): Promise<RtmpConsumerStatusResponse> {
  return post<RtmpConsumerStatusResponse>('/rtmp-demo/consumer/stop');
}

export async function getRtmpConsumerStatus(): Promise<RtmpConsumerStatusResponse> {
  return get<RtmpConsumerStatusResponse>('/rtmp-demo/consumer/status');
}

export function mjpegRtmpConsumerUrl(): string {
  return '/rtmp-demo/consumer/mjpeg';
}

export function rtmpDemoStatusWebSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/rtmp-demo/status`;
}
