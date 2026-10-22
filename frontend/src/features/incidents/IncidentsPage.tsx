import { Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Button, EmptyState, ErrorState, Input, Kbd, SegmentedControl, Select, Skeleton, StatusPill, Table, Td, Th, Tr, cn } from '@/components/ui'
import type { Incident } from '@/lib/api/client'
import { useCameras, useIncidents, usePatchIncident, type IncidentFilters } from '@/lib/api/hooks'
import { absoluteTime, duration, relativeTime, ruleLabel, severityLabel, severityTone, statusLabel, statusTone } from '@/lib/format'
import { IncidentDrawer } from './IncidentDrawer'

const STATUS_OPTS = [
  { value: 'open', label: 'Open' },
  { value: 'acknowledged', label: 'Acknowledged' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'all', label: 'All' },
]
const RULE_OPTS = [
  { value: 'all', label: 'Any rule' },
  { value: 'intrusion', label: 'Entered no-entry zone' },
  { value: 'ppe_missing', label: 'Missing PPE' },
  { value: 'overcrowding', label: 'Zone over capacity' },
  { value: 'dwell_exceeded', label: 'Stayed too long' },
]
const SEV_OPTS = [
  { value: 'all', label: 'Any severity' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]


export default function IncidentsPage() {
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? 'open'
  const rule = params.get('rule') ?? 'all'
  const severity = params.get('severity') ?? 'all'
  const camera = params.get('camera') ?? 'all'
  const openId = params.get('id')
  const [q, setQ] = useState(params.get('q') ?? '')
  const [cursors, setCursors] = useState<string[]>([])
  const [active, setActive] = useState(0)
  const search = useRef<HTMLInputElement>(null)
  const cameras = useCameras()

  const set = (k: string, v: string | null) =>
    setParams(
      (p) => {
        if (v === null || v === 'all' || v === '') p.delete(k)
        else p.set(k, v)
        return p
      },
      { replace: true },
    )

  const filters: IncidentFilters = useMemo(
    () => ({
      status: status === 'all' ? undefined : status,
      rule: rule === 'all' ? undefined : rule,
      severity: severity === 'all' ? undefined : severity,
      camera_id: camera === 'all' ? undefined : camera,
      q: params.get('q') ?? undefined,
      limit: 50,
      cursor: cursors[cursors.length - 1],
    }),
    [status, rule, severity, camera, params, cursors],
  )
  useEffect(() => setCursors([]), [status, rule, severity, camera])
  useEffect(() => {
    const t = setTimeout(() => set('q', q.trim() || null), 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q])

  const list = useIncidents(filters)
  const rows = list.data?.items ?? []
  const patch = usePatchIncident()

  useEffect(() => {
    if (active >= rows.length) setActive(Math.max(0, rows.length - 1))
  }, [rows.length, active])

  // Keyboard: j/k move, Enter opens, a acknowledge, r resolve, / search. Ignored while typing or in the drawer.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.closest('[role=dialog]')) return
      const row = rows[active]
      if (e.key === '/') {
        e.preventDefault()
        search.current?.focus()
      } else if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault()
        setActive((a) => Math.min(a + 1, rows.length - 1))
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault()
        setActive((a) => Math.max(a - 1, 0))
      } else if (e.key === 'Enter' && row) set('id', row.id)
      else if (e.key === 'a' && row && row.status === 'open') patch.mutate({ id: row.id, status: 'acknowledged' })
      else if (e.key === 'r' && row && row.status !== 'resolved') patch.mutate({ id: row.id, status: 'resolved' })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  useEffect(() => {
    document.querySelector(`[data-row="${active}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [active])

  const cameraOpts = [{ value: 'all', label: 'All cameras' }, ...(cameras.data ?? []).map((c) => ({ value: c.id, label: c.name }))]

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl">Incidents</h1>
          <p className="text-xs text-muted">
            {list.data ? (
              <>
                <span className="num text-fg">{list.data.total}</span> {status === 'all' ? 'in total' : statusLabel(status).toLowerCase()}
              </>
            ) : (
              ' '
            )}
            <span className="ml-3 hidden lg:inline">
              <Kbd>j</Kbd> <Kbd>k</Kbd> move · <Kbd>Enter</Kbd> open · <Kbd>a</Kbd> acknowledge · <Kbd>r</Kbd> resolve · <Kbd>/</Kbd> search
            </span>
          </p>
        </div>
        <SegmentedControl label="Status" value={status} onChange={(v) => set('status', v === 'open' ? null : v)} options={STATUS_OPTS} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute top-2 left-2.5 size-4 text-subtle" aria-hidden />
          <Input ref={search} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search zone, rule or ID" aria-label="Search incidents" className="w-64 pl-8" />
        </div>
        <Select label="Rule" value={rule} onChange={(v) => set('rule', v)} options={RULE_OPTS} />
        <Select label="Severity" value={severity} onChange={(v) => set('severity', v)} options={SEV_OPTS} />
        <Select label="Camera" value={camera} onChange={(v) => set('camera', v)} options={cameraOpts} />
      </div>
      <div className="min-h-0 flex-1 overflow-auto rounded-md border border-line bg-sunken">
        {list.isPending ? (
          <div className="flex flex-col gap-2 p-4">
            {Array.from({ length: 8 }, (_, i) => (
              <Skeleton key={i} className="h-7" />
            ))}
          </div>
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        ) : rows.length === 0 ? (
          <EmptyState
            title={status === 'open' ? 'No open incidents' : 'No incidents match these filters'}
            action={
              status === 'open' ? (
                <Button size="sm" onClick={() => set('status', 'all')}>
                  Show all incidents
                </Button>
              ) : (
                <Button size="sm" onClick={() => setParams({}, { replace: true })}>
                  Clear filters
                </Button>
              )
            }
          >
            {status === 'open' ? 'Cameras are watching. New incidents appear here and as a notification.' : 'Try a wider filter or a different camera.'}
          </EmptyState>
        ) : (
          <Table aria-label="Incidents" aria-rowcount={list.data?.total}>
            <thead>
              <tr>
                <Th>Severity</Th>
                <Th>What happened</Th>
                <Th>Zone</Th>
                <Th>Camera</Th>
                <Th align="right">Person</Th>
                <Th>Status</Th>
                <Th align="right">Duration</Th>
                <Th align="right">Started</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((i: Incident, n) => (
                <Tr
                  key={i.id}
                  data-row={n}
                  selected={n === active}
                  onClick={() => {
                    setActive(n)
                    set('id', i.id)
                  }}
                  className="cursor-pointer"
                >
                  <Td>
                    <StatusPill tone={severityTone(i.severity)}>{severityLabel(i.severity)}</StatusPill>
                  </Td>
                  <Td className="text-fg">
                    {ruleLabel(i.rule)}
                    {i.reopen_count > 0 && <span className="ml-2 text-xs text-muted">reopened {i.reopen_count}×</span>}
                  </Td>
                  <Td className="text-muted">{i.zone_name ?? '—'}</Td>
                  <Td className="text-muted">{i.camera_name ?? i.camera_id}</Td>
                  <Td align="right" className="text-muted">
                    {i.track_id !== null ? `#${i.track_id}` : '—'}
                  </Td>
                  <Td>
                    <span className="flex items-center gap-2">
                      <StatusPill tone={statusTone(i.status)}>{statusLabel(i.status)}</StatusPill>
                      {i.active && <span className="text-xs text-danger">ongoing</span>}
                    </span>
                  </Td>
                  <Td align="right">{duration(i.duration_s)}</Td>
                  <Td align="right" title={absoluteTime(i.started_at)} className={cn('text-muted')}>
                    {relativeTime(i.started_at)}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>
      {(list.data?.next_cursor || cursors.length > 0) && (
        <div className="flex items-center gap-2">
          <Button size="sm" disabled={cursors.length === 0} onClick={() => setCursors((c) => c.slice(0, -1))}>
            Newer
          </Button>
          <Button size="sm" disabled={!list.data?.next_cursor} onClick={() => list.data?.next_cursor && setCursors((c) => [...c, list.data.next_cursor!])}>
            Older
          </Button>
          <span className="text-xs text-muted">Page {cursors.length + 1}</span>
        </div>
      )}
      <IncidentDrawer id={openId} onClose={() => set('id', null)} />
    </div>
  )
}
