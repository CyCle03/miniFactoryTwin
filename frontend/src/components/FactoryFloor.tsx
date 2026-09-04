import { AlertTriangle, ArrowRight } from 'lucide-react'
import type { MachineState } from '../types/machine'

interface FactoryFloorProps {
  state: MachineState
}

function Sensor({ label, active, position }: { label: string; active: boolean; position: number }) {
  return (
    <div className={`sensor-unit ${active ? 'active' : ''}`} style={{ left: `${position}%` }}>
      <div className="sensor-label">{label}</div>
      <div className="sensor-head"><span /></div>
      <div className="sensor-beam" />
    </div>
  )
}

export function FactoryFloor({ state }: FactoryFloorProps) {
  const { machine, conveyor, sensors, cylinder, products } = state

  return (
    <section className={`factory-floor panel ${machine.emergency ? 'emergency' : ''}`}>
      <div className="section-heading">
        <div>
          <span className="eyebrow">LIVE PROCESS</span>
          <h2>Conveyor Cell</h2>
        </div>
        <div className={`run-state ${machine.running ? 'running' : ''}`}>
          <span />{machine.emergency ? 'EMERGENCY STOP' : machine.running ? 'AUTO RUN' : 'IDLE'}
        </div>
      </div>

      {machine.emergency && (
        <div className="emergency-banner"><AlertTriangle size={18} /> Safety circuit active — motion inhibited</div>
      )}

      <div className="cell-stage">
        <div className="station-tag entry">INFEED</div>
        <div className="station-tag exit">OUTFEED</div>
        <Sensor label="PS-01" active={sensors.photo_1} position={20} />
        <Sensor label="PS-02" active={sensors.photo_2} position={70} />

        <div className={`cylinder ${cylinder.state}`}>
          <div className="cylinder-label">CY-01 · {cylinder.state.toUpperCase()}</div>
          <div className="cylinder-body"><div className="cylinder-rod" /></div>
          <div className="reject-bin">REJECT</div>
        </div>

        <div className={`conveyor ${conveyor.running ? 'moving' : ''}`}>
          <div className="conveyor-belt">
            <div className="belt-markers">
              {Array.from({ length: 14 }, (_, index) => <span key={index} />)}
            </div>
            {products.map((product) => (
              <div
                className={`product ${product.result.toLowerCase()}`}
                key={product.id}
                style={{ left: `${Math.min(98, Math.max(1, product.position))}%` }}
                title={`Product #${product.id} · ${product.result}`}
              >
                <span>#{product.id}</span>
              </div>
            ))}
          </div>
          <div className="conveyor-frame">
            {Array.from({ length: 12 }, (_, index) => <span key={index} />)}
          </div>
        </div>

        <div className="flow-label">
          <ArrowRight size={15} /> FLOW DIRECTION
        </div>
      </div>
    </section>
  )
}

