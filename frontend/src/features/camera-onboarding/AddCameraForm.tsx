import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { ApiError, createCamera } from '../../services/camerasApi';

const initialFormState = { ipAddress: '', port: '80', username: '', password: '', rtspUrlOverride: '' };

function AddCameraForm() {
  const [form, setForm] = useState(initialFormState);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      createCamera({
        ip_address: form.ipAddress,
        port: Number(form.port) || 80,
        username: form.username,
        password: form.password,
        rtsp_url_override: form.rtspUrlOverride || null,
      }),
    onSuccess: () => {
      setForm(initialFormState);
      void queryClient.invalidateQueries({ queryKey: ['cameras'] });
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
        <label className="col-span-2 flex flex-col gap-1 text-sm text-slate-600 sm:col-span-1">
          IP address
          <input
            required
            className="rounded border border-slate-300 px-2 py-1"
            value={form.ipAddress}
            onChange={(event) => setForm({ ...form, ipAddress: event.target.value })}
            placeholder="192.168.1.64"
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
        <label className="col-span-2 flex flex-col gap-1 text-sm text-slate-600">
          Public RTSP URL override (optional)
          <input
            className="rounded border border-slate-300 px-2 py-1"
            value={form.rtspUrlOverride}
            onChange={(event) => setForm({ ...form, rtspUrlOverride: event.target.value })}
            placeholder="rtsp://public-host:port/path"
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
          Password
          <input
            required
            type="password"
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
        {mutation.isPending ? 'Connecting…' : 'Add camera'}
      </button>

      {mutation.isError && (
        <p className="text-sm text-red-600">
          {mutation.error instanceof ApiError
            ? mutation.error.message
            : 'Failed to onboard camera.'}
        </p>
      )}
    </form>
  );
}

export default AddCameraForm;
