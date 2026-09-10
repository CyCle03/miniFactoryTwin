import type { ProductResult } from './machine'

export type EventSeverity = 'INFO' | 'WARNING' | 'CRITICAL' | 'ERROR'

export interface ProductionRecord {
  id: number
  product_id: number
  result: ProductResult
  started_at: string
  inspected_at: string
  completed_at: string
  cycle_time_seconds: number
  inspection_confidence: number | null
  inspection_latency_ms: number | null
  inspection_model: string | null
  inspection_defect: string | null
  inspection_image_name: string | null
  created_at: string
}

export interface EventRecord {
  id: number
  timestamp: string
  event_type: string
  severity: EventSeverity
  message: string
  product_id: number | null
  metadata: Record<string, string | number | boolean | null>
}

export interface AnalyticsSummary {
  total: number
  good: number
  reject: number
  recent_cycle_time: number | null
  average_cycle_time: number | null
  min_cycle_time: number | null
  max_cycle_time: number | null
}

export interface ProductionBucket {
  bucket: string
  total: number
  good: number
  reject: number
  average_cycle_time: number | null
}
