import { useQuery } from '@tanstack/react-query';
import { listDetectionEvents } from '../services/analyticsApi';
import type { DetectionEventFilters } from '../types/analytics';

/** Historical analytics events (T-083), filtered server-side by camera/exact
 * event type/time range — used by Event Center and the Dashboard's recent-events widget. */
function useAnalyticsEvents(filters: DetectionEventFilters = {}) {
  return useQuery({
    queryKey: ['analytics-events', filters],
    queryFn: () => listDetectionEvents(filters),
  });
}

export default useAnalyticsEvents;
