import type { components } from './schema'

export type Schemas = components['schemas']
export type Camera = Schemas['CameraOut']
export type CameraIn = Schemas['CameraIn']
export type Zone = Schemas['ZoneOut']
export type ZoneIn = Schemas['ZoneIn']
export type ZoneRules = Schemas['ZoneRulesIO']
export type Incident = Schemas['IncidentOut']
export type IncidentPage = Schemas['IncidentPage']
export type Upload = Schemas['UploadOut']
export type XaiJob = Schemas['XaiOut']
export type Thresholds = Schemas['ThresholdsIO']

export const API = '/api/v1'

export class ApiError extends Error {
  status: number
  code: string
  details?: unknown
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

let onUnauthorized: (() => void) | null = null
export const setUnauthorizedHandler = (fn: () => void) => {
  onUnauthorized = fn
}

export function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)vs_csrf=([^;]+)/)
  return m ? decodeURIComponent(m[1]) : ''
}

type Query = Record<string, string | number | boolean | null | undefined>

export function qs(q?: Query): string {
  if (!q) return ''
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== null && v !== '') p.set(k, String(v))
  const s = p.toString()
  return s ? `?${s}` : ''
}

export async function request<T>(
  method: string,
  path: string,
  opts: { query?: Query; body?: unknown; form?: FormData; text?: string; raw?: boolean; signal?: AbortSignal } = {},
): Promise<T> {
  const headers: Record<string, string> = {}
  if (method !== 'GET') headers['x-csrf-token'] = csrfToken()
  let body: BodyInit | undefined
  if (opts.form) body = opts.form
  else if (opts.text !== undefined) {
    headers['content-type'] = 'application/yaml'
    body = opts.text
  } else if (opts.body !== undefined) {
    headers['content-type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  const res = await fetch(`${API}${path}${qs(opts.query)}`, {
    method,
    headers,
    body,
    credentials: 'same-origin',
    signal: opts.signal,
  })
  if (!res.ok) {
    let code = 'http_error'
    let message = `${res.status} ${res.statusText}`
    let details: unknown
    try {
      const j = await res.json()
      if (j?.error) ({ code, message, details } = j.error)
    } catch {
      /* not JSON */
    }
    if (res.status === 401 && !path.startsWith('/auth/login')) onUnauthorized?.()
    throw new ApiError(res.status, code, message, details)
  }
  if (opts.raw) return res as unknown as T
  if (res.status === 204) return undefined as T
  const type = res.headers.get('content-type') ?? ''
  return (type.includes('json') ? res.json() : res.text()) as Promise<T>
}

export const api = {
  get: <T>(path: string, query?: Query, signal?: AbortSignal) => request<T>('GET', path, { query, signal }),
  post: <T>(path: string, body?: unknown, query?: Query) => request<T>('POST', path, { body, query }),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, { body }),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, { body }),
  del: <T>(path: string) => request<T>('DELETE', path),
  upload: <T>(path: string, form: FormData) => request<T>('POST', path, { form }),
  postText: <T>(path: string, text: string, query?: Query) => request<T>('POST', path, { text, query }),
}

/** URL for an authenticated image/file endpoint (cookies are sent by the browser). */
export const url = (path: string, query?: Query) => `${API}${path}${qs(query)}`
