import { useEffect, useRef, useState } from 'react';
import { analyticsEventsWebSocketUrl } from '../services/analyticsApi';
import type { DetectionEventResponse } from '../types/analytics';

const _DEFAULT_MAX_BUFFERED = 200;

/**
 * Subscribes to the one global `/ws/analytics/events` channel (T-084 — no
 * per-source server-side filtering yet, see DetectionOverlay's docstring for
 * the same caveat) and keeps the most recent `maxBuffered` events, newest
 * first. `enabled=false` tears the socket down without unmounting the
 * consumer — used by Event Center's "Live" pill to freeze the feed while
 * scrolling through history.
 */
function useAnalyticsEventsFeed(
  enabled: boolean,
  maxBuffered: number = _DEFAULT_MAX_BUFFERED,
): DetectionEventResponse[] {
  const [events, setEvents] = useState<DetectionEventResponse[]>([]);
  const maxBufferedRef = useRef(maxBuffered);
  maxBufferedRef.current = maxBuffered;

  useEffect(() => {
    if (!enabled) return;
    const socket = new WebSocket(analyticsEventsWebSocketUrl());
    socket.onmessage = (event: MessageEvent<string>) => {
      const detection = JSON.parse(event.data) as DetectionEventResponse;
      setEvents((previous) => [detection, ...previous].slice(0, maxBufferedRef.current));
    };
    return () => socket.close();
  }, [enabled]);

  return events;
}

export default useAnalyticsEventsFeed;
