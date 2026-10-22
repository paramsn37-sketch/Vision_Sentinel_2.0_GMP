import { FileDown } from 'lucide-react'
import { useMemo, useState } from 'react'
import { HourGrid, TimeChart } from '@/components/charts/charts'
import { Button, EmptyState, ErrorState, Metric, Panel, SegmentedControl, Select, Skeleton, Table, Td, Th, Tr } from '@/components/ui'
import { url } from '@/lib/api/client'
import { useCameras, useIncidentsByHour, useSummary, useTimeseries, useZoneStats } from '@/lib/api/hooks'
import { pct, ruleLabel, severityLabel, startOfToday, toDate, ZONE_KIND_LABEL } from '@/lib/format'

type RangeKey = 'today' | '24h' | '7d'

function rangeOf(k: RangeKey) {
  const until = new Date()
  const since = k === 'today' ? new Date(startOfToday()) : new Date(until.getTime() - (k === '24h' ? 24 : 24 * 7) * 3600_000)
  // Round "until" to the minute so query keys stay stable while the page is open.
  until.setSeconds(0, 0)
  until.setMinutes(until.getMinutes() + 1)
  return { since: since.toISOString(), until: until.toISOString() }
}

export default function AnalyticsPage() {
  const [rk, setRk] = useState<RangeKey>('today')
  const [camera, setCamera] = useState('all')
  const range = useMemo(() => rangeOf(rk), [rk])
  const cameras = useCameras()
  const summary = useSummary(range)
  const series = useTimeseries({ ...range, bucket: 'hour', camera_id: camera === 'all' ? undefined : camera })
  const byHour = useIncidentsByHour(range)
  const zones = useZoneStats(range)
  const s = summary.data
  const pts = series.data?.points ?? []
  const hourFmt = (t: string) => {
    const d = toDate(t)
    return rk === '7d' ? `${d.toLocaleDateString('en-GB', { weekday: 'short' })} ${String(d.getHours()).padStart(2, '0')}` : `${String(d.getHours()).padStart(2, '0')}:00`
  }
  const busiest = pts.reduce<null | { t: string; v: number }>((a, p) => (p.new_people > (a?.v ?? 0) ? { t: p.t, v: p.new_people } : a), null)
  const topRule = s ? Object.entries(s.incidents_by_rule).sort((a, b) => b[1] - a[1])[0] : undefined

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl">Analytics</h1>
          <p className="text-sm text-muted">
            {s && busiest
              ? `Busiest hour ${hourFmt(busiest.t)} with ${busiest.v} new people${topRule ? `; most incidents were “${ruleLabel(topRule[0]).toLowerCase()}” (${topRule[1]})` : ''}.`
              : 'Counts are unique confirmed people, aggregated per minute on the server.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <SegmentedControl label="Range" value={rk} onChange={setRk} options={[{ value: 'today', label: 'Today' }, { value: '24h', label: 'Last 24 h' }, { value: '7d', label: 'Last 7 days' }]} />
          <Select label="Camera" value={camera} onChange={setCamera} options={[{ value: 'all', label: 'All cameras' }, ...(cameras.data ?? []).map((c) => ({ value: c.id, label: c.name }))]} />
          <a href={url('/reports/shift', { ...range, format: 'pdf' })} download>
            <Button size="sm" icon={<FileDown className="size-4" />}>PDF report</Button>
          </a>
          <a href={url('/reports/shift', { ...range, format: 'csv' })} download>
            <Button size="sm" icon={<FileDown className="size-4" />}>CSV</Button>
          </a>
        </div>
      </div>

      {summary.isError ? (
        <ErrorState error={summary.error} onRetry={() => summary.refetch()} />
      ) : (
        <section className="grid grid-cols-2 gap-6 rounded-md border border-line bg-sunken px-4 py-4 md:grid-cols-5" aria-label="Totals for the range">
          <Metric label="Unique people" value={s?.unique_people ?? '—'} unit="people" note="all cameras" />
          <Metric label="Incidents" value={s?.incidents ?? '—'} note={s ? `${s.open_incidents} still open` : undefined} />
          <Metric label="High severity open" value={s?.open_high ?? '—'} tone={s?.open_high ? 'danger' : undefined} />
          <Metric label="PPE compliance" value={s ? pct(s.compliance_rate) : '—'} note={s?.compliance_rate == null ? 'no PPE checks in range' : 'of people checked'} />
          <Metric label="Peak people at once" value={pts.length ? Math.max(...pts.map((p) => p.peak_people)) : '—'} note="highest minute" />
        </section>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="New people per hour" bodyClassName="p-4">
          {series.isPending ? <Skeleton className="h-[200px]" /> : <TimeChart data={pts.map((p) => ({ t: p.t, v: p.observed ? p.new_people : null }))} label="new people" unit="people / hour" formatX={hourFmt} />}
        </Panel>
        <Panel title="Peak people on site" bodyClassName="p-4">
          {series.isPending ? <Skeleton className="h-[200px]" /> : <TimeChart kind="line" data={pts.map((p) => ({ t: p.t, v: p.observed ? p.peak_people : null }))} label="people at once (peak minute)" unit="people" formatX={hourFmt} />}
        </Panel>
        <Panel title="Incidents per hour" bodyClassName="p-4">
          {series.isPending ? <Skeleton className="h-[200px]" /> : <TimeChart data={pts.map((p) => ({ t: p.t, v: p.incidents }))} label="incidents opened" unit="incidents / hour" formatX={hourFmt} />}
        </Panel>
        <Panel title="Incidents by type and hour of day" bodyClassName="p-4">
          {byHour.isPending ? (
            <Skeleton className="h-[200px]" />
          ) : byHour.data?.rows.length ? (
            <HourGrid rows={byHour.data.rows.map((r) => ({ key: r.rule, hours: r.hours }))} rowLabel={ruleLabel} />
          ) : (
            <EmptyState title="No incidents in this range">Incidents are grouped here by rule and the hour they opened.</EmptyState>
          )}
        </Panel>
      </div>

      <Panel title="Zones" bodyClassName="overflow-x-auto">
        {zones.isPending ? (
          <Skeleton className="m-4 h-24" />
        ) : !zones.data?.length ? (
          <EmptyState title="No zones yet">Draw zones on the Zones screen to see entries, incidents and occupancy per zone.</EmptyState>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Zone</Th>
                <Th>Camera</Th>
                <Th>Kind</Th>
                <Th>Severity</Th>
                <Th align="right">Entries</Th>
                <Th align="right">Incidents</Th>
                <Th align="right">Peak people</Th>
              </tr>
            </thead>
            <tbody>
              {zones.data.map((z) => (
                <Tr key={z.zone_id}>
                  <Td className="text-fg">{z.zone_name}</Td>
                  <Td className="text-muted">{cameras.data?.find((c) => c.id === z.camera_id)?.name ?? z.camera_id}</Td>
                  <Td className="text-muted">{ZONE_KIND_LABEL[z.kind] ?? z.kind}</Td>
                  <Td className="text-muted">{severityLabel(z.severity)}</Td>
                  <Td align="right">{z.entries}</Td>
                  <Td align="right">{z.incidents}</Td>
                  <Td align="right">{z.peak_occupancy}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>
    </div>
  )
}
