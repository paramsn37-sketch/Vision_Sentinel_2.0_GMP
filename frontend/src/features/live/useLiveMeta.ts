import { useEffect } from 'react'
import { connectLive } from '@/lib/ws'
import { useLive } from '@/stores/live'

/** Keep the latest metadata of one camera in the live store at a low rate (no video decoding). */
export function useLiveMeta(cameraId: string | undefined, fps = 2) {
  const setFrame = useLive((s) => s.setFrame)
  useEffect(() => {
    if (!cameraId) return
    const conn = connectLive(cameraId, fps, (m) => setFrame(m), () => undefined)
    return () => conn.close()
  }, [cameraId, fps, setFrame])
  return useLive((s) => (cameraId ? s.frames[cameraId] : undefined))
}
