import { initial, reducer, type Action, type EditorState } from './reducer'
import { isSimple, pointInPolygon, polygonErrors, snap, type Pt } from './geometry'

const run = (actions: Action[], s: EditorState = initial) => actions.reduce(reducer, s)
const square: Pt[] = [
  [0.2, 0.2],
  [0.6, 0.2],
  [0.6, 0.6],
  [0.2, 0.6],
]

describe('drawing', () => {
  it('adds points and closes with Enter (close action)', () => {
    const s = run([{ type: 'start' }, ...square.map((p) => ({ type: 'add', p }) as Action), { type: 'close' }])
    expect(s.mode).toBe('editing')
    expect(s.points).toEqual(square)
  })
  it('closes when the first point is clicked again', () => {
    const s = run([{ type: 'start' }, ...square.map((p) => ({ type: 'add', p }) as Action), { type: 'add', p: [0.201, 0.2] }])
    expect(s.mode).toBe('editing')
    expect(s.points).toHaveLength(4)
  })
  it('refuses to close with fewer than 3 points', () => {
    const s = run([{ type: 'start' }, { type: 'add', p: [0.1, 0.1] }, { type: 'add', p: [0.5, 0.1] }, { type: 'close' }])
    expect(s.mode).toBe('drawing')
    expect(s.message).toMatch(/at least 3/)
  })
  it('rejects a point whose edge would cross the outline', () => {
    const s = run([
      { type: 'start' },
      { type: 'add', p: [0.1, 0.1] },
      { type: 'add', p: [0.5, 0.1] },
      { type: 'add', p: [0.5, 0.5] },
      { type: 'add', p: [0.3, 0.0] },
    ])
    expect(s.points).toHaveLength(3)
    expect(s.message).toMatch(/cross/)
  })
  it('Esc cancels a drawing', () => {
    const s = run([{ type: 'start' }, { type: 'add', p: [0.1, 0.1] }, { type: 'cancel' }])
    expect(s.mode).toBe('idle')
    expect(s.points).toEqual([])
  })
  it('snaps to frame edges', () => {
    expect(snap([0.005, 0.995])).toEqual([0, 1])
    const s = run([{ type: 'start' }, { type: 'add', p: [-0.2, 0.004] }])
    expect(s.points[0]).toEqual([0, 0])
  })
  it('keyboard-only: the cursor moves with nudges and Space adds at the cursor', () => {
    let s = run([{ type: 'start' }, { type: 'cursor', p: [0.2, 0.2] }])
    s = run([{ type: 'add', p: s.cursor }, { type: 'nudge', dx: 0.3, dy: 0 }], s)
    expect(s.cursor[0]).toBeCloseTo(0.5)
  })
  it('Backspace while drawing removes the last point', () => {
    const s = run([{ type: 'start' }, { type: 'add', p: [0.1, 0.1] }, { type: 'add', p: [0.4, 0.1] }, { type: 'delete' }])
    expect(s.points).toEqual([[0.1, 0.1]])
  })
})

describe('editing', () => {
  const loaded = run([{ type: 'load', points: square }])
  it('drags a vertex with one undo step per gesture', () => {
    const s = run([{ type: 'beginDrag' }, { type: 'drag', index: 0, p: [0.15, 0.25] }, { type: 'drag', index: 0, p: [0.1, 0.3] }], loaded)
    expect(s.points[0]).toEqual([0.1, 0.3])
    const u = reducer(s, { type: 'undo' })
    expect(u.points).toEqual(square)
    expect(reducer(u, { type: 'redo' }).points[0]).toEqual([0.1, 0.3])
  })
  it('flags a self-intersecting drag inline', () => {
    const s = run([{ type: 'beginDrag' }, { type: 'drag', index: 0, p: [0.4, 0.8] }], loaded)
    expect(s.message).toMatch(/crosses itself/)
  })
  it('inserts a vertex on an edge and deletes it again', () => {
    const s = run([{ type: 'insert', after: 0, p: [0.4, 0.15] }], loaded)
    expect(s.points).toHaveLength(5)
    expect(s.selected).toBe(1)
    const d = reducer(s, { type: 'delete' })
    expect(d.points).toEqual(square)
  })
  it('never deletes below 3 points', () => {
    const tri = run([{ type: 'load', points: square.slice(0, 3) }, { type: 'select', index: 0 }, { type: 'delete' }])
    expect(tri.points).toHaveLength(3)
    expect(tri.message).toMatch(/at least 3/)
  })
  it('nudges the selected vertex, or the whole zone when none is selected', () => {
    const v = run([{ type: 'select', index: 2 }, { type: 'nudge', dx: 0.01, dy: 0 }], loaded)
    expect(v.points[2][0]).toBeCloseTo(0.61)
    const all = run([{ type: 'nudge', dx: 0.05, dy: 0 }], loaded)
    expect(all.points.map((p) => p[0])).toEqual([0.25, 0.65, 0.65, 0.25].map((x) => expect.closeTo(x)))
  })
  it('moves the polygon without leaving the frame', () => {
    const s = run([{ type: 'move', dx: 0.9, dy: 0 }], loaded)
    expect(Math.max(...s.points.map((p) => p[0]))).toBeCloseTo(1)
  })
  it('undo with an empty history does nothing', () => {
    expect(reducer(initial, { type: 'undo' })).toBe(initial)
  })
})

describe('geometry', () => {
  it('detects simple and self-crossing polygons', () => {
    expect(isSimple(square)).toBe(true)
    expect(isSimple([[0, 0], [1, 1], [1, 0], [0, 1]])).toBe(false)
  })
  it('point in polygon', () => {
    expect(pointInPolygon([0.4, 0.4], square)).toBe(true)
    expect(pointInPolygon([0.7, 0.4], square)).toBe(false)
  })
  it('explains every invalid polygon', () => {
    expect(polygonErrors([[0, 0], [0.01, 0], [0, 0.01]])[0]).toMatch(/too small/)
    expect(polygonErrors(square)).toEqual([])
  })
})
