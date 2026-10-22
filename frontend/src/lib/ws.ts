// WebSocket clients with reconnect + backoff. One events socket for the app; one live socket per video tile.
import type { BusEvent, FrameMeta, StatusMsg } from './api/types'

const wsUrl = (path: string) => `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${path}`

interface Options<T> {
  path: string
  onMessage: (m: T) => void
  onBinary?: (b: Blob) => void
  onState?: (s: 'connecting' | 'open' | 'closed' | 'unauthorized') => void
}

export function connect<T>({ path, onMessage, onBinary, onState }: Options<T>) {
  let ws: WebSocket | null = null
  let tries = 0
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | undefined

  const open = () => {
    if (stopped) return
    onState?.('connecting')
    ws = new WebSocket(wsUrl(path))
    ws.binaryType = 'blob'
    ws.onopen = () => {
      tries = 0
      onState?.('open')
    }
    ws.onmessage = (e) => {
      if (typeof e.data === 'string') onMessage(JSON.parse(e.data) as T)
      else onBinary?.(e.data as Blob)
    }
    ws.onclose = (e) => {
      if (stopped) return
      if (e.code === 4401) {
        onState?.('unauthorized')
        return
      }
      onState?.('closed')
      const delay = Math.min(10000, 500 * 2 ** tries++) * (0.8 + Math.random() * 0.4)
      timer = setTimeout(open, delay)
    }
  }
  open()
  return {
    send: (m: unknown) => ws?.readyState === WebSocket.OPEN && ws.send(JSON.stringify(m)),
    close: () => {
      stopped = true
      clearTimeout(timer)
      ws?.close()
    },
  }
}

export const connectEvents = (onEvent: (e: BusEvent) => void, onState?: Options<BusEvent>['onState']) =>
  connect<BusEvent>({ path: '/ws/events', onMessage: onEvent, onState })

/** Live stream: a JSON `frame` message is followed by the JPEG of the same frame. */
export function connectLive(
  cameraId: string,
  fps: number,
  onFrame: (meta: FrameMeta, jpeg: Blob) => void,
  onStatus: (s: StatusMsg) => void,
  onState?: Options<unknown>['onState'],
) {
  let pending: FrameMeta | null = null
  return connect<FrameMeta | StatusMsg>({
    path: `/ws/live?camera_id=${encodeURIComponent(cameraId)}&fps=${fps}`,
    onMessage: (m) => {
      if (m.type === 'frame') pending = m
      else onStatus(m)
    },
    onBinary: (b) => {
      if (pending) onFrame(pending, b)
      pending = null
    },
    onState,
  })
}
