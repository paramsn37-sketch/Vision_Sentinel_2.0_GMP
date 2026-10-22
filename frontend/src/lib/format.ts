// Formatting rules from DESIGN.md §8: units on every number, relative time with absolute on hover.

const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto', style: 'short' })

export function toDate(v: string | number | Date): Date {
  if (v instanceof Date) return v
  if (typeof v === 'number') return new Date(v)
  // Backend datetimes without an offset are UTC.
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(v) ? v : `${v}Z`)
}

export function relativeTime(v: string | number | Date, now: number = Date.now()): string {
  const s = Math.round((toDate(v).getTime() - now) / 1000)
  const a = Math.abs(s)
  if (a < 45) return s <= 0 ? 'just now' : 'in a few seconds'
  if (a < 3600) return rtf.format(Math.round(s / 60), 'minute')
  if (a < 86400) return rtf.format(Math.round(s / 3600), 'hour')
  return rtf.format(Math.round(s / 86400), 'day')
}

export function absoluteTime(v: string | number | Date): string {
  const d = toDate(v)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function clockTime(v: string | number | Date): string {
  return toDate(v).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function duration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = String(Math.round(seconds % 60)).padStart(2, '0')
  if (m < 60) return `${m}m ${s}s`
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`
}

export function pct(v: number | null | undefined, digits = 0): string {
  return v === null || v === undefined || Number.isNaN(v) ? '—' : `${(v * 100).toFixed(digits)}%`
}

export function num(v: number | null | undefined, digits = 0): string {
  return v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : v.toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

const PPE_LABEL: Record<string, string> = {
  helmet: 'helmet',
  vest: 'hi-vis vest',
  gloves: 'gloves',
  boots: 'boots',
  goggles: 'eye protection',
}
export const ppeLabel = (item: string) => PPE_LABEL[item] ?? item
/** Sentence-case PPE name for a standalone label (checkbox, column header). */
export const ppeTitle = (item: string) => ppeLabel(item).replace(/^./, (c) => c.toUpperCase())

/** Human name of an incident rule: "intrusion", "ppe_missing:helmet", "overcrowding", "dwell". */
export function ruleLabel(rule: string): string {
  if (rule.startsWith('ppe_missing:')) return `Missing ${ppeLabel(rule.split(':')[1])}`
  return (
    {
      intrusion: 'Entered no-entry zone',
      overcrowding: 'Zone over capacity',
      dwell: 'Stayed too long',
      dwell_exceeded: 'Stayed too long',
    }[rule] ?? rule.replace(/_/g, ' ')
  )
}

export const severityTone = (s: string) => (s === 'high' ? 'danger' : s === 'medium' ? 'warning' : 'neutral') as
  | 'danger'
  | 'warning'
  | 'neutral'

export const ZONE_KIND_LABEL: Record<string, string> = {
  restricted: 'No entry',
  ppe_required: 'PPE required',
  hazard: 'Hazard area',
}

export function startOfToday(): string {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d.toISOString()
}

export const severityLabel = (s: string) => ({ high: 'High', medium: 'Medium', low: 'Low' })[s] ?? s

export const statusTone = (s: string) => (s === 'open' ? 'danger' : s === 'acknowledged' ? 'warning' : 'neutral') as 'danger' | 'warning' | 'neutral'
export const statusLabel = (s: string) => ({ open: 'Open', acknowledged: 'Acknowledged', resolved: 'Resolved' })[s] ?? s
