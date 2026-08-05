import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { listCameras, updateCameraRtspUrl } from '../../services/camerasApi';
import ConfigPanel from './ConfigPanel';

interface CameraListProps {
  /** Client-side name/IP substring filter (docs/UI_UX_DESIGN.md §5.9) — no
   * backend search endpoint exists, so this filters the already-fetched list. */
  nameFilter?: string;
}

function CameraList({ nameFilter = '' }: CameraListProps) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['cameras'],
    queryFn: listCameras,
  });
  const needle = nameFilter.trim().toLowerCase();
  const filtered = needle
    ? data?.filter(
        (camera) =>
          camera.name.toLowerCase().includes(needle) || camera.ip_address.includes(needle),
      )
    : data;
  const [openProfile, setOpenProfile] = useState<{ cameraId: string; profileId: string } | null>(
    null,
  );
  const [rtspOverrides, setRtspOverrides] = useState<Record<string, string>>({});
  const updateRtspMutation = useMutation({
    mutationFn: ({ cameraId, value }: { cameraId: string; value: string | null }) =>
      updateCameraRtspUrl(cameraId, value),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['cameras'] }),
  });

  if (isLoading) return <p className="text-sm text-slate-500">Loading cameras…</p>;
  if (isError) return <p className="text-sm text-red-600">Failed to load cameras.</p>;
  if (!data || data.length === 0) {
    return <p className="text-sm text-slate-500">No cameras onboarded yet.</p>;
  }
  if (!filtered || filtered.length === 0) {
    return <p className="text-sm text-slate-500">No cameras match “{nameFilter}”.</p>;
  }

  return (
    <ul className="divide-y divide-slate-200">
      {filtered.map((camera) => (
        <li key={camera.id} className="py-3">
          <div className="flex items-center justify-between">
            <Link
              to={`/cameras/${camera.id}`}
              className="font-medium text-slate-900 hover:underline"
            >
              {camera.name}
            </Link>
            <span
              className={`h-2.5 w-2.5 rounded-full ${camera.is_online ? 'bg-emerald-500' : 'bg-slate-300'}`}
              title={camera.is_online ? 'Online' : 'Offline'}
            />
          </div>
          <p className="text-sm text-slate-500">
            {camera.ip_address}:{camera.port} — {camera.manufacturer ?? 'Unknown manufacturer'}{' '}
            {camera.model ?? ''}
          </p>
          <div className="mt-2 flex gap-2">
            <input
              aria-label={`Public RTSP URL for ${camera.name}`}
              className="min-w-0 flex-1 rounded border border-slate-300 px-2 py-1 text-xs"
              value={rtspOverrides[camera.id] ?? camera.rtsp_url_override ?? ''}
              onChange={(event) =>
                setRtspOverrides({ ...rtspOverrides, [camera.id]: event.target.value })
              }
              placeholder="Public RTSP URL override"
            />
            <button
              type="button"
              className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700"
              disabled={updateRtspMutation.isPending}
              onClick={() =>
                updateRtspMutation.mutate({
                  cameraId: camera.id,
                  value: (rtspOverrides[camera.id] ?? camera.rtsp_url_override ?? '') || null,
                })
              }
            >
              Save RTSP
            </button>
          </div>
          <ul className="mt-1 space-y-1">
            {camera.stream_profiles.map((profile) => {
              const isOpen =
                openProfile?.cameraId === camera.id && openProfile.profileId === profile.onvif_token;
              return (
                <li key={profile.id} className="text-xs text-slate-400">
                  <div className="flex items-center gap-2">
                    <span>
                      {profile.name}: {profile.resolution} @ {profile.fps}fps,{' '}
                      {profile.bitrate_kbps}kbps ({profile.codec})
                    </span>
                    {profile.onvif_token && (
                      <button
                        type="button"
                        className="text-slate-500 underline hover:text-slate-700"
                        onClick={() =>
                          setOpenProfile(
                            isOpen
                              ? null
                              : { cameraId: camera.id, profileId: profile.onvif_token as string },
                          )
                        }
                      >
                        {isOpen ? 'Hide config' : 'Configure'}
                      </button>
                    )}
                  </div>
                  {isOpen && profile.onvif_token && (
                    <div className="mt-2">
                      <ConfigPanel cameraId={camera.id} profileId={profile.onvif_token} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </li>
      ))}
    </ul>
  );
}

export default CameraList;
