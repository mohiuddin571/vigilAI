import type { ReactNode } from 'react';

/** Small presentation helpers shared by the RTMP Demo's four panels only —
 * kept inside `features/rtmp-demo/` rather than promoted to `components/`,
 * since nothing outside this isolated feature uses them (docs/RTMP_DEMO.md). */

export function StatusRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className="flex items-center gap-1.5 text-slate-800">{children}</span>
    </div>
  );
}

export function StateDot({ ok }: { ok: boolean }) {
  return <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${ok ? 'bg-emerald-500' : 'bg-slate-300'}`} />;
}
