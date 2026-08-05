import { useQuery } from '@tanstack/react-query';
import { listZonesByCamera } from '../services/zonesApi';

/** Every `AnalyticsZone` defined for one camera (T-111). */
function useZones(cameraId: string) {
  return useQuery({
    queryKey: ['zones', cameraId],
    queryFn: () => listZonesByCamera(cameraId),
  });
}

export default useZones;
