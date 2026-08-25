// Mirrors backend/app/interfaces/schemas/rtmp_demo.py.

import type { StreamState } from './stream';

export interface RtmpServerStatusResponse {
  running: boolean;
  pid: number | null;
  host: string;
  port: number;
  app_name: string;
  stream_key: string;
  rtmp_url: string;
}

export interface RtmpPublisherStatusResponse {
  running: boolean;
  pid: number | null;
  video_id: string | null;
  exited_unexpectedly: boolean;
  error: string | null;
  publish_auth_required: boolean;
}

export interface RtmpConsumerStatusResponse {
  state: StreamState;
  last_frame_at: string | null;
  consecutive_failures: number;
  last_error: string | null;
  observed_resolution: [number, number] | null;
  observed_fps: number | null;
  configured_codec: string;
  configured_video_bitrate_kbps: number;
  read_auth_required: boolean;
  rtmp_url: string;
}

export interface RtmpDemoStatusMessage {
  server: RtmpServerStatusResponse;
  publisher: RtmpPublisherStatusResponse;
  consumer: RtmpConsumerStatusResponse;
}
