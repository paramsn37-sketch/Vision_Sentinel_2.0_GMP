import { useState } from 'react'
import { Button, Drawer, ErrorState, Skeleton, StatusPill, TabList, TabPanel, Tabs, Textarea } from '@/components/ui'
import { url } from '@/lib/api/client'
import { useIncident, usePatchIncident } from '@/lib/api/hooks'
import { absoluteTime, duration, relativeTime, ruleLabel, severityLabel, severityTone, statusLabel, statusTone } from '@/lib/format'
import { XaiPanel } from '@/features/xai/XaiPanel'

export function IncidentDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const q = useIncident(id)
  const patch = usePatchIncident()
  const [note, setNote] = useState('')
  const [tab, setTab] = useState('evidence')
  const i = q.data

  return (
    <Drawer
      open={!!id}
      onOpenChange={(v) => !v && onClose()}
      title={i ? ruleLabel(i.rule) : 'Incident'}
      description={i ? `${i.id} · ${i.zone_name ?? 'whole frame'} · ${i.camera_name ?? i.camera_id}` : id ?? undefined}
      footer={
        i && (
          <>
            <Button variant="primary" disabled={i.status !== 'open'} loading={patch.isPending && patch.variables?.status === 'acknowledged'} onClick={() => patch.mutate({ id: i.id, status: 'acknowledged' })}>
              Acknowledge
            </Button>
            <Button disabled={i.status === 'resolved'} onClick={() => patch.mutate({ id: i.id, status: 'resolved' })}>
              Resolve
            </Button>
            {i.status === 'resolved' && (
              <Button variant="ghost" onClick={() => patch.mutate({ id: i.id, status: 'open' })}>
                Reopen
              </Button>
            )}
          </>
        )
      }
    >
      {q.isPending ? (
        <div className="flex flex-col gap-3 p-5">
          <Skeleton className="aspect-video w-full" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : i ? (
        <div className="flex flex-col gap-4 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill tone={severityTone(i.severity)}>{severityLabel(i.severity)}</StatusPill>
            <StatusPill tone={statusTone(i.status)}>{statusLabel(i.status)}</StatusPill>
            {i.active && <StatusPill tone="danger">Ongoing</StatusPill>}
            {i.feedback === 'false_alarm' && <StatusPill tone="neutral">Marked as wrong</StatusPill>}
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div>
              <dt className="text-xs text-muted">Started</dt>
              <dd title={absoluteTime(i.started_at)}>
                <span className="num">{absoluteTime(i.started_at)}</span> <span className="text-muted">({relativeTime(i.started_at)})</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Duration</dt>
              <dd className="num">{duration(i.duration_s)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Person</dt>
              <dd className="num">{i.track_id !== null ? `#${i.track_id}` : 'zone-wide'}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Peak confidence</dt>
              <dd className="num">{(i.peak_conf * 100).toFixed(0)}%</dd>
            </div>
          </dl>
          <Tabs value={tab} onValueChange={setTab}>
            <TabList
              tabs={[
                { value: 'evidence', label: 'Evidence' },
                { value: 'explain', label: 'Explanation' },
                { value: 'notes', label: `Timeline (${i.notes.length})` },
              ]}
            />
            <TabPanel value="evidence" className="pt-4">
              {i.has_snapshot ? (
                <img src={url(`/incidents/${i.id}/evidence`)} alt={`Evidence frame for ${ruleLabel(i.rule)}`} className="w-full rounded-sm border border-line" />
              ) : (
                <p className="text-sm text-muted">The evidence frame is saved within a second of the incident opening. If it is still missing, the camera stopped before it could be written.</p>
              )}
            </TabPanel>
            <TabPanel value="explain" className="pt-4">
              {i.has_snapshot && i.box ? (
                <XaiPanel
                  target={{ source: 'incident', incident_id: i.id }}
                  onFeedback={(wrong) => patch.mutate({ id: i.id, feedback: wrong ? 'false_alarm' : 'correct', note: wrong ? 'Operator marked this alert as wrong' : undefined })}
                />
              ) : (
                <p className="text-sm text-muted">
                  {i.box ? 'Waiting for the evidence frame.' : 'This rule applies to the whole zone (for example over capacity), so there is no single detection to explain.'}
                </p>
              )}
            </TabPanel>
            <TabPanel value="notes" className="flex flex-col gap-3 pt-4">
              <ol className="flex flex-col gap-2">
                <li className="text-sm">
                  <span className="num text-xs text-muted">{absoluteTime(i.started_at)}</span> Opened by the {ruleLabel(i.rule).toLowerCase()} rule
                </li>
                {i.notes.map((n, k) => (
                  <li key={k} className="text-sm">
                    <span className="num text-xs text-muted">{absoluteTime(String(n.at))}</span>{' '}
                    <span className={n.system ? 'text-muted' : ''}>{String(n.text)}</span> <span className="text-xs text-subtle">· {String(n.user)}</span>
                  </li>
                ))}
              </ol>
              <form
                className="flex flex-col gap-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (!note.trim()) return
                  patch.mutate({ id: i.id, note: note.trim() }, { onSuccess: () => setNote('') })
                }}
              >
                <label htmlFor="inc-note" className="text-xs font-medium text-muted">
                  Add a note
                </label>
                <Textarea id="inc-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="What did you check or do?" maxLength={1000} />
                <div>
                  <Button type="submit" size="sm" disabled={!note.trim()} loading={patch.isPending && !!patch.variables?.note}>
                    Add note
                  </Button>
                </div>
              </form>
            </TabPanel>
          </Tabs>
        </div>
      ) : null}
    </Drawer>
  )
}
