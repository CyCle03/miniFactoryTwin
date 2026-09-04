import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchMachineState, websocketUrl } from '../services/machineApi'
import type { ConnectionStatus, MachineState } from '../types/machine'

const initialState: MachineState = {
  timestamp: new Date(0).toISOString(),
  machine: { power: false, running: false, emergency: false },
  conveyor: { running: false, speed: 0 },
  sensors: { photo_1: false, photo_2: false },
  cylinder: { state: 'retracted' },
  production: { total: 0, good: 0, reject: 0, ppm: 0 },
  products: [],
}

export function useMachineState() {
  const [state, setState] = useState<MachineState>(initialState)
  const [connection, setConnection] = useState<ConnectionStatus>('connecting')
  const [error, setError] = useState<string | null>(null)
  const retryCount = useRef(0)
  const retryTimer = useRef<number | undefined>(undefined)
  const lastMessageAt = useRef(0)

  const clearError = useCallback(() => setError(null), [])

  useEffect(() => {
    let socket: WebSocket | null = null
    let disposed = false

    const connect = () => {
      if (disposed) return
      setConnection('connecting')
      socket = new WebSocket(websocketUrl())

      socket.onopen = () => {
        retryCount.current = 0
        lastMessageAt.current = Date.now()
        setConnection('connected')
        setError(null)
      }

      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          setState(JSON.parse(event.data) as MachineState)
          lastMessageAt.current = Date.now()
          setConnection('connected')
        } catch {
          setError('Received invalid machine data')
        }
      }

      socket.onerror = () => socket?.close()
      socket.onclose = () => {
        if (disposed) return
        setConnection('disconnected')
        const delay = Math.min(1000 * 2 ** retryCount.current, 10_000)
        retryCount.current += 1
        retryTimer.current = window.setTimeout(connect, delay)
      }
    }

    fetchMachineState().then(setState).catch(() => undefined)
    connect()
    const freshnessTimer = window.setInterval(() => {
      if (lastMessageAt.current > 0 && Date.now() - lastMessageAt.current > 3_000) {
        setConnection('disconnected')
      }
    }, 1_000)

    return () => {
      disposed = true
      window.clearInterval(freshnessTimer)
      if (retryTimer.current !== undefined) window.clearTimeout(retryTimer.current)
      socket?.close()
    }
  }, [])

  return { state, connection, error, setError, clearError }
}
