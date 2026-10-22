import { Minus, Plus, Scan } from 'lucide-react'
import { useEffect, useRef, useState, type Dispatch } from 'react'
import { IconButton, cn } from '@/components/ui'
import { distToSegment, type Pt } from './geometry'
import type { Action, EditorState } from './reducer'

export interface ZoneShape {
  id: string
  name: string
  color: string
  points: Pt[]
}

const NUDGE = 0.002
const NUDGE_BIG = 0.01
const HIT_PX = 10 // visible vertex hit radius (screen px)

/** Frozen camera frame with the polygon being edited. Pointer + keyboard + touch; zoom (wheel, buttons) and pan
 *  (space-drag or middle button). Coordinates are converted to normalised [0, 1] against the image box. */
export function ZoneCanvas({
  image,
  state,
  dispatch,
  color,
  others,
  people,
  onCommitDraw,
}: {
  image: string
  state: EditorState
  dispatch: Dispatch<Action>
  color: string
  others: ZoneShape[]
  people: { id: number; foot: Pt; inside: boolean }[]
  onCommitDraw?: () => void
}) {
  const frame = useRef<HTMLDivElement>(null)
  const img = useRef<HTMLImageElement>(null)
  const [size, setSize] = useState<[number, number] | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState<[number, number]>([0, 0])
  const [hover, setHover] = useState<Pt | null>(null)
  const [spaceDown, setSpaceDown] = useState(false)
  const drag = useRef<null | { kind: 'vertex'; index: number } | { kind: 'body'; last: Pt } | { kind: 'pan'; x: number; y: number; moved: boolean }>(null)
  const spacePanned = useRef(false)

  const [W, H] = size ?? [16, 9]
  const toNorm = (cx: number, cy: number): Pt => {
    const r = img.current!.getBoundingClientRect()
    return [(cx - r.left) / r.width, (cy - r.top) / r.height]
  }
  const pxPerNorm = () => img.current?.getBoundingClientRect().width ?? 1

  useEffect(() => {
    setZoom(1)
    setPan([0, 0])
  }, [image])

  // Fit the frame inside the canvas area ("contain") in CSS pixels.
  const [box, setBox] = useState<[number, number]>([0, 0])
  useEffect(() => {
    const el = frame.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => {
      const { width, height } = e.contentRect
      const s = Math.min(width / W, height / H)
      setBox([W * s, H * s])
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [W, H])

  const onPointerDown = (e: React.PointerEvent) => {
    frame.current?.focus({ preventScroll: true })
    if (e.button === 1 || spaceDown) {
      drag.current = { kind: 'pan', x: e.clientX, y: e.clientY, moved: false }
      ;(e.target as Element).setPointerCapture(e.pointerId)
      return
    }
    if (e.button !== 0) return
    const p = toNorm(e.clientX, e.clientY)
    if (state.mode === 'drawing') {
      dispatch({ type: 'add', p })
      return
    }
    if (state.mode !== 'editing') return
    const scale = pxPerNorm()
    const aspect = H / W
    // Vertex first (generous radius), then edges (insert), then the body (move).
    const vi = state.points.findIndex(([x, y]) => Math.hypot((x - p[0]) * scale, (y - p[1]) * scale * aspect) <= HIT_PX + 2)
    if (vi >= 0) {
      dispatch({ type: 'select', index: vi })
      dispatch({ type: 'beginDrag' })
      drag.current = { kind: 'vertex', index: vi }
      ;(e.target as Element).setPointerCapture(e.pointerId)
      return
    }
    for (let i = 0; i < state.points.length; i++) {
      const a = state.points[i]
      const b = state.points[(i + 1) % state.points.length]
      const sa: Pt = [a[0], a[1] * aspect]
      const sb: Pt = [b[0], b[1] * aspect]
      if (distToSegment([p[0], p[1] * aspect], sa, sb).d * scale <= 6) {
        dispatch({ type: 'insert', after: i, p })
        dispatch({ type: 'beginDrag' })
        drag.current = { kind: 'vertex', index: i + 1 }
        ;(e.target as Element).setPointerCapture(e.pointerId)
        return
      }
    }
    if ((e.target as Element).getAttribute('data-body') === 'true') {
      dispatch({ type: 'select', index: null })
      dispatch({ type: 'beginDrag' })
      drag.current = { kind: 'body', last: p }
      ;(e.target as Element).setPointerCapture(e.pointerId)
      return
    }
    dispatch({ type: 'select', index: null })
  }

  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current
    if (d?.kind === 'pan') {
      d.moved = true
      spacePanned.current = true
      setPan(([x, y]) => [x + e.clientX - d.x, y + e.clientY - d.y])
      d.x = e.clientX
      d.y = e.clientY
      return
    }
    if (!img.current) return
    const p = toNorm(e.clientX, e.clientY)
    setHover(p)
    if (d?.kind === 'vertex') dispatch({ type: 'drag', index: d.index, p })
    else if (d?.kind === 'body') {
      dispatch({ type: 'move', dx: p[0] - d.last[0], dy: p[1] - d.last[1] })
      d.last = p
    }
  }

  const onPointerUp = () => {
    drag.current = null
  }

  const onWheel = (e: React.WheelEvent) => {
    if (!frame.current) return
    const r = frame.current.getBoundingClientRect()
    const mx = e.clientX - r.left - r.width / 2
    const my = e.clientY - r.top - r.height / 2
    const next = Math.min(6, Math.max(1, zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15)))
    const k = next / zoom
    setZoom(next)
    setPan(([x, y]) => (next === 1 ? [0, 0] : [mx - (mx - x) * k, my - (my - y) * k]))
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    const mod = e.metaKey || e.ctrlKey
    const step = e.shiftKey ? NUDGE_BIG : NUDGE
    const k = e.key
    let handled = true
    if (mod && k.toLowerCase() === 'z') dispatch({ type: e.shiftKey ? 'redo' : 'undo' })
    else if (mod && k.toLowerCase() === 'y') dispatch({ type: 'redo' })
    else if (k === 'Enter') {
      if (state.mode === 'drawing') {
        dispatch({ type: 'close' })
        onCommitDraw?.()
      } else handled = false
    } else if (k === 'Escape') dispatch({ type: 'cancel' })
    else if (k === 'Delete' || k === 'Backspace') dispatch({ type: 'delete' })
    else if (k === 'ArrowLeft') dispatch({ type: 'nudge', dx: -step, dy: 0 })
    else if (k === 'ArrowRight') dispatch({ type: 'nudge', dx: step, dy: 0 })
    else if (k === 'ArrowUp') dispatch({ type: 'nudge', dx: 0, dy: -step })
    else if (k === 'ArrowDown') dispatch({ type: 'nudge', dx: 0, dy: step })
    else if (k === ']' || k === '[') {
      if (state.mode === 'editing' && state.points.length) {
        const n = state.points.length
        const cur = state.selected ?? (k === ']' ? -1 : 0)
        dispatch({ type: 'select', index: (cur + (k === ']' ? 1 : n - 1)) % n })
      }
    } else if (k === ' ') {
      if (!e.repeat) {
        spacePanned.current = false
        setSpaceDown(true)
      }
    } else if (k === '+' || k === '=') setZoom((z) => Math.min(6, z * 1.25))
    else if (k === '-') setZoom((z) => (z / 1.25 <= 1.01 ? (setPan([0, 0]), 1) : z / 1.25))
    else handled = false
    if (handled) {
      e.preventDefault()
      e.stopPropagation()
    }
  }

  const onKeyUp = (e: React.KeyboardEvent) => {
    if (e.key !== ' ') return
    setSpaceDown(false)
    // Space without dragging adds a point at the keyboard cursor while drawing.
    if (!spacePanned.current && state.mode === 'drawing') dispatch({ type: 'add', p: state.cursor })
    e.preventDefault()
  }

  const pts = (p: Pt[]) => p.map(([x, y]) => `${x * W},${y * H}`).join(' ')
  // Handle radius in image pixels so it stays ~HIT_PX on screen at any zoom.
  const r = (HIT_PX / Math.max(zoom, 1)) * (W / Math.max(box[0], 1)) * 0.55
  const last = state.points[state.points.length - 1]
  const rubber = state.mode === 'drawing' && last ? (hover ?? state.cursor) : null
  const help =
    state.mode === 'drawing'
      ? 'Click to add points. Click the first point or press Enter to close. Arrow keys move the cursor and Space adds a point. Backspace removes the last point, Esc cancels.'
      : state.mode === 'editing'
        ? 'Drag a point to move it, click an edge to add a point, drag inside to move the zone. [ and ] select points, arrows nudge (Shift for larger steps), Delete removes the selected point. Ctrl+Z undoes.'
        : 'Choose a zone from the list or draw a new one.'

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div
        ref={frame}
        tabIndex={0}
        role="application"
        aria-label="Zone editor. Use the keyboard as described below the canvas."
        aria-describedby="zone-help"
        onKeyDown={onKeyDown}
        onKeyUp={onKeyUp}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onPointerLeave={() => setHover(null)}
        className={cn(
          'relative grid min-h-0 flex-1 touch-none place-items-center overflow-hidden rounded-md border border-line bg-black outline-none select-none focus-visible:ring-2 focus-visible:ring-accent',
          state.mode === 'drawing' && 'cursor-crosshair',
          spaceDown && 'cursor-grab',
        )}
        data-testid="zone-canvas"
      >
        <div className="relative" style={{ transform: `translate(${pan[0]}px, ${pan[1]}px) scale(${zoom})`, width: box[0], height: box[1] }}>
          <img
            ref={img}
            src={image}
            alt="Frozen camera frame"
            draggable={false}
            onLoad={(e) => setSize([e.currentTarget.naturalWidth, e.currentTarget.naturalHeight])}
            className="block size-full object-contain"
          />
          {size && (
            <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 size-full overflow-visible" aria-hidden>
              {others.map((z) => (
                <g key={z.id}>
                  <polygon points={pts(z.points)} fill={z.color} fillOpacity={0.12} stroke={z.color} strokeOpacity={0.6} strokeWidth={1.5} vectorEffect="non-scaling-stroke" strokeDasharray="6 4" />
                </g>
              ))}
              {people.map((p) => (
                // Feet of people in the latest frame: small solid dots, deliberately unlike the hollow vertex handles.
                <circle key={p.id} cx={p.foot[0] * W} cy={p.foot[1] * H} r={r * 0.38} fill={p.inside ? 'var(--ov-danger)' : 'var(--ov-person)'} fillOpacity={0.9} />
              ))}
              {state.points.length > 0 &&
                (state.mode === 'drawing' ? (
                  <polyline points={pts(state.points)} fill="none" stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke" />
                ) : (
                  <polygon
                    data-body="true"
                    points={pts(state.points)}
                    fill={color}
                    fillOpacity={0.2}
                    stroke={color}
                    strokeWidth={2}
                    vectorEffect="non-scaling-stroke"
                    style={{ pointerEvents: 'all', cursor: state.mode === 'editing' ? 'move' : undefined }}
                  />
                ))}
              {rubber && last && (
                <line x1={last[0] * W} y1={last[1] * H} x2={rubber[0] * W} y2={rubber[1] * H} stroke={color} strokeWidth={1.5} strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
              )}
              {state.points.map(([x, y], i) => (
                <circle
                  key={i}
                  data-vertex={i}
                  cx={x * W}
                  cy={y * H}
                  r={i === state.selected ? r * 1.25 : r}
                  fill={i === state.selected ? color : '#0b0b0d'}
                  stroke={i === 0 && state.mode === 'drawing' ? '#fff' : color}
                  strokeWidth={2}
                  vectorEffect="non-scaling-stroke"
                  style={{ cursor: state.mode === 'editing' ? 'grab' : undefined }}
                />
              ))}
              {state.mode === 'drawing' && (
                <g>
                  <line x1={state.cursor[0] * W - r * 2} x2={state.cursor[0] * W + r * 2} y1={state.cursor[1] * H} y2={state.cursor[1] * H} stroke="#fff" strokeWidth={1} vectorEffect="non-scaling-stroke" />
                  <line y1={state.cursor[1] * H - r * 2} y2={state.cursor[1] * H + r * 2} x1={state.cursor[0] * W} x2={state.cursor[0] * W} stroke="#fff" strokeWidth={1} vectorEffect="non-scaling-stroke" />
                </g>
              )}
            </svg>
          )}
        </div>
        <div className="absolute right-2 bottom-2 flex items-center gap-1 rounded-sm border border-line bg-raised/90 p-0.5">
          <IconButton size="sm" label="Zoom out" shortcut="-" onClick={() => setZoom((z) => (z / 1.25 <= 1.01 ? (setPan([0, 0]), 1) : z / 1.25))}>
            <Minus className="size-4" />
          </IconButton>
          <span className="num w-10 text-center text-xs text-muted">{Math.round(zoom * 100)}%</span>
          <IconButton size="sm" label="Zoom in" shortcut="+" onClick={() => setZoom((z) => Math.min(6, z * 1.25))}>
            <Plus className="size-4" />
          </IconButton>
          <IconButton size="sm" label="Fit to view" onClick={() => (setZoom(1), setPan([0, 0]))}>
            <Scan className="size-4" />
          </IconButton>
        </div>
        {state.message && (
          <p role="alert" className="absolute top-2 left-2 rounded-sm bg-danger-bg px-2 py-1 text-xs text-danger">
            {state.message}
          </p>
        )}
      </div>
      <p id="zone-help" className="text-xs text-muted">
        {help}
      </p>
    </div>
  )
}
