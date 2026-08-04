import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { ApiError, getCameraConfig, updateCameraConfig } from '../../services/camerasApi';

interface ConfigPanelProps {
  cameraId: string;
  profileId: string;
}

function parseResolution(value: string): { width: number; height: number } {
  const [width, height] = value.split('x').map(Number);
  return { width, height };
}

function ConfigPanel({ cameraId, profileId }: ConfigPanelProps) {
  const queryClient = useQueryClient();
  const queryKey = ['camera-config', cameraId, profileId];

  const { data, isLoading, isError } = useQuery({
    queryKey,
    queryFn: () => getCameraConfig(cameraId, profileId),
  });

  const [resolution, setResolution] = useState('');
  const [bitrateKbps, setBitrateKbps] = useState('');
  const [fps, setFps] = useState('');

  useEffect(() => {
    if (!data) return;
    setResolution(data.resolution);
    setBitrateKbps(String(data.bitrate_kbps));
    setFps(String(data.fps));
  }, [data]);

  const mutation = useMutation({
    mutationFn: () =>
      updateCameraConfig(cameraId, profileId, {
        resolution: parseResolution(resolution),
        bitrate_kbps: Number(bitrateKbps),
        fps: Number(fps),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  if (isLoading) return <p className="text-sm text-slate-500">Loading configuration…</p>;
  if (isError || !data) {
    return <p className="text-sm text-red-600">Failed to load camera configuration.</p>;
  }

  const capabilities = data.capabilities;

  return (
    <form
      className="space-y-3 rounded border border-slate-200 bg-slate-50 p-3"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <p className="text-xs text-slate-500">
        Codec: <span className="font-medium text-slate-700">{data.codec}</span> (not editable —
        the camera does not report codec-switching support for this profile)
      </p>

      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          Resolution
          <select
            className="rounded border border-slate-300 px-2 py-1"
            value={resolution}
            onChange={(event) => setResolution(event.target.value)}
          >
            {(capabilities?.resolutions ?? [data.resolution]).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-600">
          FPS
          <input
            type="number"
            className="rounded border border-slate-300 px-2 py-1"
            value={fps}
            min={capabilities?.fps_min}
            max={capabilities?.fps_max}
            onChange={(event) => setFps(event.target.value)}
          />
          {capabilities && (
            <span className="text-xs text-slate-400">
              Supported: {capabilities.fps_min}–{capabilities.fps_max}
            </span>
          )}
        </label>

        <label className="col-span-2 flex flex-col gap-1 text-sm text-slate-600">
          Bitrate (kbps)
          <input
            type="number"
            className="rounded border border-slate-300 px-2 py-1"
            value={bitrateKbps}
            min={capabilities?.bitrate_min_kbps ?? undefined}
            max={capabilities?.bitrate_max_kbps ?? undefined}
            onChange={(event) => setBitrateKbps(event.target.value)}
          />
          {capabilities?.bitrate_min_kbps != null && capabilities.bitrate_max_kbps != null && (
            <span className="text-xs text-slate-400">
              Supported: {capabilities.bitrate_min_kbps}–{capabilities.bitrate_max_kbps}
            </span>
          )}
        </label>
      </div>

      <button
        type="submit"
        disabled={mutation.isPending}
        className="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
      >
        {mutation.isPending ? 'Saving…' : 'Save changes'}
      </button>

      {mutation.isError && (
        <p className="text-sm text-red-600">
          {mutation.error instanceof ApiError
            ? mutation.error.message
            : 'Failed to update camera configuration.'}
        </p>
      )}
      {mutation.isSuccess && <p className="text-sm text-emerald-600">Configuration updated.</p>}
    </form>
  );
}

export default ConfigPanel;
