import { useQuery } from '@tanstack/react-query';
import { listCameras } from '../services/camerasApi';

/** The onboarded camera list, shared by any feature that needs to pick a camera. */
function useCameras() {
  return useQuery({ queryKey: ['cameras'], queryFn: listCameras });
}

export default useCameras;
