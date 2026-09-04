import { CircleGauge, Power, ShieldAlert, ToggleLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import type { MachineState } from '../types/machine'

interface StatusPanelProps {
  state: MachineState
}

function StatusRow({ icon, label, value, tone }: { icon: ReactNode; label: string; value: string; tone: string }) {
  return (
    <div className="status-row">
      <span className="status-icon">{icon}</span>
      <span>{label}</span>
      <strong className={tone}><i />{value}</strong>
    </div>
  )
}

export function StatusPanel({ state }: StatusPanelProps) {
  return (
    <section className="panel info-panel">
      <div className="section-heading compact">
        <div><span className="eyebrow">EQUIPMENT</span><h2>Machine Status</h2></div>
      </div>
      <div className="status-list">
        <StatusRow icon={<Power size={17} />} label="Main power" value={state.machine.power ? 'ON' : 'OFF'} tone={state.machine.power ? 'ok' : 'muted'} />
        <StatusRow icon={<CircleGauge size={17} />} label="Conveyor" value={state.conveyor.running ? 'RUN' : 'STOP'} tone={state.conveyor.running ? 'ok' : 'muted'} />
        <StatusRow icon={<ShieldAlert size={17} />} label="Emergency" value={state.machine.emergency ? 'ACTIVE' : 'CLEAR'} tone={state.machine.emergency ? 'danger' : 'ok'} />
        <StatusRow icon={<ToggleLeft size={17} />} label="Cylinder" value={state.cylinder.state.toUpperCase()} tone={state.cylinder.state === 'extended' ? 'warn' : 'muted'} />
      </div>
      <div className="speed-readout">
        <span>LINE SPEED</span>
        <strong>{state.conveyor.speed.toFixed(2)}</strong>
        <small>m/s nominal</small>
      </div>
    </section>
  )
}
