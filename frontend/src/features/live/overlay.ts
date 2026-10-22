// Overlay geometry and drawing for a video tile. Boxes arrive in original frame pixels; the canvas shows the
// frame letterboxed ("contain") inside the tile. Pure functions here are unit-tested (overlay.test.ts).
import type { FrameMeta, LivePerson, LiveZone } from '@/lib/api/types'

export interface Fit {
  scale: number
  ox: number
  oy: number
  w: number
  h: number
}

/** Fit a srcW×srcH frame inside dstW×dstH, centred, keeping aspect ratio. */
export function fitContain(srcW: number, srcH: number, dstW: number, dstH: number): Fit {
  if (srcW <= 0 || srcH <= 0 || dstW <= 0 || dstH <= 0) return { scale: 1, ox: 0, oy: 0, w: 0, h: 0 }
  const scale = Math.min(dstW / srcW, dstH / srcH)
  const w = srcW * scale
  const h = srcH * scale
  return { scale, ox: (dstW - w) / 2, oy: (dstH - h) / 2, w, h }
}

export const toView = (f: Fit, x: number, y: number): [number, number] => [f.ox + x * f.scale, f.oy + y * f.scale]
export const toFrame = (f: Fit, x: number, y: number): [number, number] => [(x - f.ox) / f.scale, (y - f.oy) / f.scale]

/** Topmost (smallest) person box under a point in view coordinates, or null. */
export function hitPerson(f: Fit, persons: LivePerson[], vx: number, vy: number, pad = 4): LivePerson | null {
  const [x, y] = toFrame(f, vx, vy)
  const p = pad / f.scale
  const hits = persons.filter(({ box: [x1, y1, x2, y2] }) => x >= x1 - p && x <= x2 + p && y >= y1 - p && y <= y2 + p)
  hits.sort((a, b) => (a.box[2] - a.box[0]) * (a.box[3] - a.box[1]) - (b.box[2] - b.box[0]) * (b.box[3] - b.box[1]))
  return hits[0] ?? null
}

export interface Layers {
  boxes: boolean
  ppe: boolean
  ids: boolean
  zones: boolean
}

export type PersonTone = 'violation' | 'ok' | 'neutral'

/** A person is red when an incident is open on them, green when every required item is present, else neutral. */
export function personTone(p: LivePerson): PersonTone {
  if (p.violations.length) return 'violation'
  const states = Object.values(p.ppe)
  if (states.length && states.every((s) => s === 'present')) return 'ok'
  return 'neutral'
}

const SHORT: Record<string, string> = { helmet: 'Helmet', vest: 'Vest', gloves: 'Gloves', boots: 'Boots', goggles: 'Goggles' }

function css(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

const ZONE_VAR: Record<LiveZone['kind'], string> = {
  restricted: '--zone-restricted',
  hazard: '--zone-hazard',
  ppe_required: '--zone-ppe',
}

export function drawOverlay(
  ctx: CanvasRenderingContext2D,
  meta: FrameMeta,
  f: Fit,
  layers: Layers,
  selected: number | null,
  dpr: number,
) {
  const c = {
    person: css('--ov-person'),
    ok: css('--ov-ok'),
    danger: css('--ov-danger'),
    labelBg: css('--ov-label-bg'),
    accent: css('--accent'),
  }
  ctx.save()
  ctx.scale(dpr, dpr)
  if (layers.zones) {
    for (const z of meta.zones) {
      const color = css(ZONE_VAR[z.kind] ?? '--zone-hazard')
      ctx.beginPath()
      z.polygon.forEach(([nx, ny], i) => {
        const [x, y] = toView(f, nx * meta.width, ny * meta.height)
        if (i) ctx.lineTo(x, y)
        else ctx.moveTo(x, y)
      })
      ctx.closePath()
      ctx.globalAlpha = 0.2
      ctx.fillStyle = color
      ctx.fill()
      ctx.globalAlpha = 1
      ctx.lineWidth = 1.5
      ctx.strokeStyle = color
      ctx.stroke()
      const [lx, ly] = toView(f, z.polygon[0][0] * meta.width, z.polygon[0][1] * meta.height)
      label(ctx, z.name, lx + 4, ly + 4, color, c.labelBg, 'top')
    }
  }
  ctx.font = '500 11px "IBM Plex Mono", monospace'
  for (const p of meta.persons) {
    const [x1, y1] = toView(f, p.box[0], p.box[1])
    const [x2, y2] = toView(f, p.box[2], p.box[3])
    const tone = personTone(p)
    const color = tone === 'violation' ? c.danger : tone === 'ok' ? c.ok : c.person
    if (layers.boxes) {
      ctx.lineWidth = p.track_id === selected ? 2.5 : tone === 'violation' ? 2 : 1.25
      ctx.strokeStyle = p.track_id === selected ? c.accent : color
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
    }
    if (layers.ids) label(ctx, `#${p.track_id}`, x1, y1 - 2, color, c.labelBg, 'bottom')
    if (layers.ppe) {
      let y = y1 + 2
      for (const [item, state] of Object.entries(p.ppe)) {
        if (state === 'unknown') continue
        const name = SHORT[item] ?? item
        const text = state === 'present' ? name : `No ${name.toLowerCase()}`
        label(ctx, text, x2 + 3, y, state === 'present' ? c.ok : c.danger, c.labelBg, 'top')
        y += 16
      }
    }
  }
  ctx.restore()
}

function label(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  color: string,
  bg: string,
  anchor: 'top' | 'bottom',
) {
  ctx.font = '500 11px "IBM Plex Mono", monospace'
  const w = ctx.measureText(text).width + 8
  const h = 15
  const top = anchor === 'top' ? y : y - h
  ctx.fillStyle = bg
  ctx.fillRect(x, top, w, h)
  ctx.fillStyle = color
  ctx.textBaseline = 'middle'
  ctx.fillText(text, x + 4, top + h / 2 + 0.5)
}
