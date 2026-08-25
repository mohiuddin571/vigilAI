import { useQuery } from '@tanstack/react-query';
import { listRtmpDemoVideos } from '../services/rtmpDemoApi';

/** The publishable video list for the RTMP Demo's Publisher panel — the same
 * `storage/demo_videos/` library `useDemoVideos.ts` lists, reached through
 * `/rtmp-demo/videos` instead of `/demo/videos` so the RTMP Demo page only
 * ever talks to its own isolated API prefix (docs/RTMP_DEMO.md). */
function useRtmpDemoVideos() {
  return useQuery({ queryKey: ['rtmp-demo-videos'], queryFn: listRtmpDemoVideos });
}

export default useRtmpDemoVideos;
