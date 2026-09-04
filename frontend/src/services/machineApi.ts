import type { MachineCommand, MachineState } from '../types/machine'

const configuredUrl = import.meta.env.VITE_API_URL?.trim()
const developmentUrl = `${window.location.protocol}//${window.location.hostname}:8000`
export const API_BASE = configuredUrl || (window.location.port === '5173' ? developmentUrl : window.location.origin)

export const websocketUrl = (): string => {
  const base = new URL(API_BASE)
  base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
  base.pathname = '/ws/machine'
  return base.toString()
}

export async function fetchMachineState(): Promise<MachineState> {
  const response = await fetch(`${API_BASE}/api/state`)
  if (!response.ok) {
    throw new Error(`State request failed (${response.status})`)
  }
  return response.json() as Promise<MachineState>
}

export async function sendMachineCommand(command: MachineCommand): Promise<void> {
  const response = await fetch(`${API_BASE}/api/commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command }),
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Command failed (${response.status})`)
  }
}


async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) throw new Error(`History request failed (${response.status})`)
  return response.json() as Promise<T>
}

export async function fetchHistoryDashboard() {
  const [production, events, summary, buckets] = await Promise.all([
    fetchJson<import('../types/history').ProductionRecord[]>('/api/history/production?limit=12'),
    fetchJson<import('../types/history').EventRecord[]>('/api/history/events?limit=12'),
    fetchJson<import('../types/history').AnalyticsSummary>('/api/analytics/summary'),
    fetchJson<import('../types/history').ProductionBucket[]>('/api/analytics/production?limit=12'),
  ])
  return { production, events, summary, buckets }
}

export async function fetchSourceStatus(): Promise<import('../types/source').SourceStatus> {
  return fetchJson<import('../types/source').SourceStatus>('/api/source')
}
