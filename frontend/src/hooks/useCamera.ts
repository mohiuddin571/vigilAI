import { useQuery } from '@tanstack/react-query';
import { getCamera } from '../services/camerasApi';

/** One onboarded camera by id (T-033's `GET /cameras/{id}`), for Camera Detail. */
function useCamera(cameraId: string | undefined) {
  return useQuery({
    queryKey: ['camera', cameraId],
    queryFn: () => getCamera(cameraId as string),
    enabled: cameraId !== undefined,
  });
}

export default useCamera;
