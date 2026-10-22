import { useMemo } from 'react'
import { Skeleton } from '@/components/ui'
import type { TimePoint } from '@/lib/api/types'
import { toDate } from '@/lib/format'

/** The shift strip: people on site per minute (peak) with each incident marked at its minute.
 *  Bars are the measured per-minute peaks from counts_minutely; nothing is smoothed or sampled. */
export function ShiftStrip({ points, height = 64, loading }: { points: TimePoint[] | undefined; height?: number; loading?: boolean }) {
  const { max, peak, first, last } = useMemo(() => {
    const p = points ?? []
    const peak = Math.max(0, ...p.map((x) => x.peak_people))
    return {
      max: Math.max(1, peak),
      peak,
      first: p[0]?.t,
      last: p[p.length - 1]?.t,
    }
  }, [points])
  if (loading || !points) return <Skeleton className="w-full" />
  const n = points.length
  const w = 100 / Math.max(1, n)
  const incidents = points.reduce((a, p) => a + p.incidents, 0)
  const fmt = (t?: string) => (t ? toDate(t).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : '')
  return (
    <figure className="flex flex-col gap-1">
      <svg
        viewBox={`0 0 100 ${height}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
        role="img"
        aria-label={`People on site per minute, peak ${peak}; ${incidents} incidents in this window`}
      >
        <line x1="0" x2="100" y1={height - 0.5} y2={height - 0.5} stroke="var(--line)" vectorEffect="non-scaling-stroke" />
        {points.map((p, i) =>
          p.peak_people > 0 ? (
            <rect key={p.t} x={i * w} width={Math.max(w - 0.05, 0.05)} y={height - (p.peak_people / max) * (height - 10)} height={(p.peak_people / max) * (height - 10)} fill="var(--fg-muted)" opacity={0.55}>
              <title>{`${fmt(p.t)} · peak ${p.peak_people} people${p.incidents ? ` · ${p.incidents} incident(s)` : ''}`}</title>
            </rect>
          ) : null,
        )}
        {points.map((p, i) =>
          p.incidents > 0 ? (
            <rect key={`i${p.t}`} x={i * w} width={Math.max(w, 0.35)} y={0} height={6} fill="var(--danger)">
              <title>{`${fmt(p.t)} · ${p.incidents} incident(s) opened`}</title>
            </rect>
          ) : null,
        )}
      </svg>
      <figcaption className="flex justify-between text-xs text-muted">
        <span className="num">{fmt(first)}</span>
        <span>
          peak <span className="num text-fg">{peak}</span> at once · <span className="num text-fg">{incidents}</span> incidents
        </span>
        <span className="num">{fmt(last)}</span>
      </figcaption>
    </figure>
  )
}
