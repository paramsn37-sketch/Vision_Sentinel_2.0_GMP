import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, type Camera, type CameraIn, type Incident, type IncidentPage, type Thresholds, type Upload, type Zone, type ZoneIn } from './client'
import type { ActiveModel, Health, IncidentsByHour, Summary, Timeseries, ZoneStat } from './types'

export const keys = {
  me: ['me'] as const,
  cameras: ['cameras'] as const,
  zones: (cameraId?: string) => ['zones', cameraId ?? 'all'] as const,
  incidents: (f: IncidentFilters) => ['incidents', f] as const,
  incident: (id: string) => ['incident', id] as const,
  summary: (range?: Range) => ['summary', range ?? {}] as const,
  timeseries: (range: Range & { bucket: string; camera_id?: string }) => ['timeseries', range] as const,
  byHour: (range?: Range) => ['by-hour', range ?? {}] as const,
  zoneStats: (range?: Range) => ['zone-stats', range ?? {}] as const,
  health: ['health'] as const,
  model: ['model'] as const,
  runs: ['runs'] as const,
  evaluations: ['evaluations'] as const,
  dataset: ['dataset'] as const,
  figures: ['figures'] as const,
  uploads: ['uploads'] as const,
  upload: (id: string) => ['upload', id] as const,
  thresholds: ['thresholds'] as const,
  audit: ['audit'] as const,
}

export interface Range {
  since?: string
  until?: string
}
export interface IncidentFilters {
  status?: string
  rule?: string
  camera_id?: string
  zone_id?: string
  severity?: string
  q?: string
  since?: string
  limit?: number
  cursor?: string
}

const errorToast = (title: string) => (e: Error) => toast.error(title, { description: e.message })

export const useMe = () =>
  useQuery({ queryKey: keys.me, queryFn: () => api.get<{ user: string; csrf_token: string }>('/auth/me'), retry: false })

export const useCameras = () =>
  useQuery({ queryKey: keys.cameras, queryFn: () => api.get<Camera[]>('/cameras'), refetchInterval: 5000 })

export const useZones = (cameraId?: string) =>
  useQuery({
    queryKey: keys.zones(cameraId),
    queryFn: () => api.get<Zone[]>('/zones', { camera_id: cameraId }),
  })

export const useIncidents = (f: IncidentFilters) =>
  useQuery({
    queryKey: keys.incidents(f),
    queryFn: ({ signal }) => api.get<IncidentPage>('/incidents', { ...f }, signal),
    placeholderData: keepPreviousData,
    refetchInterval: 15000,
  })

export const useIncident = (id: string | null) =>
  useQuery({
    queryKey: keys.incident(id ?? ''),
    queryFn: () => api.get<Incident>(`/incidents/${id}`),
    enabled: !!id,
  })

export const useSummary = (range?: Range) =>
  useQuery({ queryKey: keys.summary(range), queryFn: () => api.get<Summary>('/analytics/summary', { ...range }), refetchInterval: 5000 })

export const useTimeseries = (range: Range & { bucket: 'hour' | 'minute'; camera_id?: string }) =>
  useQuery({
    queryKey: keys.timeseries(range),
    queryFn: () => api.get<Timeseries>('/analytics/timeseries', { ...range }),
    refetchInterval: range.bucket === 'minute' ? 30000 : 60000,
    placeholderData: keepPreviousData,
  })

export const useIncidentsByHour = (range?: Range) =>
  useQuery({ queryKey: keys.byHour(range), queryFn: () => api.get<IncidentsByHour>('/analytics/incidents-by-hour', { ...range }) })

export const useZoneStats = (range?: Range) =>
  useQuery({ queryKey: keys.zoneStats(range), queryFn: () => api.get<ZoneStat[]>('/analytics/zones', { ...range }) })

export const useHealth = () =>
  useQuery({ queryKey: keys.health, queryFn: () => api.get<Health>('/health'), refetchInterval: 10000 })

export const useActiveModel = () => useQuery({ queryKey: keys.model, queryFn: () => api.get<ActiveModel>('/model/active') })

export const useRuns = () =>
  useQuery({ queryKey: keys.runs, queryFn: () => api.get<{ runs: Record<string, unknown>[] }>('/model/runs') })

export const useEvaluations = () =>
  useQuery({
    queryKey: keys.evaluations,
    queryFn: () =>
      api.get<{ counting: CountingResults | null; xai: XaiResults | null; detector: DetectorResults | null; latency: LatencyResults | null }>(
        '/model/evaluations',
      ),
  })

export const useDataset = () =>
  useQuery({ queryKey: keys.dataset, queryFn: () => api.get<{ card: string | null; split: unknown }>('/model/dataset') })

export const useFigures = () =>
  useQuery({ queryKey: keys.figures, queryFn: () => api.get<Record<string, string[]>>('/model/figures') })

export const useUploads = () =>
  useQuery({ queryKey: keys.uploads, queryFn: () => api.get<Upload[]>('/uploads'), refetchInterval: 4000 })

export const useThresholds = () => useQuery({ queryKey: keys.thresholds, queryFn: () => api.get<Thresholds>('/settings/thresholds') })

export const useAudit = () =>
  useQuery({ queryKey: keys.audit, queryFn: () => api.get<Record<string, unknown>[]>('/audit', { limit: 50 }) })

/** Acknowledge / resolve / note. Optimistic on every cached incident list, rolled back on error. */
export function usePatchIncident() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; status?: string; note?: string; feedback?: string }) =>
      api.patch<Incident>(`/incidents/${id}`, body),
    onMutate: async ({ id, status }) => {
      if (!status) return {}
      await qc.cancelQueries({ queryKey: ['incidents'] })
      const prev = qc.getQueriesData<IncidentPage>({ queryKey: ['incidents'] })
      qc.setQueriesData<IncidentPage>({ queryKey: ['incidents'] }, (p) =>
        p ? { ...p, items: p.items.map((i) => (i.id === id ? { ...i, status } : i)) } : p,
      )
      qc.setQueryData<Incident>(keys.incident(id), (i) => (i ? { ...i, status } : i))
      return { prev }
    },
    onError: (e: Error, _v, ctx) => {
      ctx?.prev?.forEach(([k, v]) => qc.setQueryData(k, v))
      errorToast('Could not update the incident')(e)
    },
    onSettled: (_d, _e, v) => {
      qc.invalidateQueries({ queryKey: ['incidents'] })
      qc.invalidateQueries({ queryKey: keys.incident(v.id) })
      qc.invalidateQueries({ queryKey: ['summary'] })
    },
  })
}

export function useSaveCamera() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<CameraIn> & { id?: string }) =>
      id ? api.patch<Camera>(`/cameras/${id}`, body) : api.post<Camera>('/cameras', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.cameras }),
    onError: errorToast('Could not save the camera'),
  })
}

export function useCameraAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'start' | 'stop' | 'delete' }) =>
      action === 'delete' ? api.del(`/cameras/${id}`) : api.post(`/cameras/${id}/${action}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.cameras }),
    onError: errorToast('Camera action failed'),
  })
}

export function useSaveZone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: ZoneIn & { id?: string }) =>
      id ? api.put<Zone>(`/zones/${id}`, body) : api.post<Zone>('/zones', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['zones'] }),
  })
}

export function useDeleteZone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.del(`/zones/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['zones'] }),
    onError: errorToast('Could not delete the zone'),
  })
}

export function useSaveThresholds() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (t: Thresholds) => api.put<Thresholds>('/settings/thresholds', t),
    onSuccess: (t) => {
      qc.setQueryData(keys.thresholds, t)
      toast.success('Thresholds saved', { description: 'Running cameras use the new values from the next frame.' })
    },
    onError: errorToast('Could not save thresholds'),
  })
}

// Evaluation result shapes (docs/eval/*.json); only the fields the UI reads.
export interface CountingResults {
  detector: string
  imgsz: number
  tuned_config: Record<string, number>
  trials: number
  report: {
    seq: string
    naive_1fps: { gt_unique: number; pred_unique: number; count_error: number }
    bytetrack_default: CountRow
    bytetrack_tuned: CountRow
    ours: CountRow
  }[]
}
export interface CountRow {
  gt_unique: number
  pred_unique: number
  count_error: number
  idf1: number
  mota: number
  id_switches: number
}
export type XaiResults = Record<string, unknown>
export type DetectorResults = Record<string, unknown>
export type LatencyResults = Record<string, unknown>
