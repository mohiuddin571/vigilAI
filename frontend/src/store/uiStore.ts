import { create } from 'zustand';

interface UiState {
  /** Last camera viewed on Live View, so `/live` (no camera in the URL) has a sensible
   * default instead of always falling back to the first onboarded camera (TD-12/TD-31). */
  lastViewedCameraId: string | null;
  setLastViewedCameraId: (cameraId: string) => void;

  /** Count of analytics events received over `/ws/analytics/events` while the user is
   * somewhere other than Event Center — shown as a badge on the nav item (§5.8 of
   * docs/UI_UX_DESIGN.md). Purely client-side; no backend notification state exists. */
  unreadEventCount: number;
  recordUnreadEvents: (count: number) => void;
  clearUnreadEvents: () => void;
}

const useUiStore = create<UiState>((set) => ({
  lastViewedCameraId: null,
  setLastViewedCameraId: (cameraId) => set({ lastViewedCameraId: cameraId }),

  unreadEventCount: 0,
  recordUnreadEvents: (count) =>
    set((state) => ({ unreadEventCount: state.unreadEventCount + count })),
  clearUnreadEvents: () => set({ unreadEventCount: 0 }),
}));

export default useUiStore;
