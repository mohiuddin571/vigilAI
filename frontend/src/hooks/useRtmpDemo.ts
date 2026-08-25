import { useMutation } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  mjpegRtmpConsumerUrl,
  rtmpDemoStatusWebSocketUrl,
  startRtmpConsumer,
  startRtmpPublisher,
  startRtmpServer,
  stopRtmpConsumer,
  stopRtmpPublisher,
  stopRtmpServer,
} from '../services/rtmpDemoApi';
import type { RtmpDemoStatusMessage } from '../types/rtmpDemo';

interface UseRtmpDemoResult {
  status: RtmpDemoStatusMessage | null;
  mjpegUrl: string;
  startServer: () => void;
  stopServer: () => void;
  startPublisher: (videoId: string) => void;
  stopPublisher: () => void;
  startConsumer: () => void;
  stopConsumer: () => void;
  isStartingServer: boolean;
  isStartingPublisher: boolean;
  isStartingConsumer: boolean;
}

/**
 * One combined hook for the RTMP Demo page's three independently
 * controllable lifecycles (server/publisher/consumer) — a single
 * `/ws/rtmp-demo/status` subscription drives all three panels, otherwise
 * mirroring `useDemoStream.ts`'s mutation-plus-WebSocket shape.
 */
function useRtmpDemo(): UseRtmpDemoResult {
  const [status, setStatus] = useState<RtmpDemoStatusMessage | null>(null);

  useEffect(() => {
    const socket = new WebSocket(rtmpDemoStatusWebSocketUrl());
    socket.onmessage = (event: MessageEvent<string>) => {
      setStatus(JSON.parse(event.data) as RtmpDemoStatusMessage);
    };
    return () => socket.close();
  }, []);

  const { mutate: startServerMutate, isPending: isStartingServer } = useMutation({
    mutationFn: startRtmpServer,
  });
  const { mutate: stopServerMutate } = useMutation({ mutationFn: stopRtmpServer });

  const { mutate: startPublisherMutate, isPending: isStartingPublisher } = useMutation({
    mutationFn: (videoId: string) => startRtmpPublisher(videoId),
  });
  const { mutate: stopPublisherMutate } = useMutation({ mutationFn: stopRtmpPublisher });

  const { mutate: startConsumerMutate, isPending: isStartingConsumer } = useMutation({
    mutationFn: startRtmpConsumer,
  });
  const { mutate: stopConsumerMutate } = useMutation({ mutationFn: stopRtmpConsumer });

  const startServer = useCallback(() => startServerMutate(), [startServerMutate]);
  const stopServer = useCallback(() => stopServerMutate(), [stopServerMutate]);
  const startPublisher = useCallback(
    (videoId: string) => startPublisherMutate(videoId),
    [startPublisherMutate],
  );
  const stopPublisher = useCallback(() => stopPublisherMutate(), [stopPublisherMutate]);
  const startConsumer = useCallback(() => startConsumerMutate(), [startConsumerMutate]);
  const stopConsumer = useCallback(() => stopConsumerMutate(), [stopConsumerMutate]);

  // Cache-bust per mount, same reasoning as `useLiveStream.ts`/`useDemoStream.ts`.
  const mjpegUrl = useMemo(() => `${mjpegRtmpConsumerUrl()}?t=${Date.now()}`, []);

  return {
    status,
    mjpegUrl,
    startServer,
    stopServer,
    startPublisher,
    stopPublisher,
    startConsumer,
    stopConsumer,
    isStartingServer,
    isStartingPublisher,
    isStartingConsumer,
  };
}

export default useRtmpDemo;
