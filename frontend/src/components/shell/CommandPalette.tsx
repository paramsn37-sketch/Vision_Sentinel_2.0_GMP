import * as D from '@radix-ui/react-dialog'
import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { cn, Kbd } from '@/components/ui'
import { useUI } from '@/stores/ui'
import { NAV } from './nav'

interface Command {
  id: string
  label: string
  hint?: string
  run: () => void
}

export function CommandPalette({ onLogout }: { onLogout: () => void }) {
  const { paletteOpen, setPalette, theme, setTheme, toggleRail } = useUI()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)

  const commands = useMemo<Command[]>(() => {
    const go = (to: string) => () => navigate(to)
    const list: Command[] = [
      ...NAV.map((n) => ({ id: n.to, label: `Go to ${n.label}`, hint: `g ${n.key}`, run: go(n.to) })),
      { id: 'open', label: 'Show open incidents', run: go('/incidents?status=open') },
      { id: 'zone-new', label: 'Draw a new zone', run: go('/zones?new=1') },
      { id: 'upload', label: 'Analyse a file', run: go('/uploads') },
      { id: 'theme', label: theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme', run: () => setTheme(theme === 'dark' ? 'light' : 'dark') },
      { id: 'rail', label: 'Toggle menu labels', hint: '[', run: toggleRail },
      { id: 'logout', label: 'Sign out', run: onLogout },
    ]
    if (/^inc_[\w-]+$/.test(q.trim())) list.unshift({ id: 'inc', label: `Open incident ${q.trim()}`, run: go(`/incidents?id=${q.trim()}`) })
    return list
  }, [navigate, theme, setTheme, toggleRail, onLogout, q])

  const shown = commands.filter((c) => c.label.toLowerCase().includes(q.trim().toLowerCase()) || c.id === 'inc')
  const close = () => {
    setPalette(false)
    setQ('')
    setActive(0)
  }
  const run = (c: Command | undefined) => {
    if (!c) return
    close()
    c.run()
  }

  return (
    <D.Root open={paletteOpen} onOpenChange={(v) => (v ? setPalette(true) : close())}>
      <D.Portal>
        <D.Overlay className="vs-fade fixed inset-0 z-40 bg-(--scrim)" />
        <D.Content
          aria-label="Command palette"
          className="vs-pop fixed top-[18vh] left-1/2 z-50 w-[min(92vw,560px)] -translate-x-1/2 overflow-hidden rounded-md border border-line bg-raised shadow-float outline-none"
        >
          <D.Title className="sr-only">Go to or run a command</D.Title>
          <D.Description className="sr-only">Type to filter, arrow keys to choose, Enter to run.</D.Description>
          <div className="flex items-center gap-2 border-b border-line px-3">
            <Search className="size-4 text-muted" aria-hidden />
            <input
              autoFocus
              value={q}
              onChange={(e) => {
                setQ(e.target.value)
                setActive(0)
              }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') {
                  e.preventDefault()
                  setActive((a) => Math.min(a + 1, shown.length - 1))
                } else if (e.key === 'ArrowUp') {
                  e.preventDefault()
                  setActive((a) => Math.max(a - 1, 0))
                } else if (e.key === 'Enter') run(shown[active])
              }}
              placeholder="Go to a screen, run an action, or paste an incident ID"
              aria-label="Command"
              aria-controls="vs-cmd-list"
              className="h-11 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-subtle"
            />
          </div>
          <ul id="vs-cmd-list" role="listbox" className="max-h-80 overflow-y-auto p-1">
            {shown.length === 0 && <li className="px-3 py-3 text-sm text-muted">No command matches “{q}”.</li>}
            {shown.map((c, i) => (
              <li
                key={c.id}
                role="option"
                aria-selected={i === active}
                onMouseMove={() => setActive(i)}
                onClick={() => run(c)}
                className={cn('flex h-9 cursor-default items-center justify-between rounded-sm px-3 text-sm', i === active ? 'bg-hover text-fg' : 'text-muted')}
              >
                {c.label}
                {c.hint && <Kbd>{c.hint}</Kbd>}
              </li>
            ))}
          </ul>
        </D.Content>
      </D.Portal>
    </D.Root>
  )
}
