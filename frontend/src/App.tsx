import CameraOnboardingPage from "./features/camera-onboarding/CameraOnboardingPage";
import LiveViewPage from "./features/live-view/LiveViewPage";

function App() {
  return (
    <div className="flex min-h-screen flex-col items-center gap-6 bg-slate-50 py-10">
      <h1 className="text-2xl font-semibold text-slate-900">VigilAI</h1>
      <CameraOnboardingPage />
      <div className="w-full max-w-xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Live View</h2>
        <p className="mt-1 text-sm text-slate-500">
          Live MJPEG preview of an onboarded camera, with connection status.
        </p>
        <div className="mt-4">
          <LiveViewPage />
        </div>
      </div>
    </div>
  );
}

export default App;
