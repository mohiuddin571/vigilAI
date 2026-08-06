import { useMutation } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { mjpegStreamUrl, startStream, stopStream, streamStatusWebSocketUrl } from '../services/streamsApi';
import type { StreamStatusResponse } from '../types/stream';

interface UseLiveStreamResult {
  status: StreamStatusResponse | null;
  mjpegUrl: string;
  isConnecting: boolean;
  start: () => void;
  stop: () => void;
}

/** Live-view state for one camera (T-055): MJPEG image URL + WS-driven connection status. */
function useLiveStream(cameraId: string): UseLiveStreamResult {
  const [status, setStatus] = useState<StreamStatusResponse | null>(null);

  useEffect(() => {
    const socket = new WebSocket(streamStatusWebSocketUrl(cameraId));
    socket.onmessage = (event: MessageEvent<string>) => {
      setStatus(JSON.parse(event.data) as StreamStatusResponse);
    };
    return () => socket.close();
  }, [cameraId]);

  const { mutate: startMutate, isPending: isConnecting } = useMutation({
    mutationFn: () => startStream(cameraId),
  });
  const { mutate: stopMutate } = useMutation({ mutationFn: () => stopStream(cameraId) });
  const start = useCallback(() => startMutate(), [startMutate]);
  const stop = useCallback(() => stopMutate(), [stopMutate]);

  // Cache-bust per mount: the browser can otherwise reuse a stale/cached
  // response for this exact URL from an earlier <img> (e.g. the Dashboard
  // tile, or the same tab's previous mount) instead of opening a fresh
  // multipart connection, which renders as one frozen frame until a full
  // page reload. A token fixed for this hook instance's lifetime — not
  // recomputed on every render — still lets the browser reuse one open
  // connection across re-renders while streaming.
  const mjpegUrl = useMemo(() => `${mjpegStreamUrl(cameraId)}?t=${Date.now()}`, [cameraId]);

  return {
    status,
    mjpegUrl,
    isConnecting,
    start,
    stop,
  };
}

export default useLiveStream;
