// Polygon helpers for the zone editor. Coordinates are normalised [0, 1] (x right, y down).
export type Pt = [number, number]

export const clamp01 = (v: number) => Math.min(1, Math.max(0, v))

/** Clamp to the frame and snap to an edge when within `tol` of it. */
export function snap([x, y]: Pt, tol = 0.012): Pt {
  const s = (v: number) => (v < tol ? 0 : v > 1 - tol ? 1 : v)
  return [s(clamp01(x)), s(clamp01(y))]
}

export function area(poly: Pt[]): number {
  let a = 0
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i]
    const [x2, y2] = poly[(i + 1) % poly.length]
    a += x1 * y2 - x2 * y1
  }
  return Math.abs(a) / 2
}

const orient = (a: Pt, b: Pt, c: Pt) => Math.sign((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
const onSeg = (a: Pt, b: Pt, p: Pt) =>
  Math.min(a[0], b[0]) <= p[0] && p[0] <= Math.max(a[0], b[0]) && Math.min(a[1], b[1]) <= p[1] && p[1] <= Math.max(a[1], b[1])

export function segmentsIntersect(p1: Pt, p2: Pt, p3: Pt, p4: Pt): boolean {
  const d1 = orient(p3, p4, p1)
  const d2 = orient(p3, p4, p2)
  const d3 = orient(p1, p2, p3)
  const d4 = orient(p1, p2, p4)
  if (d1 !== d2 && d3 !== d4 && d1 !== 0 && d2 !== 0 && d3 !== 0 && d4 !== 0) return true
  return (d1 === 0 && onSeg(p3, p4, p1)) || (d2 === 0 && onSeg(p3, p4, p2)) || (d3 === 0 && onSeg(p1, p2, p3)) || (d4 === 0 && onSeg(p1, p2, p4))
}

/** True when no two non-adjacent edges cross (closed polygon). */
export function isSimple(poly: Pt[]): boolean {
  const n = poly.length
  if (n < 4) return true
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (j === i + 1 || (i === 0 && j === n - 1)) continue
      if (segmentsIntersect(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n])) return false
    }
  }
  return true
}

/** Would the open path `poly` + `next` cross itself? (used while drawing) */
export function pathCrossesWith(poly: Pt[], next: Pt): boolean {
  const n = poly.length
  if (n < 2) return false
  const a = poly[n - 1]
  for (let i = 0; i < n - 2; i++) if (segmentsIntersect(poly[i], poly[i + 1], a, next)) return true
  return false
}

export function pointInPolygon([x, y]: Pt, poly: Pt[]): boolean {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i]
    const [xj, yj] = poly[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

export const MIN_AREA = 0.001

/** Human-readable problems, empty when the polygon can be saved. Mirrors backend validate(). */
export function polygonErrors(poly: Pt[]): string[] {
  const e: string[] = []
  if (poly.length < 3) e.push('A zone needs at least 3 points.')
  else {
    if (!isSimple(poly)) e.push('The outline crosses itself. Move a point so the edges do not cross.')
    if (area(poly) < MIN_AREA) e.push('The zone is too small. Make it cover more of the frame.')
  }
  return e
}

export function distToSegment([px, py]: Pt, [ax, ay]: Pt, [bx, by]: Pt): { d: number; t: number } {
  const dx = bx - ax
  const dy = by - ay
  const len = dx * dx + dy * dy
  const t = len ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len)) : 0
  const cx = ax + t * dx
  const cy = ay + t * dy
  return { d: Math.hypot(px - cx, py - cy), t }
}
