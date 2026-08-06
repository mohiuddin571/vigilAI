import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { ApiError, updateCamera } from '../../services/camerasApi';
import type { CameraResponse } from '../../types/camera';

interface EditCameraFormProps {
  camera: CameraResponse;
  onSuccess?: () => void;
}

/** Edit a camera's name/IP/port/username/password (T-170) — a plain field update, no
 * re-authentication against the camera (docs/TECHNICAL_DECISIONS.md TD-32 decision 4);
 * password is left blank and omitted from the request unless the operator types a new one. */
function EditCameraForm({ camera, onSuccess }: EditCameraFormProps) {
  const [form, setForm] = useState({
    name: camera.name,
    ipAddress: camera.ip_address,
    port: String(camera.port),
    username: camera.username,
    password: '',
  });
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      updateCamera(camera.id, {
        name: form.name,
        ip_address: form.ipAddress,
        port: Number(form.port) || camera.port,
        username: form.username,
        ...(form.password ? { password: form.password } : {}),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['cameras'] });
      void queryClient.invalidateQueries({ queryKey: ['camera', camera.id] });
      onSuccess?.();
    },
  });

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <div className="grid grid-cols-2 gap-3">
        <label className="col-span-2 flex flex-col gap-1 text-sm text-slate-600">
          Name
          <input
            required
            className="rounded border border-slate-300 px-2 py-1"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          IP address
          <input
            required
            className="rounded border border-slate-300 px-2 py-1"
            value={form.ipAddress}
            onChange={(event) => setForm({ ...form, ipAddress: event.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          Port
          <input
            className="rounded border border-slate-300 px-2 py-1"
            value={form.port}
            onChange={(event) => setForm({ ...form, port: event.target.value })}
            inputMode="numeric"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          Username
          <input
            required
            className="rounded border border-slate-300 px-2 py-1"
            value={form.username}
            onChange={(event) => setForm({ ...form, username: event.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-600">
          New password (optional)
          <input
            type="password"
            placeholder="Leave blank to keep current"
            className="rounded border border-slate-300 px-2 py-1"
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
          />
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
            : 'Failed to update camera.'}
        </p>
      )}
    </form>
  );
}

export default EditCameraForm;
