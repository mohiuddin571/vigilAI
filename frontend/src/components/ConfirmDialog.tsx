import Dialog from './Dialog';

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  isPending?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Shared destructive-action confirm dialog (`components/`) — camera delete, recording
 * delete, and clear-events all reuse this rather than each hand-rolling a `window.confirm`. */
function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Delete',
  isPending = false,
  error,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Dialog title={title} onClose={onCancel}>
      <p className="text-sm text-slate-600">{message}</p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={isPending}
          className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {isPending ? 'Working…' : confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}

export default ConfirmDialog;
