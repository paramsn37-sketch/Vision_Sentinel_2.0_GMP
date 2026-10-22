import type { LivePerson } from '@/lib/api/types'
import { fitContain, hitPerson, personTone, toFrame, toView } from './overlay'

const person = (id: number, box: [number, number, number, number], extra: Partial<LivePerson> = {}): LivePerson => ({
  track_id: id,
  box,
  conf: 0.9,
  confirmed: true,
  since_s: 3,
  ppe: {},
  items: [],
  zones: [],
  violations: [],
  ...extra,
})

describe('fitContain', () => {
  it('letterboxes a wide frame into a tall tile', () => {
    const f = fitContain(1920, 1080, 960, 960)
    expect(f.scale).toBeCloseTo(0.5)
    expect(f.ox).toBe(0)
    expect(f.oy).toBeCloseTo((960 - 540) / 2)
  })
  it('round-trips view and frame coordinates', () => {
    const f = fitContain(1280, 720, 800, 600)
    const [vx, vy] = toView(f, 640, 360)
    const [x, y] = toFrame(f, vx, vy)
    expect(x).toBeCloseTo(640)
    expect(y).toBeCloseTo(360)
  })
  it('handles an empty tile', () => {
    expect(fitContain(1280, 720, 0, 0).w).toBe(0)
  })
})

describe('hitPerson', () => {
  const f = fitContain(1000, 1000, 500, 500)
  it('picks the smallest box under the pointer', () => {
    const big = person(1, [0, 0, 600, 600])
    const small = person(2, [100, 100, 200, 300])
    expect(hitPerson(f, [big, small], 75, 100)?.track_id).toBe(2)
  })
  it('returns null outside every box', () => {
    expect(hitPerson(f, [person(1, [0, 0, 100, 100])], 400, 400)).toBeNull()
  })
})

describe('personTone', () => {
  it('is a violation when an incident is open on the person', () => {
    expect(personTone(person(1, [0, 0, 1, 1], { violations: ['intrusion'] }))).toBe('violation')
  })
  it('is ok only when every known item is present', () => {
    expect(personTone(person(1, [0, 0, 1, 1], { ppe: { helmet: 'present', vest: 'present' } }))).toBe('ok')
    expect(personTone(person(1, [0, 0, 1, 1], { ppe: { helmet: 'present', vest: 'unknown' } }))).toBe('neutral')
  })
})
