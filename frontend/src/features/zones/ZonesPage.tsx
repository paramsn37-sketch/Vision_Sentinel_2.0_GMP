import { useQueryClient } from '@tanstack/react-query'
import { Download, Plus, Upload as UploadIcon } from 'lucide-react'
import { useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { Button, Dialog, EmptyState, ErrorState, Select, Skeleton, StatusPill, cn } from '@/components/ui'
import { api, url, type Zone, type ZoneIn } from '@/lib/api/client'
import { useCameras, useDeleteZone, useSaveZone, useZones } from '@/lib/api/hooks'
import { severityLabel, ZONE_KIND_LABEL } from '@/lib/format'
import { useLiveMeta } from '@/features/live/useLiveMeta'
import { pointInPolygon, type Pt } from './editor/geometry'
import { initial, reducer } from './editor/reducer'
import { ZoneCanvas } from './editor/ZoneCanvas'
import { ZoneForm, type FormValues } from './ZoneForm'

const KIND_VAR: Record<string, string> = { restricted: 'var(--zone-restricted)', hazard: 'var(--zone-hazard)', ppe_required: 'var(--zone-ppe)' }
const blank = (cameraId: string): FormValues => ({
  camera_id: cameraId,
  name: '',
  kind: 'restricted',
  severity: 'high',
  enabled: true,
  rules: { no_entry: true, required_ppe: [], max_occupancy: null, max_dwell_s: null, active_hours: null },
})

export default function ZonesPage() {
  const [params, setParams] = useSearchParams()
  const cameras = useCameras()
  const cameraId = params.get('camera') ?? cameras.data?.[0]?.id
  const zones = useZones(cameraId)
  const [selectedId, setSelectedId] = useState<string | 'new' | null>(params.get('new') ? 'new' : null)
  const [ed, dispatch] = useReducer(reducer, initial)
  const [form, setForm] = useState<FormValues | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [snapKey, setSnapKey] = useState(0)
  const save = useSaveZone()
  const del = useDeleteZone()
  const qc = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const meta = useLiveMeta(cameraId)

  const list = zones.data ?? []
  const current = list.find((z) => z.id === selectedId)

  // Selecting a zone loads it into the editor; "new" starts drawing.
  useEffect(() => {
    if (!cameraId) return
    if (selectedId === 'new') {
      dispatch({ type: 'start' })
      setForm(blank(cameraId))
    } else if (current) {
      dispatch({ type: 'load', points: current.polygon as Pt[] })
      setForm({ camera_id: current.camera_id, name: current.name, kind: current.kind, severity: current.severity, enabled: current.enabled ?? true, rules: { ...blank(cameraId).rules, ...current.rules } })
    } else {
      dispatch({ type: 'clear' })
      setForm(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, cameraId, current?.id, current?.updated_at])

  const people = useMemo(() => {
    if (!meta || ed.points.length < 3) return []
    return meta.persons.map((p) => {
      const foot: Pt = [(p.box[0] + p.box[2]) / 2 / meta.width, p.box[3] / meta.height]
      return { id: p.track_id, foot, inside: pointInPolygon(foot, ed.points) }
    })
  }, [meta, ed.points])
  const insideNow = people.filter((p) => p.inside).length

  const dirty =
    selectedId === 'new' ||
    (current && (JSON.stringify(current.polygon) !== JSON.stringify(ed.points) || JSON.stringify(formOf(current)) !== JSON.stringify(form && { ...form, rules: { ...form.rules } })))

  const onSave = () => {
    if (!form || !cameraId) return
    const body: ZoneIn & { id?: string } = { ...form, polygon: ed.points, id: current?.id }
    save.mutate(body, {
      onSuccess: (z) => {
        toast.success(selectedId === 'new' ? `Zone “${z.name}” created` : `Zone “${z.name}” saved`, { description: 'The camera applies it from the next frame.' })
        setSelectedId(z.id)
      },
      onError: (e) => toast.error('Could not save the zone', { description: e.message }),
    })
  }

  const onImport = async (f: File) => {
    if (!cameraId) return
    try {
      const out = await api.postText<Zone[]>('/zones/import', await f.text(), { camera_id: cameraId })
      qc.invalidateQueries({ queryKey: ['zones'] })
      toast.success(`Imported ${out.length} zone${out.length === 1 ? '' : 's'}`)
    } catch (e) {
      toast.error('Could not import zones', { description: (e as Error).message })
    }
  }

  if (cameras.isPending) return <Skeleton className="m-4 h-96" />
  if (cameras.isError) return <ErrorState error={cameras.error} onRetry={() => cameras.refetch()} />
  if (!cameraId)
    return (
      <EmptyState title="Add a camera first" className="p-6">
        Zones are drawn on a camera’s frame. Add a camera in Settings, then come back here.
      </EmptyState>
    )

  const color = KIND_VAR[form?.kind ?? 'restricted']
  const others = list.filter((z) => z.id !== selectedId).map((z) => ({ id: z.id, name: z.name, color: KIND_VAR[z.kind], points: z.polygon as Pt[] }))

  return (
    <div className="flex h-full min-h-0 max-lg:h-auto max-lg:flex-col">
      <aside className="flex w-64 shrink-0 flex-col border-r border-line bg-bg max-lg:w-full max-lg:border-r-0 max-lg:border-b" aria-label="Zones on this camera">
        <div className="flex flex-col gap-3 border-b border-line p-4">
          <h1 className="text-xl">Zones</h1>
          <Select
            label="Camera"
            value={cameraId}
            onChange={(v) => {
              setParams({ camera: v })
              setSelectedId(null)
            }}
            options={(cameras.data ?? []).map((c) => ({ value: c.id, label: c.name }))}
          />
          <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setSelectedId('new')} disabled={selectedId === 'new'}>
            New zone
          </Button>
        </div>
        <ul className="min-h-0 flex-1 overflow-y-auto py-1 max-lg:max-h-56">
          {zones.isPending && <Skeleton className="mx-4 my-2 h-10" />}
          {zones.data && list.length === 0 && selectedId !== 'new' && <li className="px-4 py-3 text-sm text-muted">No zones on this camera yet. Draw one with New zone.</li>}
          {selectedId === 'new' && (
            <li className="relative bg-hover px-4 py-2 shadow-[inset_1px_0_0_var(--accent)]">
              <span className="text-sm">{form?.name || 'Untitled zone'}</span>
              <span className="block text-xs text-muted">drawing…</span>
            </li>
          )}
          {list.map((z) => (
            <li key={z.id}>
              <button
                type="button"
                onClick={() => setSelectedId(z.id)}
                className={cn(
                  'flex w-full flex-col items-start gap-0.5 px-4 py-2 text-left transition-colors duration-(--dur-fast) hover:bg-hover',
                  z.id === selectedId && 'bg-hover shadow-[inset_1px_0_0_var(--accent)]',
                )}
                aria-current={z.id === selectedId}
              >
                <span className="flex w-full items-center gap-2">
                  <span className="size-2.5 shrink-0 rounded-[2px]" style={{ background: KIND_VAR[z.kind] }} aria-hidden />
                  <span className="truncate text-sm">{z.name}</span>
                  {!z.enabled && <StatusPill tone="neutral" className="ml-auto">Off</StatusPill>}
                </span>
                <span className="pl-4.5 text-xs text-muted">
                  {ZONE_KIND_LABEL[z.kind]} · {severityLabel(z.severity)}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2 border-t border-line p-3">
          <a href={url('/zones/export', { camera_id: cameraId })} download={`zones-${cameraId}.yaml`} className="flex-1">
            <Button size="sm" className="w-full" icon={<Download className="size-4" />}>
              Export
            </Button>
          </a>
          <Button size="sm" className="flex-1" icon={<UploadIcon className="size-4" />} onClick={() => fileInput.current?.click()}>
            Import
          </Button>
          <input ref={fileInput} type="file" accept=".yaml,.yml" hidden onChange={(e) => e.target.files?.[0] && onImport(e.target.files[0])} />
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col gap-2 p-4 max-lg:h-[clamp(320px,75vw,640px)] max-lg:flex-none" aria-label="Editor">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted">
            {ed.mode === 'drawing' ? `Drawing: ${ed.points.length} point${ed.points.length === 1 ? '' : 's'}` : ed.mode === 'editing' ? `${ed.points.length} points` : 'Frame from the camera'}
            {meta && ed.points.length >= 3 && (
              <span className="ml-3">
                <span className={cn('num', insideNow ? 'text-danger' : 'text-fg')}>{insideNow}</span> {insideNow === 1 ? 'person is' : 'people are'} inside right now
              </span>
            )}
          </p>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => dispatch({ type: 'undo' })} disabled={!ed.past.length}>
              Undo
            </Button>
            <Button size="sm" variant="ghost" onClick={() => dispatch({ type: 'redo' })} disabled={!ed.future.length}>
              Redo
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSnapKey(Date.now())}>
              Refresh frame
            </Button>
          </div>
        </div>
        <ZoneCanvas
          image={url(`/cameras/${cameraId}/snapshot`, snapKey ? { t: snapKey } : undefined)}
          state={ed}
          dispatch={dispatch}
          color={color}
          others={others}
          people={people}
        />
      </section>

      <aside className="w-[340px] shrink-0 overflow-y-auto border-l border-line bg-bg max-lg:w-full max-lg:border-t max-lg:border-l-0" aria-label="Zone settings">
        {form ? (
          <ZoneForm
            value={form}
            onChange={setForm}
            points={ed.points}
            canSave={ed.mode === 'editing' && !ed.message && !!dirty}
            saving={save.isPending}
            onSave={onSave}
            onCancel={() => setSelectedId(current ? current.id : null)}
            onDelete={current ? () => setConfirmDelete(true) : undefined}
            drawing={ed.mode === 'drawing'}
          />
        ) : (
          <EmptyState title="No zone selected">Pick a zone from the list to edit it, or create one with New zone.</EmptyState>
        )}
      </aside>

      <Dialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete “${current?.name}”?`}
        description="The camera stops checking this zone immediately. Past incidents and reports keep their record."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
              Keep zone
            </Button>
            <Button
              variant="danger"
              loading={del.isPending}
              onClick={() =>
                current &&
                del.mutate(current.id, {
                  onSuccess: () => {
                    setConfirmDelete(false)
                    setSelectedId(null)
                    toast.success(`Zone “${current.name}” deleted`)
                  },
                })
              }
            >
              Delete zone
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">You can export the zones as YAML first if you may need it again.</p>
      </Dialog>
    </div>
  )
}

function formOf(z: Zone): FormValues {
  return { camera_id: z.camera_id, name: z.name, kind: z.kind, severity: z.severity, enabled: z.enabled ?? true, rules: { ...blank(z.camera_id).rules, ...z.rules } }
}
