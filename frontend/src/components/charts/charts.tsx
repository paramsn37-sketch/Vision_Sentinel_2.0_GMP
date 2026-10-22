// Small SVG charts following DESIGN.md §8 and the dataviz method: one series per chart (no dual axes), y-scale and
// dates always shown, 3–5 faint gridlines, thin marks with 4 px rounded data ends, hover tooltip on every mark,
// and a table view for screen readers. No chart library: these are ~100 lines and weigh nothing.
import { useId, useMemo, useRef, useState, type ReactNode } from 'react'
import { cn } from '@/components/ui'

export interface Point {
  t: string // ISO time
  v: number | null // null = no data for this bucket (drawn as a gap, never as zero)
}

const niceMax = (m: number) => {
  if (m <= 4) return Math.max(1, Math.ceil(m))
  const p = 10 ** Math.floor(Math.log10(m))
  const n = m / p
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p
}
const ticks = (max: number) => {
  const step = max <= 4 ? 1 : max / 4
  return Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step)
}

function useWidth() {
  const ref = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(600)
  const cb = useMemo(
    () => (el: HTMLDivElement | null) => {
      ;(ref as React.MutableRefObject<HTMLDivElement | null>).current = el
      if (!el) return
      const ro = new ResizeObserver(([e]) => setW(Math.max(200, e.contentRect.width)))
      ro.observe(el)
    },
    [],
  )
  return [cb, w] as const
}

interface ChartProps {
  data: Point[]
  label: string // what one value is, e.g. "new people"
  unit: string // axis title, e.g. "people per hour"
  height?: number
  formatX: (t: string) => string
  formatTip?: (p: Point) => ReactNode
  kind?: 'bars' | 'line'
  emptyText?: string
}

export function TimeChart({ data, label, unit, height = 200, formatX, formatTip, kind = 'bars', emptyText }: ChartProps) {
  const [ref, width] = useWidth()
  const [hover, setHover] = useState<number | null>(null)
  const id = useId()
  const pad = { l: 36, r: 8, t: 22, b: 22 } // top padding leaves room for the unit label
  const max = niceMax(Math.max(0, ...data.map((d) => d.v ?? 0)))
  const iw = width - pad.l - pad.r
  const ih = height - pad.t - pad.b
  const n = data.length
  const band = iw / Math.max(1, n)
  const x = (i: number) => pad.l + band * i + band / 2
  const y = (v: number) => pad.t + ih - (v / max) * ih
  const every = Math.max(1, Math.ceil(n / Math.max(1, Math.floor(iw / 64))))
  const total = data.reduce((a, d) => a + (d.v ?? 0), 0)
  const bw = Math.max(1, Math.min(24, band - 2))

  return (
    <div ref={ref} className="relative w-full">
      <svg width={width} height={height} role="img" aria-labelledby={`${id}-t`} onMouseLeave={() => setHover(null)}>
        <title id={`${id}-t`}>{`${label} over time, ${n} points, total ${total}`}</title>
        {ticks(max).map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={width - pad.r} y1={y(t)} y2={y(t)} stroke="var(--line)" />
            <text x={pad.l - 6} y={y(t)} dy="0.32em" textAnchor="end" className="num fill-(--fg-subtle) text-[11px]">
              {Number.isInteger(t) ? t : t.toFixed(1)}
            </text>
          </g>
        ))}
        {kind === 'bars'
          ? data.map((d, i) =>
              d.v ? (
                <path
                  key={d.t}
                  d={roundedTop(x(i) - bw / 2, y(d.v), bw, y(0) - y(d.v), Math.min(4, bw / 2))}
                  fill={hover === i ? 'var(--fg)' : 'var(--fg-muted)'}
                />
              ) : null,
            )
          : (
              <>
                <path
                  d={data.map((d, i) => (d.v === null ? '' : `${i && data[i - 1].v !== null ? 'L' : 'M'}${x(i)},${y(d.v)}`)).join('')}
                  fill="none"
                  stroke="var(--fg-muted)"
                  strokeWidth={2}
                  strokeLinejoin="round"
                />
                {/* An observed point with no observed neighbour has no line segment; mark it so it is not invisible. */}
                {data.map((d, i) =>
                  d.v !== null && data[i - 1]?.v == null && data[i + 1]?.v == null ? <circle key={d.t} cx={x(i)} cy={y(d.v)} r={3} fill="var(--fg-muted)" /> : null,
                )}
                {hover !== null && data[hover]?.v != null && <circle cx={x(hover)} cy={y(data[hover].v!)} r={4} fill="var(--fg)" stroke="var(--bg-sunken)" strokeWidth={2} />}
              </>
            )}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={pad.t + ih} stroke="var(--line-strong)" strokeDasharray="2 3" />}
        {data.map((d, i) =>
          i % every === 0 ? (
            <text key={d.t} x={x(i)} y={height - 6} textAnchor="middle" className="num fill-(--fg-subtle) text-[11px]">
              {formatX(d.t)}
            </text>
          ) : null,
        )}
        {/* hit targets: full-height bands, bigger than the marks */}
        {data.map((d, i) => (
          <rect key={`h${d.t}`} x={pad.l + band * i} y={pad.t} width={band} height={ih} fill="transparent" onMouseEnter={() => setHover(i)} />
        ))}
      </svg>
      <span className="absolute top-0 left-0 text-[11px] text-subtle" aria-hidden>
        {unit}
      </span>
      {hover !== null && data[hover] && (
        <div
          className="pointer-events-none absolute z-10 rounded-sm border border-line bg-raised px-2 py-1 text-xs shadow-float"
          style={{ left: Math.min(width - 160, Math.max(0, x(hover) + 8)), top: 8 }}
        >
          {formatTip ? formatTip(data[hover]) : (
            <>
              <span className="text-muted">{formatX(data[hover].t)}</span>{' '}
              {data[hover].v === null ? <span className="text-muted">no data (no camera running)</span> : <><span className="num text-fg">{data[hover].v}</span> {label}</>}
            </>
          )}
        </div>
      )}
      {n === 0 && <p className="absolute inset-0 grid place-items-center text-sm text-muted">{emptyText ?? 'No data in this range.'}</p>}
      <table className="sr-only">
        <caption>{label}</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.t}>
              <th scope="row">{formatX(d.t)}</th>
              <td>{d.v ?? 'no data'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function roundedTop(x: number, y: number, w: number, h: number, r: number) {
  if (h <= 0) return ''
  const rr = Math.min(r, h)
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`
}

/** Rows × 24 hours. One hue (accent) ramps with count; zero cells stay plain. */
export function HourGrid({ rows, rowLabel }: { rows: { key: string; hours: number[] }[]; rowLabel: (k: string) => string }) {
  const max = Math.max(1, ...rows.flatMap((r) => r.hours))
  const [hover, setHover] = useState<{ r: string; h: number; v: number } | null>(null)
  return (
    <div className="flex flex-col gap-1">
      <div className="grid grid-cols-[160px_repeat(24,minmax(0,1fr))] gap-[2px] text-[11px]">
        <span />
        {Array.from({ length: 24 }, (_, h) => (
          <span key={h} className="num text-center text-subtle">
            {h % 3 === 0 ? String(h).padStart(2, '0') : ''}
          </span>
        ))}
        {rows.map((r) => (
          <Row key={r.key} label={rowLabel(r.key)} hours={r.hours} max={max} onHover={(h, v) => setHover(h === null ? null : { r: r.key, h, v })} />
        ))}
      </div>
      <p className="h-4 text-xs text-muted" aria-live="polite">
        {hover ? (
          <>
            {rowLabel(hover.r)}, <span className="num">{String(hover.h).padStart(2, '0')}:00–{String(hover.h).padStart(2, '0')}:59</span>: <span className="num text-fg">{hover.v}</span> incident{hover.v === 1 ? '' : 's'}
          </>
        ) : (
          'Hover a cell for its count. Darker means more incidents in that hour.'
        )}
      </p>
    </div>
  )
}

function Row({ label, hours, max, onHover }: { label: string; hours: number[]; max: number; onHover: (h: number | null, v: number) => void }) {
  return (
    <>
      <span className="truncate pr-2 text-xs text-muted">{label}</span>
      {hours.map((v, h) => (
        <span
          key={h}
          role="img"
          aria-label={`${label}, hour ${h}: ${v}`}
          onMouseEnter={() => onHover(h, v)}
          onMouseLeave={() => onHover(null, 0)}
          className={cn('h-6 rounded-[3px]', v === 0 && 'bg-hover')}
          style={v ? { background: `color-mix(in srgb, var(--accent) ${20 + (80 * v) / max}%, var(--bg-sunken))` } : undefined}
        />
      ))}
    </>
  )
}
