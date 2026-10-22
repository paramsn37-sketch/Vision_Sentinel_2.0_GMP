import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { Button, Checkbox, Drawer, EmptyState, ErrorState, Metric, SegmentedControl, Skeleton, StatusPill, cn } from '@/components/ui'
import { useCameras, useIncidents, useSummary, useTimeseries } from '@/lib/api/hooks'
import type { FrameMeta } from '@/lib/api/types'
import { absoluteTime, relativeTime, ruleLabel, severityLabel, severityTone, startOfToday } from '@/lib/format'
import { useLive } from '@/stores/live'
import { XaiPanel, type XaiTarget } from '@/features/xai/XaiPanel'
import type { Layers } from './overlay'
import { ShiftStrip } from './ShiftStrip'
import { TrackCard } from './TrackCard'
import { VideoTile, type Selection } from './VideoTile'

type Layout = '1' | '2' | '4'

const readPref = <T,>(k: string, d: T): T => {
  try {
    return (JSON.parse(localStorage.getItem(k) ?? 'null') as T) ?? d
  } catch {
    return d
  }
}
const writePref = (k: string, v: unknown) => {
  try {
    localStorage.setItem(k, JSON.stringify(v))
  } catch {
    /* ignore */
  }
}

export default function LivePage() {
  const cameras = useCameras()
  const [layout, setLayout] = useState<Layout>(() => readPref('vs.live.layout', '2'))
  const [layers, setLayers] = useState<Layers>(() => readPref('vs.live.layers', { boxes: true, ppe: true, ids: true, zones: true }))
  const [selected, setSelected] = useState<Selection | null>(null)
  const [paused, setPaused] = useState<Record<string, FrameMeta | null>>({})
  const [explain, setExplain] = useState<XaiTarget | null>(null)
  const frames = useLive((s) => s.frames)

  useEffect(() => writePref('vs.live.layout', layout), [layout])
  useEffect(() => writePref('vs.live.layers', layers), [layers])

  const running = useMemo(() => (cameras.data ?? []).filter((c) => c.enabled), [cameras.data])
  const shown = running.slice(0, Number(layout))
  const selMeta = selected ? (paused[selected.cameraId] ?? frames[selected.cameraId] ?? null) : null
  const isPaused = !!(selected && paused[selected.cameraId])

  const startExplain = () => {
    if (!selected || !selMeta) return
    const p = selMeta.persons.find((x) => x.track_id === selected.trackId)
    if (!p) return
    setExplain({ source: 'live', camera_id: selected.cameraId, frame_idx: selMeta.frame_idx, box: p.box, cls: 'person' })
  }

  return (
    <div className="flex h-full min-h-0 max-lg:h-auto max-lg:flex-col">
      <section className="flex min-w-0 flex-1 flex-col gap-4 p-4" aria-label="Camera wall">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-xl">Live</h1>
          <div className="flex flex-wrap items-center gap-6">
            <fieldset className="flex items-center gap-4">
              <legend className="sr-only">Overlay layers</legend>
              <Checkbox label="Boxes" checked={layers.boxes} onChange={(v) => setLayers({ ...layers, boxes: v })} />
              <Checkbox label="PPE" checked={layers.ppe} onChange={(v) => setLayers({ ...layers, ppe: v })} />
              <Checkbox label="IDs" checked={layers.ids} onChange={(v) => setLayers({ ...layers, ids: v })} />
              <Checkbox label="Zones" checked={layers.zones} onChange={(v) => setLayers({ ...layers, zones: v })} />
            </fieldset>
            <SegmentedControl
              label="Camera layout"
              value={layout}
              onChange={setLayout}
              options={[
                { value: '1', label: '1 camera' },
                { value: '2', label: '2' },
                { value: '4', label: '2 × 2' },
              ]}
            />
          </div>
        </div>
        {cameras.isPending ? (
          <Skeleton className="flex-1" />
        ) : cameras.isError ? (
          <ErrorState error={cameras.error} onRetry={() => cameras.refetch()} />
        ) : shown.length === 0 ? (
          <EmptyState title="No cameras are enabled" action={<Link to="/settings"><Button variant="primary">Add a camera</Button></Link>}>
            Add a video file, webcam or RTSP stream in Settings. Detection starts as soon as the camera is enabled.
          </EmptyState>
        ) : (
          <div
            className={cn(
              'grid min-h-0 flex-1 gap-4 max-lg:[&>figure]:h-[clamp(240px,56vw,520px)]',
              layout === '1' && 'grid-cols-1',
              layout === '2' && 'grid-cols-1 2xl:grid-cols-2',
              layout === '4' && 'grid-cols-1 md:grid-cols-2 lg:grid-rows-2',
            )}
          >
            {shown.map((c) => (
              <VideoTile
                key={c.id}
                camera={c}
                layers={layers}
                selected={selected}
                fps={layout === '4' ? 8 : 12}
                onSelect={(s) => setSelected(s)}
                onPausedChange={(p, meta) => setPaused((prev) => ({ ...prev, [c.id]: p ? meta : null }))}
              />
            ))}
          </div>
        )}
        {running.length > shown.length && (
          <p className="text-xs text-muted">
            Showing {shown.length} of {running.length} cameras. Choose 2 × 2 to see more.
          </p>
        )}
      </section>
      <SidePanel
        selected={selected}
        selMeta={selMeta}
        paused={isPaused}
        onExplain={startExplain}
        onClear={() => setSelected(null)}
      />
      <Drawer
        open={!!explain}
        onOpenChange={(v) => !v && setExplain(null)}
        title={selected ? `Why person #${selected.trackId} was detected` : 'Explanation'}
        description="Gradient heatmap for this exact detection on the paused frame."
      >
        <div className="p-5">{explain && <XaiPanel target={explain} />}</div>
      </Drawer>
    </div>
  )
}

function SidePanel({
  selected,
  selMeta,
  paused,
  onExplain,
  onClear,
}: {
  selected: Selection | null
  selMeta: FrameMeta | null
  paused: boolean
  onExplain: () => void
  onClear: () => void
}) {
  const [since] = useState(startOfToday)
  const [shiftSince] = useState(() => new Date(Date.now() - 4 * 3600_000).toISOString())
  const summary = useSummary({ since })
  const series = useTimeseries({ since: shiftSince, bucket: 'minute' })
  const open = useIncidents({ status: 'open', limit: 8 })
  const feed = useLive((s) => s.feed)
  const fresh = new Set(feed.filter((f) => f.kind === 'opened').slice(0, 5).map((f) => f.incident.id))
  const s = summary.data

  return (
    <aside className="flex w-[340px] shrink-0 flex-col overflow-y-auto border-l border-line bg-bg max-lg:w-full max-lg:overflow-visible max-lg:border-t max-lg:border-l-0" aria-label="Site overview">
      {selected && <TrackCard meta={selMeta} trackId={selected.trackId} paused={paused} onExplain={onExplain} onClose={onClear} />}
      <section className="grid grid-cols-3 gap-4 border-b border-line px-4 py-4">
        <Metric label="People now" value={s?.people_now ?? '—'} />
        <Metric label="Unique today" value={s?.unique_people ?? '—'} />
        <Metric
          label="Compliance"
          value={s?.compliance_rate == null ? '—' : `${Math.round(s.compliance_rate * 100)}%`}
          note={s?.compliance_rate == null ? 'no PPE checks yet' : 'people with all PPE'}
        />
      </section>
      <section className="flex flex-col gap-2 border-b border-line px-4 py-4">
        <h2 className="text-sm font-semibold">Last 4 hours</h2>
        <ShiftStrip points={series.data?.points} loading={series.isPending} />
      </section>
      <section className="flex min-h-0 flex-col">
        <header className="flex items-center justify-between px-4 pt-4 pb-2">
          <h2 className="text-sm font-semibold">
            Open incidents {open.data && <span className="num ml-1 text-muted">{open.data.total}</span>}
          </h2>
          <Link to="/incidents?status=open" className="text-xs text-accent">
            View all
          </Link>
        </header>
        {open.isPending ? (
          <div className="flex flex-col gap-2 px-4">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : open.data?.items.length === 0 ? (
          <p className="px-4 pb-4 text-sm text-muted">Nothing open. New incidents appear here and as a notification.</p>
        ) : (
          <ul className="flex flex-col pb-2">
            {open.data?.items.map((i) => (
              <li key={i.id} className={cn(fresh.has(i.id) && 'vs-row-in')}>
                <Link
                  to={`/incidents?id=${i.id}`}
                  className="flex flex-col gap-0.5 px-4 py-2 transition-colors duration-(--dur-fast) hover:bg-hover"
                >
                  <span className="flex items-center gap-2">
                    <StatusPill tone={severityTone(i.severity)}>{severityLabel(i.severity)}</StatusPill>
                    <span className="truncate text-sm">{ruleLabel(i.rule)}</span>
                  </span>
                  <span className="text-xs text-muted" title={absoluteTime(i.started_at)}>
                    {i.zone_name ?? 'whole frame'} · {i.camera_name ?? i.camera_id} · {relativeTime(i.started_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  )
}
