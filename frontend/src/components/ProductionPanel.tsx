import { Check, PackageCheck, Timer, X } from 'lucide-react'
import type { MachineState } from '../types/machine'

interface ProductionPanelProps {
  production: MachineState['production']
}

export function ProductionPanel({ production }: ProductionPanelProps) {
  const yieldRate = production.total === 0 ? 100 : (production.good / production.total) * 100

  return (
    <section className="panel production-panel">
      <div className="section-heading compact">
        <div><span className="eyebrow">SHIFT METRICS</span><h2>Production</h2></div>
        <div className="yield-chip">YIELD {yieldRate.toFixed(1)}%</div>
      </div>
      <div className="metric-grid">
        <article className="metric total"><PackageCheck size={19} /><span>Total</span><strong>{production.total.toLocaleString()}</strong></article>
        <article className="metric good"><Check size={19} /><span>Good</span><strong>{production.good.toLocaleString()}</strong></article>
        <article className="metric reject"><X size={19} /><span>Reject</span><strong>{production.reject.toLocaleString()}</strong></article>
        <article className="metric ppm"><Timer size={19} /><span>PPM</span><strong>{production.ppm}</strong></article>
      </div>
    </section>
  )
}

