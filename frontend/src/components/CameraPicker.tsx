import type { CameraResponse } from '../types/camera';

interface CameraPickerProps {
  cameras: CameraResponse[];
  value: string;
  onChange: (cameraId: string) => void;
  label?: string;
  includeAllOption?: boolean;
  className?: string;
}

/** Shared "pick a camera" `<select>` (`components/` — feature-agnostic, depends
 * only on `types/`), replacing the inline `<select>` duplicated across the
 * pre-M14 `App.tsx` and `RecordingsBrowser.tsx`. */
function CameraPicker({
  cameras,
  value,
  onChange,
  label = 'Camera',
  includeAllOption = false,
  className = '',
}: CameraPickerProps) {
  return (
    <label className={`flex flex-col gap-1 text-sm text-slate-600 ${className}`}>
      {label}
      <select
        className="rounded border border-slate-300 px-2 py-1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {includeAllOption && <option value="">All cameras</option>}
        {cameras.map((camera) => (
          <option key={camera.id} value={camera.id}>
            {camera.name}
          </option>
        ))}
      </select>
    </label>
  );
}

export default CameraPicker;
