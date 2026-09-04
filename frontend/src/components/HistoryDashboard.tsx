import { useCallback, useEffect, useState } from 'react'
import { fetchHistoryDashboard } from '../services/machineApi'
import type { AnalyticsSummary, EventRecord, ProductionBucket, ProductionRecord } from '../types/history'

const EMPTY: AnalyticsSummary = { total: 0, good: 0, reject: 0, recent_cycle_time: null, average_cycle_time: null, min_cycle_time: null, max_cycle_time: null }
const seconds = (value: number | null) => value === null ? '—' : `${value.toFixed(2)} s`
const time = (value: string) => new Date(value).toLocaleString()

export function HistoryDashboard() {
  const [production, setProduction] = useState<ProductionRecord[]>([])
  const [events, setEvents] = useState<EventRecord[]>([])
  const [summary, setSummary] = useState(EMPTY)
  const [buckets, setBuckets] = useState<ProductionBucket[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await fetchHistoryDashboard()
      setProduction(data.production); setEvents(data.events); setSummary(data.summary); setBuckets(data.buckets); setError(null)
    } catch { setError('History temporarily unavailable') }
  }, [])

  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 5000); return () => window.clearInterval(timer) }, [refresh])
  const max = Math.max(1, ...buckets.map((bucket) => bucket.total))

  return <section className="history-dashboard" aria-label="Production analytics">
    {error && <p className="history-error" role="status">{error}. Live controls remain available.</p>}
    <div className="cycle-grid panel">
      <header className="section-heading compact"><div><span className="eyebrow">CYCLE TIME</span><h2>Performance Summary</h2></div></header>
      <div className="cycle-metrics">
        <div><span>RECENT</span><strong>{seconds(summary.recent_cycle_time)}</strong></div>
        <div><span>AVERAGE</span><strong>{seconds(summary.average_cycle_time)}</strong></div>
        <div><span>MINIMUM</span><strong>{seconds(summary.min_cycle_time)}</strong></div>
        <div><span>MAXIMUM</span><strong>{seconds(summary.max_cycle_time)}</strong></div>
      </div>
    </div>
    <div className="panel chart-panel">
      <header className="section-heading compact"><div><span className="eyebrow">PRODUCTION CHART</span><h2>Hourly Output</h2></div></header>
      {buckets.length === 0 ? <p className="empty-state">No completed products yet.</p> :
        <div className="bar-chart" role="img" aria-label="Hourly good and reject production">
          {buckets.map((bucket) => <div className="bar-column" key={bucket.bucket} title={`${time(bucket.bucket)}: ${bucket.good} good, ${bucket.reject} reject`}>
            <div className="bars"><i className="bar good-bar" style={{height: `${bucket.good / max * 100}%`}} /><i className="bar reject-bar" style={{height: `${bucket.reject / max * 100}%`}} /></div>
            <span>{new Date(bucket.bucket).getHours().toString().padStart(2, '0')}</span>
          </div>)}
        </div>}
      <div className="chart-legend"><span>■ GOOD</span><span>■ REJECT</span></div>
    </div>
    <HistoryTable production={production} />
    <EventTable events={events} />
  </section>
}

function HistoryTable({ production }: { production: ProductionRecord[] }) {
  return <section className="panel table-panel"><header className="section-heading compact"><div><span className="eyebrow">TRACEABILITY</span><h2>Production History</h2></div></header>
    <div className="table-scroll"><table><thead><tr><th>Product</th><th>Result</th><th>Completed</th><th>Cycle</th></tr></thead>
      <tbody>{production.length === 0 ? <tr><td colSpan={4} className="empty-state">No production history.</td></tr> : production.map((row) =>
        <tr key={row.id}><td>#{row.product_id}</td><td><span className={`status-label ${row.result.toLowerCase()}`}>{row.result === 'GOOD' ? '✓ GOOD' : '✕ REJECT'}</span></td><td>{time(row.completed_at)}</td><td>{seconds(row.cycle_time_seconds)}</td></tr>)}</tbody>
    </table></div></section>
}

function EventTable({ events }: { events: EventRecord[] }) {
  return <section className="panel table-panel"><header className="section-heading compact"><div><span className="eyebrow">ALARM / EVENT</span><h2>Event History</h2></div></header>
    <div className="table-scroll"><table><thead><tr><th>Severity</th><th>Message</th><th>Product</th><th>Time</th></tr></thead>
      <tbody>{events.length === 0 ? <tr><td colSpan={4} className="empty-state">No events recorded.</td></tr> : events.map((row) =>
        <tr key={row.id}><td><span className={`status-label ${row.severity.toLowerCase()}`}>{row.severity}</span></td><td>{row.message}</td><td>{row.product_id ? `#${row.product_id}` : '—'}</td><td>{time(row.timestamp)}</td></tr>)}</tbody>
    </table></div></section>
}
