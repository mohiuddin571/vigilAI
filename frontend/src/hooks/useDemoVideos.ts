import { useQuery } from '@tanstack/react-query';
import { listDemoVideos } from '../services/demoApi';

/** The demo video library list (M17), mirrors `useCameras.ts`. */
function useDemoVideos() {
  return useQuery({ queryKey: ['demo-videos'], queryFn: listDemoVideos });
}

export default useDemoVideos;
