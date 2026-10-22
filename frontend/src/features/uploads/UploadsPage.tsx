import { useQueryClient } from '@tanstack/react-query'
import { Download, FileUp, ScanSearch } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Button, Drawer, EmptyState, ErrorState, Metric, Panel, Skeleton, StatusPill, Table, Td, Th, Tr, cn } from '@/components/ui'
import { api, url, type Upload } from '@/lib/api/client'
import { keys, useUploads } from '@/lib/api/hooks'
import type { FrameMeta } from '@/lib/api/types'
import { absoluteTime, duration, ppeLabel, relativeTime, ruleLabel } from '@/lib/format'
import { XaiPanel, type XaiTarget } from '@/features/xai/XaiPanel'

const ACCEPT = '.jpg,.jpeg,.png,.mp4,.mov,.avi,.mkv,.webm'

interface Result {
  frames: number
  fps: number
  duration_s: number
  unique_people: number
  peak_people: number
  ppe_summary: Record<string, { present: number; absent: number; unknown: number }>
  incidents: { id: string; rule: string; track_id: number | null; severity: string; duration_s: number }[]
  keyframes: FrameMeta[]
  model: string
}

export default function UploadsPage() {
  const uploads = useUploads()
  const qc = useQueryClient()
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)

  const send = async (f: File) => {
    setBusy(true)
    try {
      const form = new FormData()
      form.append('file', f)
      const up = await api.upload<Upload>('/uploads', form)
      qc.invalidateQueries({ queryKey: keys.uploads })
      setSelected(up.id)
      toast.success(`Analysing ${f.name}`, { description: 'Progress shows in the list. You can leave this page.' })
    } catch (e) {
      toast.error(`Could not upload ${f.name}`, { description: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  const list = uploads.data ?? []
  const current = list.find((u) => u.id === selected) ?? list[0]

  return (
    <div className="flex flex-col gap-4 p-4">
      <div>
        <h1 className="text-xl">Uploads</h1>
        <p className="text-sm text-muted">Run the same detection, tracking and PPE checks on a photo or a video file. Nothing here is sampled or simulated.</p>
      </div>
      <div
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          const f = e.dataTransfer.files[0]
          if (f) send(f)
        }}
        className={cn(
          'flex cursor-pointer items-center gap-4 rounded-md border border-dashed border-line-strong/60 bg-sunken px-5 py-6 transition-colors duration-(--dur-fast) hover:border-line-strong',
          over && 'border-accent bg-accent-bg',
        )}
      >
        <FileUp className="size-6 text-muted" aria-hidden />
        <div className="flex-1">
          <p className="text-sm font-medium">{busy ? 'Uploading…' : 'Drop a photo or video here, or click to choose'}</p>
          <p className="text-xs text-muted">JPG, PNG, MP4, MOV, AVI, MKV or WebM. Videos are processed at their own frame rate on this machine.</p>
        </div>
        <input ref={input} type="file" accept={ACCEPT} hidden onChange={(e) => e.target.files?.[0] && send(e.target.files[0])} />
      </div>

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Panel title="Recent files" bodyClassName="overflow-x-auto">
          {uploads.isPending ? (
            <Skeleton className="m-4 h-24" />
          ) : uploads.isError ? (
            <ErrorState error={uploads.error} onRetry={() => uploads.refetch()} />
          ) : list.length === 0 ? (
            <EmptyState title="Nothing analysed yet">Upload a file above. Results stay here with the annotated copy.</EmptyState>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>File</Th>
                  <Th>Status</Th>
                  <Th align="right">People</Th>
                  <Th align="right">Incidents</Th>
                  <Th align="right">Added</Th>
                </tr>
              </thead>
              <tbody>
                {list.map((u) => {
                  const r = u.result as Result | null
                  return (
                    <Tr key={u.id} selected={u.id === current?.id} onClick={() => setSelected(u.id)} className="cursor-pointer">
                      <Td className="max-w-[240px] truncate text-fg">{u.filename}</Td>
                      <Td>
                        <UploadStatus u={u} />
                      </Td>
                      <Td align="right">{r ? r.unique_people : '—'}</Td>
                      <Td align="right">{r ? r.incidents.length : '—'}</Td>
                      <Td align="right" className="text-muted" title={absoluteTime(u.created_at)}>
                        {relativeTime(u.created_at)}
                      </Td>
                    </Tr>
                  )
                })}
              </tbody>
            </Table>
          )}
        </Panel>
        {current && <UploadResult u={current} />}
      </div>
    </div>
  )
}

function UploadStatus({ u }: { u: Upload }) {
  if (u.status === 'done') return <StatusPill tone="ok">Done</StatusPill>
  if (u.status === 'failed') return <StatusPill tone="danger">Failed</StatusPill>
  return (
    <span className="flex items-center gap-2">
      <span className="h-1 w-20 overflow-hidden rounded-full bg-hover" role="progressbar" aria-valuenow={Math.round(u.progress * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Progress">
        <span className="block h-full bg-accent transition-[width] duration-(--dur-ui)" style={{ width: `${Math.round(u.progress * 100)}%` }} />
      </span>
      <span className="num text-xs text-muted">{Math.round(u.progress * 100)}%</span>
    </span>
  )
}

function UploadResult({ u }: { u: Upload }) {
  const r = u.result as Result | null
  const [explain, setExplain] = useState<XaiTarget | null>(null)
  if (u.status === 'failed') return <Panel title={u.filename}><ErrorState error={new Error(u.error ?? 'Processing failed.')} /></Panel>
  if (!r)
    return (
      <Panel title={u.filename} bodyClassName="p-4">
        <p className="text-sm text-muted">Analysing… {Math.round(u.progress * 100)}% done.</p>
      </Panel>
    )
  const isVideo = u.media === 'video'
  const people = r.keyframes.flatMap((k) => k.persons.map((p) => ({ k, p }))).slice(0, 12)
  return (
    <Panel
      title={u.filename}
      actions={
        u.has_output && (
          <a href={url(`/uploads/${u.id}/annotated`)} download>
            <Button size="sm" icon={<Download className="size-4" />}>Annotated {isVideo ? 'video' : 'image'}</Button>
          </a>
        )
      }
      bodyClassName="flex flex-col gap-4 p-4"
    >
      {u.has_output &&
        (isVideo ? (
          <video src={url(`/uploads/${u.id}/annotated`)} controls className="w-full rounded-sm bg-black" aria-label="Annotated video" />
        ) : (
          <img src={url(`/uploads/${u.id}/annotated`)} alt="Annotated result" className="w-full rounded-sm border border-line" />
        ))}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Metric label="Unique people" value={r.unique_people} />
        <Metric label="Peak at once" value={r.peak_people} />
        <Metric label="Incidents" value={r.incidents.length} tone={r.incidents.length ? 'warning' : undefined} />
        <Metric label={isVideo ? 'Length' : 'Frames'} value={isVideo ? duration(r.duration_s) : r.frames} note={`model ${r.model}`} />
      </div>
      {Object.keys(r.ppe_summary).length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold">PPE per person</h3>
          <Table>
            <thead>
              <tr>
                <Th>Item</Th>
                <Th align="right">Wearing</Th>
                <Th align="right">Missing</Th>
                <Th align="right">Not visible</Th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(r.ppe_summary).map(([item, c]) => (
                <Tr key={item}>
                  <Td>{ppeLabel(item)}</Td>
                  <Td align="right" className="text-ok">{c.present}</Td>
                  <Td align="right" className={c.absent ? 'text-danger' : ''}>{c.absent}</Td>
                  <Td align="right" className="text-muted">{c.unknown}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
      {r.incidents.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm">
          {r.incidents.map((i) => (
            <li key={i.id}>
              {ruleLabel(i.rule)} {i.track_id !== null && <span className="num text-muted">#{i.track_id}</span>} <span className="text-muted">· {duration(i.duration_s)}</span>
            </li>
          ))}
        </ul>
      )}
      {people.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold">Explain a detection</h3>
          <div className="flex flex-wrap gap-2">
            {people.map(({ k, p }) => (
              <Button
                key={`${k.frame_idx}-${p.track_id}`}
                size="sm"
                variant="ghost"
                icon={<ScanSearch className="size-4" />}
                onClick={() => setExplain({ source: 'upload', upload_id: u.id, frame_idx: k.frame_idx, box: p.box, cls: 'person' })}
              >
                <span className="num">#{p.track_id}</span>
                {isVideo && <span className="text-muted">at {duration(k.frame_idx / (r.fps || 1))}</span>}
              </Button>
            ))}
          </div>
        </div>
      )}
      <Drawer open={!!explain} onOpenChange={(v) => !v && setExplain(null)} title="Explanation" description={u.filename}>
        <div className="p-5">{explain && <XaiPanel target={explain} />}</div>
      </Drawer>
    </Panel>
  )
}
