import { ChevronsLeft, ChevronsRight, LogOut, Moon, Sun } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { cn, Tooltip } from '@/components/ui'
import { useUI } from '@/stores/ui'
import { Mark } from './Mark'
import { NAV } from './nav'

function RailButton({ label, onClick, children, open }: { label: string; onClick: () => void; children: React.ReactNode; open: boolean }) {
  const btn = (
    <button
      type="button"
      onClick={onClick}
      aria-label={open ? undefined : label}
      className="press flex h-9 w-full items-center gap-3 rounded-sm px-[10px] text-muted transition-colors duration-(--dur-fast) hover:bg-hover hover:text-fg"
    >
      {children}
      {open && <span className="truncate text-sm">{label}</span>}
    </button>
  )
  return open ? btn : <Tooltip content={label} side="right">{btn}</Tooltip>
}

export function Rail({ onLogout, openCount }: { onLogout: () => void; openCount: number }) {
  const { railOpen, toggleRail, theme, setTheme } = useUI()
  const { pathname } = useLocation()
  return (
    <nav
      aria-label="Main"
      className={cn(
        'flex shrink-0 flex-col border-r border-line bg-bg px-2 py-3 transition-[width] duration-(--dur-ui) ease-out',
        railOpen ? 'w-(--rail-width-open)' : 'w-(--rail-width)',
      )}
    >
      <div className="mb-4 flex h-8 items-center gap-2.5 px-[8px] text-fg">
        <Mark />
        {railOpen && <span className="truncate text-sm font-semibold">Vision Sentinel</span>}
      </div>
      <ul className="flex flex-col gap-1">
        {NAV.map(({ to, label, icon: Icon, key }) => {
          // A plain string className: the tooltip trigger (Radix Slot) merges class names as strings.
          const isActive = pathname === to || pathname.startsWith(`${to}/`)
          const link = (
            <Link
              to={to}
              aria-label={to === '/incidents' && openCount > 0 ? `${label}, ${openCount > 99 ? '99+' : openCount} open` : railOpen ? undefined : label}
              aria-current={isActive ? 'page' : undefined}
              className={cn(
                  'relative flex h-9 items-center gap-3 rounded-sm px-[10px] transition-colors duration-(--dur-fast)',
                  isActive ? 'text-fg' : 'text-muted hover:bg-hover hover:text-fg',
                  // The selection line: 1 px on the rail's inner edge, as tall as the label.
                  isActive && 'after:absolute after:top-2 after:-right-2 after:bottom-2 after:w-px after:bg-accent',
                )}
            >
              <Icon className="size-5 shrink-0" strokeWidth={1.75} aria-hidden />
              {railOpen && <span className="flex-1 truncate text-sm">{label}</span>}
              {to === '/incidents' && openCount > 0 && (
                <span
                  className={cn(
                    'num rounded-sm bg-danger-bg px-1 text-[11px] leading-4 text-danger',
                    !railOpen && 'absolute -top-1 left-[22px]',
                  )}
                  aria-hidden
                >
                  {openCount > 99 ? '99+' : openCount}
                </span>
              )}
            </Link>
          )
          return (
            <li key={to}>
              {railOpen ? link : <Tooltip content={label} shortcut={`g ${key}`} side="right">{link}</Tooltip>}
            </li>
          )
        })}
      </ul>
      <div className="mt-auto flex flex-col gap-1">
        <RailButton open={railOpen} label={theme === 'dark' ? 'Light theme' : 'Dark theme'} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
          {theme === 'dark' ? <Sun className="size-5 shrink-0" strokeWidth={1.75} /> : <Moon className="size-5 shrink-0" strokeWidth={1.75} />}
        </RailButton>
        <RailButton open={railOpen} label="Sign out" onClick={onLogout}>
          <LogOut className="size-5 shrink-0" strokeWidth={1.75} />
        </RailButton>
        <RailButton open={railOpen} label={railOpen ? 'Collapse menu' : 'Expand menu'} onClick={toggleRail}>
          {railOpen ? <ChevronsLeft className="size-5 shrink-0" strokeWidth={1.75} /> : <ChevronsRight className="size-5 shrink-0" strokeWidth={1.75} />}
        </RailButton>
      </div>
    </nav>
  )
}
