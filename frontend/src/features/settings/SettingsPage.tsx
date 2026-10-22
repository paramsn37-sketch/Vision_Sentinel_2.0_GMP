import { Play, Plus, Square, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button, Dialog, EmptyState, ErrorState, Field, IconButton, Input, Select, Skeleton, StatusPill, Switch, Table, Td, Th, Tr } from '@/components/ui'
import { api, type Camera, type Thresholds } from '@/lib/api/client'
import { useCameraAction, useCameras, useMe, useSaveCamera, useSaveThresholds, useThresholds } from '@/lib/api/hooks'
import { SECTION_TITLES, THRESHOLD_DOCS } from './thresholdDocs'

function Section({ title, help, children }: { title: string; help: string; children: React.ReactNode }) {
  return (
    <section className="grid grid-cols-1 gap-4 border-b border-line py-6 lg:grid-cols-[300px_minmax(0,1fr)]">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-muted">{help}</p>
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  )
}

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-[1180px] px-6 pb-10">
      <h1 className="pt-6 text-xl">Settings</h1>
      <CamerasSection />
      <ThresholdsSection />
      <AccountSection />
    </div>
  )
}

const statusTone = (s: string) => (s === 'running' ? 'ok' : s === 'error' ? 'danger' : 'neutral') as 'ok' | 'danger' | 'neutral'

function CamerasSection() {
  const cams = useCameras()
  const action = useCameraAction()
  const [edit, setEdit] = useState<Partial<Camera> | null>(null)
  const [remove, setRemove] = useState<Camera | null>(null)
  return (
    <Section title="Cameras" help="Video files, webcams (index such as 0) or RTSP/HTTP streams. Each enabled camera runs its own detection pipeline.">
      <div className="mb-3 flex justify-end">
        <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setEdit({ kind: 'file', enabled: true, loop: true, stride: 1, point_mode: 'foot' })}>
          Add camera
        </Button>
      </div>
      <div className="overflow-x-auto rounded-md border border-line bg-sunken">
        {cams.isPending ? (
          <Skeleton className="m-4 h-16" />
        ) : cams.isError ? (
          <ErrorState error={cams.error} onRetry={() => cams.refetch()} />
        ) : !cams.data?.length ? (
          <EmptyState title="No cameras">Add one to start monitoring.</EmptyState>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Source</Th>
                <Th>Status</Th>
                <Th align="right">fps</Th>
                <Th align="right">Every nth frame</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {cams.data.map((c) => (
                <Tr key={c.id}>
                  <Td className="text-fg">
                    <button type="button" className="hover:underline" onClick={() => setEdit(c)}>
                      {c.name}
                    </button>
                  </Td>
                  <Td className="max-w-[260px] truncate text-muted" title={c.uri}>
                    {c.uri}
                  </Td>
                  <Td>
                    <span className="flex items-center gap-2">
                      <StatusPill tone={statusTone(c.status)}>{c.status === 'running' ? 'Running' : c.status === 'error' ? 'Error' : 'Stopped'}</StatusPill>
                      {c.error && <span className="max-w-[200px] truncate text-xs text-danger" title={c.error}>{c.error}</span>}
                    </span>
                  </Td>
                  <Td align="right">{c.status === 'running' ? c.fps.toFixed(1) : '—'}</Td>
                  <Td align="right">{c.stride}</Td>
                  <Td>
                    <span className="flex justify-end gap-1">
                      {c.status === 'running' ? (
                        <IconButton size="sm" label={`Stop ${c.name}`} onClick={() => action.mutate({ id: c.id, action: 'stop' })}>
                          <Square className="size-4" />
                        </IconButton>
                      ) : (
                        <IconButton size="sm" label={`Start ${c.name}`} onClick={() => action.mutate({ id: c.id, action: 'start' })}>
                          <Play className="size-4" />
                        </IconButton>
                      )}
                      <IconButton size="sm" label={`Delete ${c.name}`} onClick={() => setRemove(c)}>
                        <Trash2 className="size-4" />
                      </IconButton>
                    </span>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>
      {edit && <CameraDialog initial={edit} onClose={() => setEdit(null)} />}
      <Dialog
        open={!!remove}
        onOpenChange={(v) => !v && setRemove(null)}
        title={`Delete camera “${remove?.name}”?`}
        description="Its pipeline stops and its zones are removed. Incidents already recorded stay in the log and reports."
        footer={
          <>
            <Button variant="ghost" onClick={() => setRemove(null)}>
              Keep camera
            </Button>
            <Button variant="danger" onClick={() => remove && action.mutate({ id: remove.id, action: 'delete' }, { onSuccess: () => setRemove(null) })}>
              Delete camera
            </Button>
          </>
        }
      >
        <span />
      </Dialog>
    </Section>
  )
}

function CameraDialog({ initial, onClose }: { initial: Partial<Camera>; onClose: () => void }) {
  const [v, setV] = useState(initial)
  const [test, setTest] = useState<{ ok: boolean; message: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const save = useSaveCamera()
  const set = (p: Partial<Camera>) => setV({ ...v, ...p })
  const runTest = async () => {
    setTesting(true)
    try {
      setTest(await api.post<{ ok: boolean; message: string }>('/cameras/test', { name: v.name || 'test', uri: v.uri, kind: v.kind }))
    } catch (e) {
      setTest({ ok: false, message: (e as Error).message })
    } finally {
      setTesting(false)
    }
  }
  return (
    <Dialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={initial.id ? `Edit ${initial.name}` : 'Add camera'}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={save.isPending}
            disabled={!v.name?.trim() || !v.uri?.trim()}
            onClick={() =>
              save.mutate(
                { id: v.id, name: v.name, uri: v.uri, kind: v.kind as 'file', enabled: v.enabled, loop: v.loop, stride: v.stride, point_mode: v.point_mode as 'foot', notes: v.notes ?? '' },
                { onSuccess: () => (toast.success('Camera saved'), onClose()) },
              )
            }
          >
            Save camera
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Name">{(p) => <Input {...p} value={v.name ?? ''} onChange={(e) => set({ name: e.target.value })} placeholder="e.g. Gate 2" />}</Field>
        <div className="grid grid-cols-[140px_1fr] gap-3">
          <Field label="Type">
            {(p) => (
              <Select id={p.id} label="Type" value={v.kind ?? 'file'} onChange={(kind) => set({ kind })} options={[{ value: 'file', label: 'Video file' }, { value: 'webcam', label: 'Webcam' }, { value: 'stream', label: 'RTSP / HTTP' }]} />
            )}
          </Field>
          <Field label="Source" hint={v.kind === 'webcam' ? 'Device index, e.g. 0' : v.kind === 'stream' ? 'rtsp://user:pass@host/stream' : 'Path on the server, e.g. data/samples/town_square.mp4'}>
            {(p) => <Input {...p} value={v.uri ?? ''} onChange={(e) => set({ uri: e.target.value })} />}
          </Field>
        </div>
        <div className="flex items-center gap-3">
          <Button size="sm" onClick={runTest} loading={testing} disabled={!v.uri}>
            Test connection
          </Button>
          {test && <span className={test.ok ? 'text-sm text-ok' : 'text-sm text-danger'}>{test.message}</span>}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Analyse every nth frame" hint="2–3 saves CPU on 25–30 fps sources.">
            {(p) => <Input {...p} inputMode="numeric" value={v.stride ?? 1} onChange={(e) => set({ stride: Math.min(10, Math.max(1, Number(e.target.value) || 1)) })} />}
          </Field>
          <Field label="Zone test point">
            {(p) => <Select id={p.id} label="Zone test point" value={v.point_mode ?? 'foot'} onChange={(point_mode) => set({ point_mode })} options={[{ value: 'foot', label: 'Feet (floor zones)' }, { value: 'center', label: 'Body centre' }]} />}
          </Field>
        </div>
        <div className="flex gap-6">
          <label className="flex items-center gap-2 text-sm">
            <Switch label="Enabled" checked={v.enabled ?? true} onChange={(enabled) => set({ enabled })} /> Enabled
          </label>
          {v.kind === 'file' && (
            <label className="flex items-center gap-2 text-sm">
              <Switch label="Loop the file" checked={v.loop ?? true} onChange={(loop) => set({ loop })} /> Loop the file
            </label>
          )}
        </div>
      </div>
    </Dialog>
  )
}

function ThresholdsSection() {
  const t = useThresholds()
  const save = useSaveThresholds()
  const [draft, setDraft] = useState<Thresholds | null>(null)
  useEffect(() => {
    if (t.data) setDraft(structuredClone(t.data))
  }, [t.data])
  if (t.isPending || !draft) return <Section title="Thresholds" help="Loading…"><Skeleton className="h-40" /></Section>
  if (t.isError) return <Section title="Thresholds" help=""><ErrorState error={t.error} /></Section>
  const dirty = JSON.stringify(draft) !== JSON.stringify(t.data)
  return (
    <>
      {(Object.keys(SECTION_TITLES) as (keyof Thresholds)[]).map((sec) => (
        <Section key={sec} title={SECTION_TITLES[sec].title} help={SECTION_TITLES[sec].help}>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {Object.entries(draft[sec] ?? {})
              .filter(([k]) => THRESHOLD_DOCS[sec]?.[k])
              .map(([k, val]) => {
                const doc = THRESHOLD_DOCS[sec][k]
                return (
                  <Field key={k} label={doc.unit ? `${doc.label} (${doc.unit})` : doc.label} hint={doc.help}>
                    {(p) => (
                      <Input
                        {...p}
                        inputMode="decimal"
                        value={String(val)}
                        onChange={(e) => setDraft({ ...draft, [sec]: { ...draft[sec], [k]: e.target.value === '' ? '' : isNaN(Number(e.target.value)) ? val : Number(e.target.value) } })}
                      />
                    )}
                  </Field>
                )
              })}
          </div>
        </Section>
      ))}
      <div className="sticky bottom-0 flex items-center justify-end gap-2 border-t border-line bg-bg py-3">
        {dirty && <span className="mr-auto text-sm text-muted">Unsaved threshold changes</span>}
        <Button variant="ghost" disabled={!dirty} onClick={() => setDraft(structuredClone(t.data!))}>
          Discard
        </Button>
        <Button variant="primary" disabled={!dirty} loading={save.isPending} onClick={() => save.mutate(draft)}>
          Save thresholds
        </Button>
      </div>
    </>
  )
}

function AccountSection() {
  const me = useMe()
  const [cur, setCur] = useState('')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState(false)
  const tooShort = next.length > 0 && next.length < 8
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.post('/auth/password', { current: cur, new: next })
      toast.success('Password changed')
      setCur('')
      setNext('')
    } catch (err) {
      toast.error('Password not changed', { description: (err as Error).message })
    } finally {
      setBusy(false)
    }
  }
  return (
    <Section title="Account" help={`Signed in as ${me.data?.user ?? 'admin'}. Retention (30 days) and head blurring in snapshots are set in config/default.yaml.`}>
      <form onSubmit={submit} className="grid max-w-xl grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Current password">{(p) => <Input {...p} type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} />}</Field>
        <Field label="New password" error={tooShort ? 'Use at least 8 characters.' : undefined}>
          {(p) => <Input {...p} type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />}
        </Field>
        <div>
          <Button type="submit" disabled={!cur || next.length < 8} loading={busy}>
            Change password
          </Button>
        </div>
      </form>
    </Section>
  )
}
