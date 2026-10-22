import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Kbd, cn } from '@/components/ui'
import { useHealth, useSummary } from '@/lib/api/hooks'
import type { AlertLevel } from '@/lib/api/types'
import { startOfToday } from '@/lib/format'
import { useLive } from '@/stores/live'
import { useUI } from '@/stores/ui'

const LEVEL: Record<AlertLevel, { label: string; cls: string; dot: string }> = {
  green: { label: 'Normal', cls: 'text-ok', dot: 'bg-ok' },
  amber: { label: 'Warning', cls: 'text-warning', dot: 'bg-warning' },
  red: { label: 'Danger', cls: 'text-danger', dot: 'bg-danger' },
}

function Item({ label, children, title }: { label: string; children: React.ReactNode; title?: string }) {
  return (
    <div className="flex items-baseline gap-1.5 whitespace-nowrap" title={title}>
      <span className="text-xs text-muted">{label}</span>
      <span className="num text-sm text-fg">{children}</span>
    </div>
  )
}

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <time className="num text-sm text-muted" dateTime={now.toISOString()}>
      {now.toLocaleTimeString('en-GB')}
    </time>
  )
}

export function StatusStrip() {
  const [since] = useState(startOfToday)
  const summary = useSummary({ since }).data
  const health = useHealth().data
  const lastAlertAt = useLive((s) => s.lastAlertAt)
  const setPalette = useUI((s) => s.setPalette)
  const level = LEVEL[summary?.alert_level ?? 'green']
  const fps = health ? Object.values(health.cameras).filter((c) => c.status === 'running') : []
  const meanFps = fps.length ? fps.reduce((a, c) => a + c.fps, 0) / fps.length : null

  return (
    <header className="flex h-(--strip-height) shrink-0 items-center gap-6 border-b border-line bg-bg px-4">
      <div
        key={lastAlertAt}
        className={cn('-ml-2 flex h-7 items-center gap-2 rounded-sm px-2', lastAlertAt > 0 && 'vs-pulse-once')}
        role="status"
        aria-live="polite"
      >
        <span className={cn('size-2 rounded-full', level.dot)} aria-hidden />
        <span className="text-xs text-muted">Site</span>
        <span className={cn('text-sm font-medium', level.cls)}>{level.label}</span>
      </div>
      <Item label="Cameras">
        {summary ? `${summary.cameras_online}/${summary.cameras_total}` : '—'}
      </Item>
      <Item label="People now">{summary?.people_now ?? '—'}</Item>
      <Item label="Unique today" title="Distinct confirmed people since midnight, all cameras">
        {summary?.unique_people ?? '—'}
      </Item>
      <Item label="Open incidents">
        {summary ? (
          <>
            {summary.open_incidents}
            {summary.open_high > 0 && <span className="ml-1 text-danger">({summary.open_high} high)</span>}
          </>
        ) : (
          '—'
        )}
      </Item>
      <div className="ml-auto flex items-center gap-6">
        <Item label="Model" title={health?.model_error ?? undefined}>
          <span className="font-sans">{health?.model ?? (health ? 'not loaded' : '—')}</span>
        </Item>
        <Item label="Avg fps">{meanFps === null ? '—' : meanFps.toFixed(1)}</Item>
        <button
          type="button"
          onClick={() => setPalette(true)}
          className="press flex h-7 items-center gap-2 rounded-sm border border-line px-2 text-xs text-muted hover:bg-hover hover:text-fg"
        >
          <Search className="size-3.5" aria-hidden />
          Go to
          <Kbd>⌘K</Kbd>
        </button>
        <Clock />
      </div>
    </header>
  )
}
