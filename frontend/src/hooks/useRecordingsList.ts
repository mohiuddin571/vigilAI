import { useQuery } from '@tanstack/react-query';
import { listRecordings } from '../services/recordingsApi';
import type { RecordingFilters } from '../types/recording';

/** Filtered recordings browse (T-071/T-072) — camera/time-range filters are all optional. */
function useRecordingsList(filters: RecordingFilters) {
  return useQuery({
    queryKey: ['recordings', 'browse', filters],
    queryFn: () => listRecordings(filters),
  });
}

export default useRecordingsList;
