import { useMutation } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  demoStreamStatusWebSocketUrl,
  mjpegDemoStreamUrl,
  startDemoStream,
  stopDemoStream,
} from '../services/demoApi';
import type { StreamStatusResponse } from '../types/stream';

interface UseDemoStreamResult {
  status: StreamStatusResponse | null;
  mjpegUrl: string;
  isConnecting: boolean;
  start: () => void;
  stop: () => void;
}

/**
 * Demo video stream state (M17): a small, deliberate duplicate of
 * `useLiveStream.ts`'s shape pointed at `demoApi` instead of `streamsApi` —
 * same "small duplication over cross-cutting abstraction" precedent the
 * backend's `StartDemoStreamUseCase` already follows.
 */
function useDemoStream(videoId: string): UseDemoStreamResult {
  const [status, setStatus] = useState<StreamStatusResponse | null>(null);

  useEffect(() => {
    const socket = new WebSocket(demoStreamStatusWebSocketUrl(videoId));
    socket.onmessage = (event: MessageEvent<string>) => {
      setStatus(JSON.parse(event.data) as StreamStatusResponse);
    };
    return () => socket.close();
  }, [videoId]);

  const { mutate: startMutate, isPending: isConnecting } = useMutation({
    mutationFn: () => startDemoStream(videoId),
  });
  const { mutate: stopMutate } = useMutation({ mutationFn: () => stopDemoStream(videoId) });
  const start = useCallback(() => startMutate(), [startMutate]);
  const stop = useCallback(() => stopMutate(), [stopMutate]);

  // Cache-bust per mount, same reasoning as `useLiveStream.ts`.
  const mjpegUrl = useMemo(() => `${mjpegDemoStreamUrl(videoId)}?t=${Date.now()}`, [videoId]);

  return {
    status,
    mjpegUrl,
    isConnecting,
    start,
    stop,
  };
}

export default useDemoStream;
