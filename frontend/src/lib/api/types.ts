// Shapes of endpoints that return free-form JSON (dicts) on the backend. Kept in one place and mirrored from
// backend/app/api/{analytics,model,system}.py and backend/app/services/serialize.py.

export type AlertLevel = 'green' | 'amber' | 'red'
export type PPEState = 'present' | 'absent' | 'unknown'

export interface Summary {
  since: string
  until: string
  cameras_online: number
  cameras_total: number
  people_now: number
  unique_people: number
  incidents: number
  incidents_by_rule: Record<string, number>
  open_incidents: number
  open_high: number
  compliance_rate: number | null
  alert_level: AlertLevel
}

export interface TimePoint {
  t: string
  new_people: number
  peak_people: number
  incidents: number
  compliant: number
  noncompliant: number
}
export interface Timeseries {
  bucket: 'hour' | 'minute'
  points: TimePoint[]
}
export interface IncidentsByHour {
  since: string
  until: string
  rows: { rule: string; hours: number[] }[]
}
export interface ZoneStat {
  zone_id: string
  zone_name: string
  camera_id: string
  kind: string
  severity: string
  entries: number
  incidents: number
  peak_occupancy: number
}

export interface Health {
  status: 'ok' | 'degraded'
  model: string | null
  model_error: string | null
  uptime_s: number
  cameras: Record<string, { status: string; fps: number; people_now: number; error: string | null }>
}

export interface ActiveModel {
  loaded: boolean
  error?: string
  name?: string
  is_ppe_model?: boolean
  classes?: string[]
  imgsz?: number
  device?: string
  thresholds?: Record<string, number>
  meta?: Record<string, unknown>
}

export interface Box {
  cls: string
  conf: number
  box: [number, number, number, number]
}
export interface LivePerson {
  track_id: number
  box: [number, number, number, number]
  conf: number
  confirmed: boolean
  since_s: number
  ppe: Record<string, PPEState>
  items: Box[]
  zones: string[]
  violations: string[]
}
export interface LiveZone {
  id: string
  name: string
  kind: 'restricted' | 'ppe_required' | 'hazard'
  severity: string
  polygon: [number, number][]
}
export interface FrameMeta {
  type: 'frame'
  camera_id: string
  frame_idx: number
  ts: number
  width: number
  height: number
  fps: number
  latency_ms: number
  counts: { current: number; unique_total: number; per_zone: Record<string, { current: number; unique: number }> }
  persons: LivePerson[]
  objects: Box[]
  zones: LiveZone[]
  alert_level: AlertLevel
}
export interface StatusMsg {
  type: 'status'
  status: string
  error?: string | null
}

export interface IncidentEvent {
  type: 'incident'
  kind: 'opened' | 'closed' | 'reopened' | 'evidence' | 'status'
  incident: {
    id: string
    camera_id: string
    track_id: number | null
    rule: string
    zone_id: string | null
    zone_name: string | null
    severity: string
    status: string
    active: boolean
    started_at: string
    ended_at: string | null
    duration_s: number
  }
}
export type BusEvent =
  | IncidentEvent
  | { type: 'zone_event'; camera_id: string; zone_id: string; track_id: number; kind: string }
  | { type: 'upload'; id: string; status: string; progress: number }
  | { type: 'ping' }
  | { type: string; [k: string]: unknown }
