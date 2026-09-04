import { Octagon, Play, RotateCcw, ShieldCheck, Square } from 'lucide-react'
import type { MachineCommand, MachineState } from '../types/machine'

interface ControlsProps {
  state: MachineState
  busy: boolean
  connected: boolean
  onCommand: (command: MachineCommand) => void
}

export function Controls({ state, busy, connected, onCommand }: ControlsProps) {
  const unavailable = busy || !connected
  return (
    <section className="panel controls-panel">
      <div className="control-copy">
        <span className="eyebrow">OPERATOR CONTROLS</span>
        <h2>Manual Command</h2>
        <p>Commands are published to the machine controller through the backend.</p>
      </div>
      <div className="control-buttons">
        <button className="command start" disabled={unavailable || state.machine.emergency || state.machine.running} onClick={() => onCommand('start')}><Play size={18} fill="currentColor" /> Start</button>
        <button className="command stop" disabled={unavailable || !state.machine.running} onClick={() => onCommand('stop')}><Square size={16} fill="currentColor" /> Stop</button>
        <button className="command reset" disabled={unavailable || state.machine.running} onClick={() => onCommand('reset')}><RotateCcw size={18} /> Reset</button>
        {state.machine.emergency ? (
          <button className="command acknowledge" disabled={unavailable} onClick={() => onCommand('emergency_reset')}><ShieldCheck size={18} /> Reset E-stop</button>
        ) : (
          <button className="command estop" disabled={unavailable} onClick={() => onCommand('emergency_stop')}><Octagon size={19} fill="currentColor" /> Emergency</button>
        )}
      </div>
    </section>
  )
}
