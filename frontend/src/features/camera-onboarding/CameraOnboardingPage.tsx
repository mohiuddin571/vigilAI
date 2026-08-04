import AddCameraForm from './AddCameraForm';
import CameraList from './CameraList';

function CameraOnboardingPage() {
  return (
    <div className="w-full max-w-xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">Cameras</h2>
      <p className="mt-1 text-sm text-slate-500">
        Onboard an ONVIF camera by IP address and credentials.
      </p>

      <div className="mt-4">
        <AddCameraForm />
      </div>

      <div className="mt-6 border-t border-slate-200 pt-4">
        <CameraList />
      </div>
    </div>
  );
}

export default CameraOnboardingPage;
