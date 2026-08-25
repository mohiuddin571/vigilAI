import ConsumerPanel from '../features/rtmp-demo/ConsumerPanel';
import PublisherPanel from '../features/rtmp-demo/PublisherPanel';
import RtmpVideoPlayer from '../features/rtmp-demo/RtmpVideoPlayer';
import ServerPanel from '../features/rtmp-demo/ServerPanel';
import useRtmpDemo from '../hooks/useRtmpDemo';

/**
 * `/rtmp-demo` (docs/RTMP_DEMO.md) — proves a real
 * Video File → RTMP Publisher → RTMP Server → RTMP Consumer → Player round
 * trip, since there is no physical RTMP camera. Isolated from every other
 * page: its own API prefix (`/rtmp-demo`), its own feature folder
 * (`features/rtmp-demo/`), no shared state with the camera/recording/demo-
 * video pages. Outside the graded milestone sequence — see docs/RTMP_DEMO.md
 * for why this exists and how it's wired.
 */
function RtmpDemoPage() {
  const {
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
  } = useRtmpDemo();

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">RTMP Push/Consume Demo</h1>
        <p className="mt-1 text-sm text-slate-500">
          Video File → ffmpeg RTMP PUSH → MediaMTX RTMP Server → RTMP CONSUME → Player.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <PublisherPanel
          status={status?.publisher ?? null}
          rtmpUrl={status?.server.rtmp_url ?? ''}
          isStarting={isStartingPublisher}
          onStart={startPublisher}
          onStop={stopPublisher}
        />
        <ServerPanel
          status={status?.server ?? null}
          publishing={status?.publisher.running ?? false}
          isStarting={isStartingServer}
          onStart={startServer}
          onStop={stopServer}
        />
        <ConsumerPanel
          status={status?.consumer ?? null}
          isStarting={isStartingConsumer}
          onStart={startConsumer}
          onStop={stopConsumer}
        />
      </div>

      <RtmpVideoPlayer status={status?.consumer ?? null} mjpegUrl={mjpegUrl} />
    </div>
  );
}

export default RtmpDemoPage;
