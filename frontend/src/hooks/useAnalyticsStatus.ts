import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { disableAnalytics, enableAnalytics, getAnalyticsStatus } from '../services/analyticsApi';

interface UseAnalyticsStatusResult {
  enabled: boolean;
  isLoading: boolean;
  isToggling: boolean;
  enable: () => void;
  disable: () => void;
}

/** Analytics enable/disable + status for one source (T-085) — real cameras use
 * their own `Camera.id` as `source_id` (see `missing_object_detector.py`'s
 * `_derive_camera_id` docstring), so `sourceId` here is always a `cameraId`. */
function useAnalyticsStatus(sourceId: string): UseAnalyticsStatusResult {
  const queryClient = useQueryClient();
  const queryKey = ['analytics-status', sourceId];

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => getAnalyticsStatus(sourceId),
  });

  const enableMutation = useMutation({
    mutationFn: () => enableAnalytics(sourceId),
    onSuccess: (status) => queryClient.setQueryData(queryKey, status),
  });
  const disableMutation = useMutation({
    mutationFn: () => disableAnalytics(sourceId),
    onSuccess: (status) => queryClient.setQueryData(queryKey, status),
  });

  return {
    enabled: data?.enabled ?? false,
    isLoading,
    isToggling: enableMutation.isPending || disableMutation.isPending,
    enable: () => enableMutation.mutate(),
    disable: () => disableMutation.mutate(),
  };
}

export default useAnalyticsStatus;
