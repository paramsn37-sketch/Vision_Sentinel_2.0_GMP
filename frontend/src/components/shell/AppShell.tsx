import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { Outlet, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { api } from '@/lib/api/client'
import { keys, useSummary } from '@/lib/api/hooks'
import type { IncidentEvent } from '@/lib/api/types'
import { ruleLabel } from '@/lib/format'
import { connectEvents } from '@/lib/ws'
import { useLive } from '@/stores/live'
import { useUI } from '@/stores/ui'
import { CommandPalette } from './CommandPalette'
import { NAV } from './nav'
import { Rail } from './Rail'
import { StatusStrip } from './StatusStrip'

/** Keyboard: ⌘K palette, `g <n>` to jump to a screen, `[` to toggle the rail. Ignored while typing. */
function useGlobalKeys() {
  const navigate = useNavigate()
  const { setPalette, toggleRail } = useUI()
  const pendingG = useRef(0)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPalette(true)
        return
      }
      const t = e.target as HTMLElement
      if (e.metaKey || e.ctrlKey || e.altKey || t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return
      if (e.key === 'g') {
        pendingG.current = Date.now()
        return
      }
      if (Date.now() - pendingG.current < 1200) {
        const item = NAV.find((n) => n.key === e.key)
        pendingG.current = 0
        if (item) {
          e.preventDefault()
          navigate(item.to)
        }
        return
      }
      if (e.key === '[') toggleRail()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, setPalette, toggleRail])
}

/** One events socket for the app: feeds the live store, refreshes queries, and toasts new incidents (grouped). */
function useEventStream() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { pushIncident, setEventsState } = useLive()
  useEffect(() => {
    let burst: IncidentEvent[] = []
    let timer: ReturnType<typeof setTimeout> | undefined
    const flush = () => {
      const opened = burst
      burst = []
      if (opened.length === 1) {
        const i = opened[0].incident
        const fn = i.severity === 'high' ? toast.error : toast.warning
        fn(ruleLabel(i.rule), {
          id: i.id,
          description: [i.zone_name, i.track_id !== null ? `person #${i.track_id}` : null].filter(Boolean).join(' · '),
          action: { label: 'Open', onClick: () => navigate(`/incidents?id=${i.id}`) },
        })
      } else if (opened.length > 1) {
        toast.warning(`${opened.length} new incidents`, {
          id: 'incident-burst',
          action: { label: 'View', onClick: () => navigate('/incidents?status=open') },
        })
      }
    }
    const conn = connectEvents(
      (e) => {
        if (e.type === 'incident') {
          const ev = e as IncidentEvent
          pushIncident(ev)
          qc.invalidateQueries({ queryKey: ['incidents'] })
          qc.invalidateQueries({ queryKey: ['summary'] })
          if (ev.kind === 'opened' && ev.incident.severity !== 'low') {
            burst.push(ev)
            clearTimeout(timer)
            timer = setTimeout(flush, 600)
          }
        } else if (e.type === 'upload') {
          qc.invalidateQueries({ queryKey: keys.uploads })
        } else if (e.type === 'incident_xai') {
          qc.invalidateQueries({ queryKey: ['incident'] })
        } else if (e.type === 'system') {
          toast.error('System problem', { description: String(e.message), duration: Infinity })
        }
      },
      (s) => {
        setEventsState(s)
        if (s === 'unauthorized') navigate('/login')
      },
    )
    return () => {
      clearTimeout(timer)
      conn.close()
    }
  }, [qc, navigate, pushIncident, setEventsState])
}

export function AppShell() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  useGlobalKeys()
  useEventStream()
  const open = useSummary().data?.open_incidents ?? 0
  const logout = async () => {
    await api.post('/auth/logout').catch(() => undefined)
    qc.clear()
    navigate('/login')
  }
  return (
    <div className="flex h-full">
      <Rail onLogout={logout} openCount={open} />
      <div className="flex min-w-0 flex-1 flex-col">
        <StatusStrip />
        <main className="min-h-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
      <CommandPalette onLogout={logout} />
    </div>
  )
}
