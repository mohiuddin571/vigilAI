import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import AppShell from './components/AppShell';
import CameraDetailPage, {
  CameraConfigTab,
  CameraLiveViewTab,
  CameraOverviewTab,
  CameraRecordingsTab,
  CameraSettingsTab,
  CameraZonesTab,
} from './pages/CameraDetailPage';
import CameraListPage from './pages/CameraListPage';
import DashboardPage from './pages/DashboardPage';
import DemoPage from './pages/DemoPage';
import EventsPage from './pages/EventsPage';
import LiveViewPage from './pages/LiveViewPage';
import RecordingsPage from './pages/RecordingsPage';

// Routing shell (T-140) per docs/UI_UX_DESIGN.md §3's sitemap. Declarative
// mode (`<BrowserRouter>`/`<Routes>`), not the data router — data fetching
// stays entirely in React Query per TD-12, routing only decides what's on
// screen (TD-31).
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />

          <Route path="cameras">
            <Route index element={<CameraListPage />} />
            <Route path=":cameraId" element={<CameraDetailPage />}>
              <Route index element={<CameraOverviewTab />} />
              <Route path="config" element={<CameraConfigTab />} />
              <Route path="zones" element={<CameraZonesTab />} />
              <Route path="live" element={<CameraLiveViewTab />} />
              <Route path="recordings" element={<CameraRecordingsTab />} />
              <Route path="settings" element={<CameraSettingsTab />} />
            </Route>
          </Route>

          <Route path="live">
            <Route index element={<LiveViewPage />} />
            <Route path=":cameraId" element={<LiveViewPage />} />
          </Route>

          <Route path="recordings" element={<RecordingsPage />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="demo" element={<DemoPage />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
