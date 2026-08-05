import type {
  AnalyticsStatusResponse,
  ClearEventsResponse,
  DetectionEventFilters,
  DetectionEventResponse,
} from '../types/analytics';
import { ApiError, parseErrorDetail } from './camerasApi';

export function analyticsEventsWebSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/analytics/events`;
}

export async function enableAnalytics(sourceId: string): Promise<AnalyticsStatusResponse> {
  const response = await fetch(`/analytics/${sourceId}/enable`, { method: 'POST' });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as AnalyticsStatusResponse;
}

export async function disableAnalytics(sourceId: string): Promise<AnalyticsStatusResponse> {
  const response = await fetch(`/analytics/${sourceId}/disable`, { method: 'POST' });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as AnalyticsStatusResponse;
}

export async function getAnalyticsStatus(sourceId: string): Promise<AnalyticsStatusResponse> {
  const response = await fetch(`/analytics/${sourceId}/status`);
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as AnalyticsStatusResponse;
}

/** `GET /analytics/events` (T-083), filterable by camera/exact event type/time range — all optional. */
export async function listDetectionEvents(
  filters: DetectionEventFilters = {},
): Promise<DetectionEventResponse[]> {
  const params = new URLSearchParams();
  if (filters.cameraId) params.set('camera_id', filters.cameraId);
  if (filters.eventType) params.set('event_type', filters.eventType);
  if (filters.start) params.set('start', filters.start);
  if (filters.end) params.set('end', filters.end);
  const query = params.toString();
  const response = await fetch(query ? `/analytics/events?${query}` : '/analytics/events');
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as DetectionEventResponse[];
}

/** `DELETE /analytics/events` (T-173) — same optional filters as `listDetectionEvents`;
 * no filters clears every event. Returns how many rows were removed. */
export async function clearDetectionEvents(
  filters: DetectionEventFilters = {},
): Promise<ClearEventsResponse> {
  const params = new URLSearchParams();
  if (filters.cameraId) params.set('camera_id', filters.cameraId);
  if (filters.eventType) params.set('event_type', filters.eventType);
  if (filters.start) params.set('start', filters.start);
  if (filters.end) params.set('end', filters.end);
  const query = params.toString();
  const response = await fetch(query ? `/analytics/events?${query}` : '/analytics/events', {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as ClearEventsResponse;
}
