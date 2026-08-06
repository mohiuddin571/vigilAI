import type { ReactNode } from 'react';

interface PanelProps {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** Shared card/section chrome (`components/` per docs/FOLDER_STRUCTURE.md) —
 * extracted from the border/padding/shadow classes repeated across every
 * section of the pre-M14 `App.tsx`. */
function Panel({ title, description, actions, children, className = '' }: PanelProps) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white p-6 shadow-sm ${className}`}>
      {(title || actions) && (
        <div className="flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-lg font-semibold text-slate-900">{title}</h2>}
            {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      {!title && description && <p className="mb-4 text-sm text-slate-500">{description}</p>}
      <div className={title || actions ? 'mt-4' : ''}>{children}</div>
    </section>
  );
}

export default Panel;
