import { useQuery } from '@tanstack/react-query';
import { listCameras } from '../../services/camerasApi';

function CameraList() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['cameras'],
    queryFn: listCameras,
  });

  if (isLoading) return <p className="text-sm text-slate-500">Loading cameras…</p>;
  if (isError) return <p className="text-sm text-red-600">Failed to load cameras.</p>;
  if (!data || data.length === 0) {
    return <p className="text-sm text-slate-500">No cameras onboarded yet.</p>;
  }

  return (
    <ul className="divide-y divide-slate-200">
      {data.map((camera) => (
        <li key={camera.id} className="py-3">
          <div className="flex items-center justify-between">
            <span className="font-medium text-slate-900">{camera.name}</span>
            <span
              className={`h-2.5 w-2.5 rounded-full ${camera.is_online ? 'bg-emerald-500' : 'bg-slate-300'}`}
              title={camera.is_online ? 'Online' : 'Offline'}
            />
          </div>
          <p className="text-sm text-slate-500">
            {camera.ip_address}:{camera.port} — {camera.manufacturer ?? 'Unknown manufacturer'}{' '}
            {camera.model ?? ''}
          </p>
          <p className="text-xs text-slate-400">
            {camera.stream_profiles.length} stream profile
            {camera.stream_profiles.length === 1 ? '' : 's'}:{' '}
            {camera.stream_profiles.map((profile) => profile.resolution).join(', ')}
          </p>
        </li>
      ))}
    </ul>
  );
}

export default CameraList;
