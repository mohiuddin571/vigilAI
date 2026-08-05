import type { AnalyticsStatusResponse } from '../types/analytics';
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
