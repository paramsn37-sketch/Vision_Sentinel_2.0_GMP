// Zone editor state machine: idle → drawing → editing, with undo/redo of polygon edits.
import { pathCrossesWith, polygonErrors, snap, type Pt } from './geometry'

export type Mode = 'idle' | 'drawing' | 'editing'

export interface EditorState {
  mode: Mode
  points: Pt[]
  selected: number | null // selected vertex
  cursor: Pt // keyboard drawing cursor
  past: Pt[][]
  future: Pt[][]
  message: string | null // inline message (e.g. "edges would cross")
}

export type Action =
  | { type: 'start' }
  | { type: 'load'; points: Pt[] }
  | { type: 'clear' }
  | { type: 'add'; p: Pt }
  | { type: 'close' }
  | { type: 'cancel' }
  | { type: 'select'; index: number | null }
  | { type: 'beginDrag' }
  | { type: 'drag'; index: number; p: Pt }
  | { type: 'move'; dx: number; dy: number } // whole polygon (drag or nudge without a selected vertex)
  | { type: 'nudge'; dx: number; dy: number } // selected vertex, or whole polygon, or the drawing cursor
  | { type: 'insert'; after: number; p: Pt }
  | { type: 'delete' }
  | { type: 'cursor'; p: Pt }
  | { type: 'undo' }
  | { type: 'redo' }

export const initial: EditorState = { mode: 'idle', points: [], selected: null, cursor: [0.5, 0.5], past: [], future: [], message: null }

const HISTORY = 100
const commit = (s: EditorState, points: Pt[], extra: Partial<EditorState> = {}): EditorState => ({
  ...s,
  points,
  past: [...s.past, s.points].slice(-HISTORY),
  future: [],
  message: null,
  ...extra,
})

const shift = (points: Pt[], dx: number, dy: number): Pt[] => {
  // Move as a block: clamp the offset so no vertex leaves the frame.
  const minX = Math.min(...points.map((p) => p[0]))
  const maxX = Math.max(...points.map((p) => p[0]))
  const minY = Math.min(...points.map((p) => p[1]))
  const maxY = Math.max(...points.map((p) => p[1]))
  const cx = Math.max(-minX, Math.min(1 - maxX, dx))
  const cy = Math.max(-minY, Math.min(1 - maxY, dy))
  return points.map(([x, y]) => [x + cx, y + cy])
}

export function reducer(s: EditorState, a: Action): EditorState {
  switch (a.type) {
    case 'start':
      return { ...initial, mode: 'drawing', cursor: s.cursor }
    case 'load':
      return { ...initial, mode: a.points.length >= 3 ? 'editing' : 'idle', points: a.points }
    case 'clear':
      return initial
    case 'add': {
      if (s.mode !== 'drawing') return s
      const p = snap(a.p)
      const first = s.points[0]
      // Clicking near the first point closes the shape.
      if (first && s.points.length >= 3 && Math.hypot(p[0] - first[0], p[1] - first[1]) < 0.015) return reducer(s, { type: 'close' })
      if (pathCrossesWith(s.points, p)) return { ...s, message: 'That point would make the outline cross itself.' }
      return commit(s, [...s.points, p], { cursor: p })
    }
    case 'close': {
      if (s.mode !== 'drawing') return s
      const errs = polygonErrors(s.points)
      if (errs.length) return { ...s, message: errs[0] }
      return { ...s, mode: 'editing', selected: null, message: null }
    }
    case 'cancel':
      if (s.mode === 'drawing') return { ...initial, cursor: s.cursor }
      return { ...s, selected: null, message: null }
    case 'select':
      return { ...s, selected: a.index, message: null }
    case 'beginDrag':
      // One history entry per drag gesture, not per pointer move.
      return { ...s, past: [...s.past, s.points].slice(-HISTORY), future: [] }
    case 'drag': {
      const p = snap(a.p)
      const next = s.points.map((q, i) => (i === a.index ? p : q))
      return { ...s, points: next, selected: a.index, message: polygonErrors(next)[0] ?? null }
    }
    case 'move':
      return { ...s, points: shift(s.points, a.dx, a.dy) }
    case 'nudge': {
      if (s.mode === 'drawing') return { ...s, cursor: snap([s.cursor[0] + a.dx, s.cursor[1] + a.dy], 0) }
      if (s.mode !== 'editing') return s
      if (s.selected === null) return commit(s, shift(s.points, a.dx, a.dy), { selected: null })
      const [x, y] = s.points[s.selected]
      const next = s.points.map((q, i) => (i === s.selected ? snap([x + a.dx, y + a.dy], 0) : q))
      const err = polygonErrors(next)[0]
      return err ? { ...s, message: err } : commit(s, next, { selected: s.selected })
    }
    case 'insert': {
      if (s.mode !== 'editing') return s
      const next = [...s.points.slice(0, a.after + 1), snap(a.p), ...s.points.slice(a.after + 1)]
      return commit(s, next, { selected: a.after + 1 })
    }
    case 'delete': {
      if (s.mode === 'drawing') return s.points.length ? commit(s, s.points.slice(0, -1)) : s
      if (s.selected === null) return s
      if (s.points.length <= 3) return { ...s, message: 'A zone needs at least 3 points.' }
      const next = s.points.filter((_, i) => i !== s.selected)
      const err = polygonErrors(next)[0]
      return err ? { ...s, message: err } : commit(s, next, { selected: null })
    }
    case 'cursor':
      return { ...s, cursor: snap(a.p, 0) }
    case 'undo': {
      if (!s.past.length) return s
      const prev = s.past[s.past.length - 1]
      return {
        ...s,
        points: prev,
        past: s.past.slice(0, -1),
        future: [s.points, ...s.future],
        selected: null,
        message: null,
        mode: s.mode === 'editing' && prev.length < 3 ? 'drawing' : s.mode,
      }
    }
    case 'redo': {
      if (!s.future.length) return s
      const [next, ...rest] = s.future
      return { ...s, points: next, past: [...s.past, s.points], future: rest, selected: null, message: null }
    }
  }
}
