import { useEffect, useState } from 'react'
import { fetchSourceStatus } from '../services/machineApi'
import type { SourceStatus } from '../types/source'

const initial: SourceStatus = { source: 'unknown', connected: false, stale: true, error: null }

export function useSourceStatus() {
  const [status, setStatus] = useState(initial)
  useEffect(() => {
    let active = true
    const update = async () => {
      try {
        const value = await fetchSourceStatus()
        if (active) setStatus(value)
      } catch {
        if (active) setStatus((value) => ({ ...value, connected: false, stale: true, error: 'Status unavailable' }))
      }
    }
    void update()
    const timer = window.setInterval(() => void update(), 1000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  return status
}
