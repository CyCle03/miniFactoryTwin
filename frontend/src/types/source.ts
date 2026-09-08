export interface SourceStatus {
  source: string
  connected: boolean
  stale: boolean
  error: string | null
}
