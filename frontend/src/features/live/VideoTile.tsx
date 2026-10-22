import { Pause, Play } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { cn, IconButton, StatusPill } from '@/components/ui'
import type { Camera } from '@/lib/api/client'
import type { FrameMeta } from '@/lib/api/types'
import { connectLive } from '@/lib/ws'
import { useLive } from '@/stores/live'
import { drawOverlay, fitContain, hitPerson, type Layers } from './overlay'

export interface Selection {
  cameraId: string
  trackId: number
}

/** One camera: JPEG frames decoded into a canvas, overlays drawn from the metadata of the same frame.
 *  Pausing freezes the frame and its metadata so a person on it can be explained. */
export function VideoTile({
  camera,
  layers,
  selected,
  onSelect,
  fps = 12,
  onPausedChange,
}: {
  camera: Camera
  layers: Layers
  selected: Selection | null
  onSelect: (s: Selection | null, meta: FrameMeta | null) => void
  fps?: number
  onPausedChange?: (paused: boolean, meta: FrameMeta | null) => void
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const bitmap = useRef<ImageBitmap | null>(null)
  const meta = useRef<FrameMeta | null>(null)
  const paused = useRef(false)
  const [isPaused, setPaused] = useState(false)
  const [status, setStatus] = useState<string>('connecting')
  const [hasFrame, setHasFrame] = useState(false)
  const [info, setInfo] = useState<{ fps: number; people: number; unique: number } | null>(null)
  const setFrame = useLive((s) => s.setFrame)
  const selTrack = selected?.cameraId === camera.id ? selected.trackId : null
  const selRef = useRef(selTrack)
  const layersRef = useRef(layers)

  const draw = () => {
    const cv = canvas.current
    const el = wrap.current
    if (!cv || !el) return
    const dpr = window.devicePixelRatio || 1
    const { width, height } = el.getBoundingClientRect()
    if (cv.width !== Math.round(width * dpr) || cv.height !== Math.round(height * dpr)) {
      cv.width = Math.round(width * dpr)
      cv.height = Math.round(height * dpr)
    }
    const ctx = cv.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, cv.width, cv.height)
    const m = meta.current
    const b = bitmap.current
    if (!m || !b) return
    const f = fitContain(m.width, m.height, width, height)
    ctx.drawImage(b, f.ox * dpr, f.oy * dpr, f.w * dpr, f.h * dpr)
    drawOverlay(ctx, m, f, layersRef.current, selRef.current, dpr)
  }

  useEffect(() => {
    selRef.current = selTrack
    layersRef.current = layers
    draw()
  })

  useEffect(() => {
    const ro = new ResizeObserver(() => draw())
    if (wrap.current) ro.observe(wrap.current)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    let alive = true
    const conn = connectLive(
      camera.id,
      fps,
      async (m, jpeg) => {
        setFrame(m)
        if (paused.current) return
        const bmp = await createImageBitmap(jpeg).catch(() => null)
        if (!alive || !bmp || paused.current) return
        bitmap.current?.close()
        bitmap.current = bmp
        meta.current = m
        draw()
        setHasFrame(true)
        setStatus('running')
        setInfo({ fps: m.fps, people: m.counts.current, unique: m.counts.unique_total })
      },
      (s) => setStatus(s.status),
      (s) => s === 'closed' && setStatus('reconnecting'),
    )
    return () => {
      alive = false
      conn.close()
      bitmap.current?.close()
      bitmap.current = null
    }
  }, [camera.id, fps, setFrame])

  const togglePause = () => {
    paused.current = !paused.current
    setPaused(paused.current)
    onPausedChange?.(paused.current, meta.current)
  }
  const toggleRef = useRef(togglePause)
  useEffect(() => {
    toggleRef.current = togglePause
  })

  // Space pauses the tile whose person is selected (the "Pause to inspect" shortcut), unless typing.
  const hasSelection = selTrack !== null
  useEffect(() => {
    if (!hasSelection) return
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (e.key !== ' ' || e.repeat || t.closest('input, textarea, select, button, [role="application"]')) return
      e.preventDefault()
      toggleRef.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [hasSelection])

  const onClick = (e: React.MouseEvent) => {
    const m = meta.current
    const el = wrap.current
    if (!m || !el) return
    const r = el.getBoundingClientRect()
    const p = hitPerson(fitContain(m.width, m.height, r.width, r.height), m.persons, e.clientX - r.left, e.clientY - r.top)
    onSelect(p ? { cameraId: camera.id, trackId: p.track_id } : null, m)
  }

  const tone = status === 'running' ? 'ok' : status === 'error' ? 'danger' : 'neutral'
  const statusLabel =
    { running: 'Live', stopped: 'Stopped', error: 'Error', connecting: 'Connecting', reconnecting: 'Reconnecting', starting: 'Starting' }[status] ?? status

  return (
    <figure className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-md border border-line bg-sunken" aria-label={`Camera ${camera.name}`}>
      <figcaption className="flex h-10 shrink-0 items-center gap-3 border-b border-line px-3">
        <span className="truncate text-sm font-medium">{camera.name}</span>
        <StatusPill tone={isPaused ? 'info' : tone}>{isPaused ? 'Paused' : statusLabel}</StatusPill>
        <div className="ml-auto flex items-center gap-4 text-xs text-muted">
          {info && (
            <>
              <span>
                <span className="num text-fg">{info.people}</span> now
              </span>
              <span title="Distinct confirmed people since this camera started">
                <span className="num text-fg">{info.unique}</span> unique
              </span>
              <span>
                <span className="num text-fg">{info.fps.toFixed(1)}</span> fps
              </span>
            </>
          )}
          <IconButton size="sm" label={isPaused ? 'Resume' : 'Pause to inspect'} shortcut="Space" onClick={togglePause} data-pause={camera.id}>
            {isPaused ? <Play className="size-4" /> : <Pause className="size-4" />}
          </IconButton>
        </div>
      </figcaption>
      <div ref={wrap} className={cn('relative min-h-0 flex-1 bg-black', isPaused && 'cursor-crosshair')} onClick={onClick}>
        <canvas ref={canvas} className="absolute inset-0 size-full" role="img" aria-label={`Live view of ${camera.name} with detections`} />
        {!hasFrame && (
          <div className="absolute inset-0 grid place-items-center text-sm text-muted">
            {status === 'stopped' ? 'Camera stopped. Start it in Settings.' : status === 'error' ? camera.error ?? 'The source could not be read.' : 'Waiting for the first frame…'}
          </div>
        )}
      </div>
    </figure>
  )
}
