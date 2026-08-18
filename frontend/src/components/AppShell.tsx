import { useEffect, useRef } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  IconAsk,
  IconAudit,
  IconDrilldown,
  IconGovernance,
  IconLogout,
  IconMap,
  IconOverview,
  IconTrends,
} from './icons'

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: IconOverview, end: true },
  { to: '/trends', label: 'Trends', icon: IconTrends },
  { to: '/map', label: 'Map', icon: IconMap },
  { to: '/ask', label: 'Ask a question', icon: IconAsk },
  { to: '/drilldown', label: 'Drill-down', icon: IconDrilldown },
]

const ADMIN_NAV_ITEMS = [
  { to: '/governance', label: 'Data quality & governance', icon: IconGovernance },
  { to: '/audit-log', label: 'Audit log', icon: IconAudit },
]

export function AppShell() {
  const { user, logout } = useAuth()
  const mainRef = useRef<HTMLElement>(null)
  useScrollToTopOnNavigate(mainRef)

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-canvas text-ink">
      <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-surface">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent text-sm font-bold text-white">
            N
          </div>
          <div>
            <div className="text-sm font-semibold leading-tight text-ink">NavyBI</div>
            <div className="text-[11px] leading-tight text-ink-faint">Post-mission analytics</div>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 px-3">
          {NAV_ITEMS.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}

          {user?.role === 'admin' && (
            <>
              <div className="mt-4 mb-1 px-3 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
                Admin
              </div>
              {ADMIN_NAV_ITEMS.map((item) => (
                <NavItem key={item.to} {...item} />
              ))}
            </>
          )}
        </nav>

        <div className="border-t border-border px-3 py-3">
          <div className="flex items-center gap-2 rounded-md px-2 py-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
              {user?.display_name?.slice(0, 1) ?? '?'}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-ink">{user?.display_name}</div>
              <div className="truncate text-[11px] capitalize text-ink-faint">{user?.role}</div>
            </div>
            <button
              onClick={() => logout()}
              title="Sign out"
              className="flex h-8 w-8 items-center justify-center rounded-md text-ink-muted hover:bg-canvas hover:text-ink"
            >
              <IconLogout />
            </button>
          </div>
        </div>
      </aside>

      <main ref={mainRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1400px] px-8 py-7">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

function useScrollToTopOnNavigate(ref: React.RefObject<HTMLElement | null>) {
  const { pathname } = useLocation()
  useEffect(() => {
    ref.current?.scrollTo(0, 0)
  }, [pathname, ref])
}

function NavItem({
  to,
  label,
  icon: Icon,
  end,
}: {
  to: string
  label: string
  icon: (props: { className?: string }) => React.JSX.Element
  end?: boolean
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
          isActive
            ? 'bg-accent-soft text-accent'
            : 'text-ink-muted hover:bg-canvas hover:text-ink'
        }`
      }
    >
      <Icon />
      <span className="truncate">{label}</span>
    </NavLink>
  )
}
