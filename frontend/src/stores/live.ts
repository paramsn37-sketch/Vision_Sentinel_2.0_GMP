import { create } from 'zustand'
import type { FrameMeta, IncidentEvent } from '@/lib/api/types'

/** Live state shared by the shell and the Live screen: latest metadata per camera and the recent incident feed. */
interface LiveState {
  frames: Record<string, FrameMeta>
  feed: IncidentEvent[]
  eventsState: 'connecting' | 'open' | 'closed' | 'unauthorized'
  lastAlertAt: number
  setFrame: (m: FrameMeta) => void
  pushIncident: (e: IncidentEvent) => void
  setEventsState: (s: LiveState['eventsState']) => void
}

export const useLive = create<LiveState>((set) => ({
  frames: {},
  feed: [],
  eventsState: 'connecting',
  lastAlertAt: 0,
  setFrame: (m) => set((s) => ({ frames: { ...s.frames, [m.camera_id]: m } })),
  pushIncident: (e) =>
    set((s) => ({
      feed: [e, ...s.feed.filter((x) => !(x.incident.id === e.incident.id && x.kind === e.kind))].slice(0, 50),
      lastAlertAt: e.kind === 'opened' && e.incident.severity === 'high' ? Date.now() : s.lastAlertAt,
    })),
  setEventsState: (eventsState) => set({ eventsState }),
}))
