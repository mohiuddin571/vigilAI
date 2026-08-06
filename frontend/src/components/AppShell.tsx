import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { analyticsEventsWebSocketUrl } from '../services/analyticsApi';
import useUiStore from '../store/uiStore';

interface NavItem {
  to: string;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Cameras' },
  { to: '/recordings', label: 'Recordings' },
  { to: '/events', label: 'Event Center' },
];

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center justify-between rounded px-3 py-2 text-sm font-medium ${
    isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
  }`;

/**
 * Persistent sidebar + topbar shell (T-140) wrapping every routed page via
 * `<Outlet />`. `components/` owns "shared, feature-agnostic UI primitives...
 * layout shell" per docs/FOLDER_STRUCTURE.md, so this depends only on
 * `services/`/`store/`/`types/`, never on a `features/` folder.
 *
 * Also owns the one background subscription to `/ws/analytics/events` that
 * drives the Event Center nav badge (docs/UI_UX_DESIGN.md §5.8) — a purely
 * client-side unread counter, since no backend notification system exists.
 * The counter only increments while the user isn't already on `/events`
 * (where the live feed is visible directly) and clears on arrival there.
 */
function AppShell() {
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const unreadEventCount = useUiStore((state) => state.unreadEventCount);
  const recordUnreadEvents = useUiStore((state) => state.recordUnreadEvents);
  const clearUnreadEvents = useUiStore((state) => state.clearUnreadEvents);
  const onEventCenter = location.pathname === '/events';

  useEffect(() => {
    if (onEventCenter) {
      clearUnreadEvents();
      return;
    }
    const socket = new WebSocket(analyticsEventsWebSocketUrl());
    socket.onmessage = () => recordUnreadEvents(1);
    return () => socket.close();
  }, [onEventCenter, recordUnreadEvents, clearUnreadEvents]);

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside
        className={`fixed inset-y-0 left-0 z-20 w-56 shrink-0 border-r border-slate-200 bg-white p-4 transition-transform sm:static sm:translate-x-0 ${
          mobileNavOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <h1 className="px-3 text-lg font-semibold text-slate-900">VigilAI</h1>
        <nav className="mt-6 space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={navLinkClass}
              onClick={() => setMobileNavOpen(false)}
            >
              <span>{item.label}</span>
              {item.to === '/events' && unreadEventCount > 0 && (
                <span className="rounded-full bg-emerald-500 px-2 py-0.5 text-xs font-semibold text-white">
                  {unreadEventCount > 99 ? '99+' : unreadEventCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>

      {mobileNavOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-10 bg-black/30 sm:hidden"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 sm:hidden">
          <button
            type="button"
            aria-label="Open navigation"
            onClick={() => setMobileNavOpen(true)}
            className="rounded border border-slate-300 px-2 py-1 text-sm text-slate-700"
          >
            ☰
          </button>
          <span className="text-base font-semibold text-slate-900">VigilAI</span>
        </header>

        <main className="flex-1 overflow-x-hidden p-4 sm:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AppShell;
