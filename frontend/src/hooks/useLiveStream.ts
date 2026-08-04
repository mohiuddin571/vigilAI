import { useMutation } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
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

  const startMutation = useMutation({ mutationFn: () => startStream(cameraId) });
  const stopMutation = useMutation({ mutationFn: () => stopStream(cameraId) });

  return {
    status,
    mjpegUrl: mjpegStreamUrl(cameraId),
    isConnecting: startMutation.isPending,
    start: () => startMutation.mutate(),
    stop: () => stopMutation.mutate(),
  };
}

export default useLiveStream;
