import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { listRecordings, startRecording, stopRecording } from '../services/recordingsApi';
import type { RecordingResponse } from '../types/recording';

interface UseRecordingResult {
  recordings: RecordingResponse[];
  isLoading: boolean;
  isRecording: boolean;
  isStarting: boolean;
  isStopping: boolean;
  error: string | null;
  start: () => void;
  stop: () => void;
}

/** Start/stop + list state for one camera's recordings (T-062/T-063). */
function useRecording(cameraId: string): UseRecordingResult {
  const queryClient = useQueryClient();
  const queryKey = ['recordings', cameraId];

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => listRecordings({ cameraId }),
  });
  const recordings = data ?? [];
  const isRecording = recordings.some((recording) => recording.ended_at === null);

  const startMutation = useMutation({
    mutationFn: () => startRecording(cameraId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });
  const stopMutation = useMutation({
    mutationFn: () => stopRecording(cameraId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const failure = startMutation.error ?? stopMutation.error;

  return {
    recordings,
    isLoading,
    isRecording,
    isStarting: startMutation.isPending,
    isStopping: stopMutation.isPending,
    error: failure instanceof Error ? failure.message : null,
    start: () => startMutation.mutate(),
    stop: () => stopMutation.mutate(),
  };
}

export default useRecording;
