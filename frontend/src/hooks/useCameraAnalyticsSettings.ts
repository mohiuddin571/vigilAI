import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getCameraAnalyticsSettings,
  updateCameraAnalyticsSettings,
} from '../services/camerasApi';

interface UseCameraAnalyticsSettingsResult {
  availableTypes: string[];
  enabledTypes: string[] | null;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  save: (enabledTypes: string[] | null) => void;
}

/** Which detector types run for one camera's analytics pipeline (Camera Detail's
 * Settings tab) — distinct from `useAnalyticsStatus`'s whole-pipeline on/off toggle:
 * this is the persisted per-type subset that toggle's "on" state actually runs. */
function useCameraAnalyticsSettings(cameraId: string): UseCameraAnalyticsSettingsResult {
  const queryClient = useQueryClient();
  const queryKey = ['camera-analytics-settings', cameraId];

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => getCameraAnalyticsSettings(cameraId),
  });

  const saveMutation = useMutation({
    mutationFn: (enabledTypes: string[] | null) =>
      updateCameraAnalyticsSettings(cameraId, { enabled_types: enabledTypes }),
    onSuccess: (settings) => queryClient.setQueryData(queryKey, settings),
  });

  return {
    availableTypes: data?.available_types ?? [],
    enabledTypes: data?.enabled_types ?? null,
    isLoading,
    isSaving: saveMutation.isPending,
    error: saveMutation.isError ? 'Failed to save event capture settings.' : null,
    save: (enabledTypes) => saveMutation.mutate(enabledTypes),
  };
}

export default useCameraAnalyticsSettings;
