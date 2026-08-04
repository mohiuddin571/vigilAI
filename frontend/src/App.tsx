import { useState } from "react";
import CameraOnboardingPage from "./features/camera-onboarding/CameraOnboardingPage";
import LiveView from "./features/live-view/LiveView";
import RecordingControl from "./features/recordings/RecordingControl";
import RecordingsBrowser from "./features/recordings/RecordingsBrowser";
import useCameras from "./hooks/useCameras";

function App() {
  const { data: cameras, isLoading, isError } = useCameras();
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const selected = cameras?.find((camera) => camera.id === selectedCameraId) ?? cameras?.[0];

  return (
    <div className="flex min-h-screen flex-col items-center gap-6 bg-slate-50 py-10">
      <h1 className="text-2xl font-semibold text-slate-900">VigilAI</h1>
      <CameraOnboardingPage />
      <div className="w-full max-w-xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Camera Monitor</h2>
        <p className="mt-1 text-sm text-slate-500">
          Live MJPEG preview and recording control for one onboarded camera.
        </p>
        <div className="mt-4 space-y-3">
          {isLoading && <p className="text-sm text-slate-500">Loading cameras…</p>}
          {isError && <p className="text-sm text-red-600">Failed to load cameras.</p>}
          {!isLoading && !isError && !selected && (
            <p className="text-sm text-slate-500">No cameras onboarded yet.</p>
          )}
          {selected && cameras && (
            <>
              <label className="flex flex-col gap-1 text-sm text-slate-600">
                Camera
                <select
                  className="rounded border border-slate-300 px-2 py-1"
                  value={selected.id}
                  onChange={(event) => setSelectedCameraId(event.target.value)}
                >
                  {cameras.map((camera) => (
                    <option key={camera.id} value={camera.id}>
                      {camera.name}
                    </option>
                  ))}
                </select>
              </label>
              <LiveView cameraId={selected.id} cameraName={selected.name} />
              <RecordingControl cameraId={selected.id} />
            </>
          )}
        </div>
      </div>
      <div className="w-full max-w-xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Recordings</h2>
        <p className="mt-1 text-sm text-slate-500">
          Browse and play back recorded footage, filterable by camera and time range.
        </p>
        <div className="mt-4">
          {!isLoading && !isError && cameras && <RecordingsBrowser cameras={cameras} />}
        </div>
      </div>
    </div>
  );
}

export default App;
