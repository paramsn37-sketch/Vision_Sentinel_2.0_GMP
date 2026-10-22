import { ScanSearch, X } from 'lucide-react'
import { Button, IconButton, StatusPill } from '@/components/ui'
import type { FrameMeta } from '@/lib/api/types'
import { duration, ppeLabel, ruleLabel } from '@/lib/format'

/** The selected person on a camera: time seen, zones, PPE state, open violations, and "explain". */
export function TrackCard({
  meta,
  trackId,
  paused,
  onExplain,
  onClose,
}: {
  meta: FrameMeta | null
  trackId: number
  paused: boolean
  onExplain: () => void
  onClose: () => void
}) {
  const p = meta?.persons.find((x) => x.track_id === trackId)
  const zoneName = (id: string) => meta?.zones.find((z) => z.id === id)?.name ?? id
  return (
    <section className="flex flex-col gap-3 border-b border-line px-4 py-4" aria-label={`Person ${trackId}`}>
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">
          Person <span className="num">#{trackId}</span>
        </h2>
        <IconButton size="sm" label="Clear selection" onClick={onClose}>
          <X className="size-4" />
        </IconButton>
      </header>
      {!p ? (
        <p className="text-sm text-muted">Not in the current frame. They may have left the view; the ID is kept for a few seconds.</p>
      ) : (
        <>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
            <dt className="text-muted">Seen for</dt>
            <dd className="num">{duration(p.since_s)}</dd>
            <dt className="text-muted">Confidence</dt>
            <dd className="num">{(p.conf * 100).toFixed(0)}%</dd>
            <dt className="text-muted">Zones</dt>
            <dd>{p.zones.length ? p.zones.map(zoneName).join(', ') : 'none'}</dd>
          </dl>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(p.ppe).map(([item, state]) => (
              <StatusPill key={item} tone={state === 'present' ? 'ok' : state === 'absent' ? 'danger' : 'neutral'}>
                {state === 'present' ? ppeLabel(item) : state === 'absent' ? `No ${ppeLabel(item)}` : `${ppeLabel(item)}: not visible`}
              </StatusPill>
            ))}
            {Object.keys(p.ppe).length === 0 && <span className="text-xs text-muted">The active model does not detect PPE.</span>}
          </div>
          {p.violations.length > 0 && (
            <ul className="flex flex-col gap-1 text-sm text-danger">
              {p.violations.map((v) => (
                <li key={v}>{ruleLabel(v)}</li>
              ))}
            </ul>
          )}
          <Button size="sm" icon={<ScanSearch className="size-4" />} onClick={onExplain} disabled={!paused} title={paused ? undefined : 'Pause the camera first, so the explanation is for the frame you see'}>
            Explain this detection
          </Button>
          {!paused && <p className="-mt-1 text-xs text-subtle">Pause the camera to explain the frame you are looking at.</p>}
        </>
      )}
    </section>
  )
}
