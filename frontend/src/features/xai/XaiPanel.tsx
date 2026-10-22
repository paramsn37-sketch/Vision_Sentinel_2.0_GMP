import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Button, ErrorState, SegmentedControl, Skeleton, Slider } from '@/components/ui'
import { api, url, type XaiJob } from '@/lib/api/client'
import { colorize } from './colormap'

export interface XaiTarget {
  source: 'live' | 'incident' | 'upload'
  camera_id?: string
  frame_idx?: number
  incident_id?: string
  upload_id?: string
  box?: [number, number, number, number]
  cls?: string
}

type Method = 'gradcam' | 'eigencam'

/** Request an explanation for one detection, show original vs heat with an opacity slider, and say what it means. */
export function XaiPanel({ target, onFeedback }: { target: XaiTarget; onFeedback?: (wrong: boolean) => void }) {
  const [method, setMethod] = useState<Method>('gradcam')
  const [opacity, setOpacity] = useState(0.6)
  const request = useMutation({ mutationFn: (m: Method) => api.post<XaiJob>('/xai', { ...target, method: m }) })
  const jobId = request.data?.id
  const job = useQuery({
    queryKey: ['xai', jobId],
    queryFn: () => api.get<XaiJob>(`/xai/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && ['done', 'failed'].includes(q.state.data.status) ? false : 400),
  })
  const key = JSON.stringify(target)
  // Ask once per target and method; the backend caches by frame, box, class and method.
  const { mutate } = request
  useEffect(() => {
    mutate(method)
  }, [key, method, mutate])

  const data = job.data
  const meta = (data?.meta ?? null) as null | {
    method: string
    target_class: string | null
    target_box: [number, number, number, number] | null
    energy_in_box: number | null
    peak_in_box: boolean | null
    anchor_score: number | null
    ms: number
  }
  const err = request.error ?? job.error ?? (data?.status === 'failed' ? new Error(data.error ?? 'The explanation failed.') : null)

  return (
    <section className="flex flex-col gap-3" aria-label="Explanation">
      <div className="flex items-center justify-between gap-3">
        <SegmentedControl
          label="Explanation method"
          value={method}
          onChange={setMethod}
          options={[
            { value: 'gradcam', label: 'Grad-CAM (this detection)' },
            { value: 'eigencam', label: 'EigenCAM (whole frame)' },
          ]}
        />
      </div>
      {err ? (
        <ErrorState error={err} onRetry={() => request.mutate(method)} />
      ) : data?.status !== 'done' || !jobId ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="aspect-video w-full" />
          <p className="text-xs text-muted">Computing on the CPU. This usually takes under a second per detection.</p>
        </div>
      ) : (
        <>
          <HeatView jobId={jobId} opacity={opacity} box={method === 'gradcam' ? (meta?.target_box ?? undefined) : undefined} />
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted">Heat</span>
            <Slider label="Heatmap opacity" value={opacity} onChange={setOpacity} />
            <span className="num w-10 text-right text-xs">{Math.round(opacity * 100)}%</span>
          </div>
          {meta && <Reading meta={meta} />}
          {onFeedback && (
            <div className="flex items-center gap-2 border-t border-line pt-3">
              <span className="text-xs text-muted">Was this alert right?</span>
              <Button size="sm" variant="ghost" onClick={() => onFeedback(false)}>
                Correct
              </Button>
              <Button size="sm" variant="ghost" onClick={() => onFeedback(true)}>
                This alert was wrong
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  )
}

function Reading({ meta }: { meta: { method: string; target_class: string | null; energy_in_box: number | null; peak_in_box: boolean | null; anchor_score: number | null; ms: number } }) {
  const e = meta.energy_in_box
  const sentence =
    e === null
      ? 'EigenCAM shows what the network attends to in the whole frame; it is not tied to one detection.'
      : e >= 0.5
        ? `${Math.round(e * 100)}% of the evidence lies inside the box${meta.peak_in_box ? ', and the strongest point is on the person' : ''}. The model looked at the right place.`
        : `Only ${Math.round(e * 100)}% of the evidence lies inside the box. The model may be relying on surroundings; treat this alert with care.`
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm">{sentence}</p>
      <dl className="grid grid-cols-3 gap-3 text-xs">
        <div>
          <dt className="text-muted">Class</dt>
          <dd className="text-sm">{meta.target_class ?? 'all'}</dd>
        </div>
        <div>
          <dt className="text-muted">Detection score</dt>
          <dd className="num text-sm">{meta.anchor_score === null ? '—' : meta.anchor_score.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="text-muted">Computed in</dt>
          <dd className="num text-sm">{Math.round(meta.ms)} ms</dd>
        </div>
      </dl>
    </div>
  )
}

function HeatView({ jobId, opacity, box }: { jobId: string; opacity: number; box?: [number, number, number, number] }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const imgs = useRef<{ src: HTMLImageElement; heat: HTMLImageElement } | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let alive = true
    const load = (u: string) =>
      new Promise<HTMLImageElement>((res, rej) => {
        const i = new Image()
        i.onload = () => res(i)
        i.onerror = () => rej(new Error('image failed to load'))
        i.src = u
      })
    Promise.all([load(url(`/xai/${jobId}/source`)), load(url(`/xai/${jobId}/heatmap`))]).then(([src, heat]) => {
      if (!alive) return
      imgs.current = { src, heat }
      setReady(true)
    })
    return () => {
      alive = false
    }
  }, [jobId])

  useEffect(() => {
    const cv = canvas.current
    const im = imgs.current
    if (!cv || !im || !ready) return
    const { src, heat } = im
    cv.width = src.naturalWidth
    cv.height = src.naturalHeight
    const ctx = cv.getContext('2d')!
    ctx.drawImage(src, 0, 0)
    const off = document.createElement('canvas')
    off.width = cv.width
    off.height = cv.height
    const octx = off.getContext('2d')!
    octx.drawImage(heat, 0, 0, cv.width, cv.height)
    const d = octx.getImageData(0, 0, cv.width, cv.height)
    colorize(d.data, opacity)
    octx.putImageData(d, 0, 0)
    ctx.drawImage(off, 0, 0)
    if (box) {
      ctx.lineWidth = Math.max(2, cv.width / 400)
      ctx.strokeStyle = '#ffffff'
      ctx.setLineDash([8, 6])
      ctx.strokeRect(box[0], box[1], box[2] - box[0], box[3] - box[1])
    }
  }, [ready, opacity, box])

  return (
    <div className="overflow-hidden rounded-sm border border-line bg-black">
      {!ready && <Skeleton className="aspect-video w-full" />}
      <canvas ref={canvas} className="block h-auto w-full" role="img" aria-label="Frame with the explanation heatmap blended over it" hidden={!ready} />
      <div className="flex items-center gap-2 px-2 py-1.5 text-[11px] text-muted">
        <span>low</span>
        <span className="h-1.5 flex-1 rounded-full" style={{ background: 'linear-gradient(90deg, rgb(13 8 60), rgb(33 82 140), rgb(32 146 140), rgb(148 200 70), rgb(250 230 60))' }} aria-hidden />
        <span>high evidence</span>
      </div>
    </div>
  )
}
