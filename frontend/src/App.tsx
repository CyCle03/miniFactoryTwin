import { useState } from 'react'
import { Controls } from './components/Controls'
import { FactoryFloor } from './components/FactoryFloor'
import { Header } from './components/Header'
import { HistoryDashboard } from './components/HistoryDashboard'
import { ProductionPanel } from './components/ProductionPanel'
import { StatusPanel } from './components/StatusPanel'
import { useMachineState } from './hooks/useMachineState'
import { useSourceStatus } from './hooks/useSourceStatus'
import { sendMachineCommand } from './services/machineApi'
import type { MachineCommand } from './types/machine'

function App() {
  const { state, connection, error, setError, clearError } = useMachineState()
  const source = useSourceStatus()
  const [busy, setBusy] = useState(false)

  const handleCommand = async (command: MachineCommand) => {
    setBusy(true)
    clearError()
    try {
      await sendMachineCommand(command)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to send command')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-shell">
      <Header connection={connection} timestamp={state.timestamp} source={source} />
      <main>
        {error && <button className="error-toast" onClick={clearError}>{error}<span>×</span></button>}
        <FactoryFloor state={state} />
        <div className="dashboard-grid">
          <StatusPanel state={state} />
          <ProductionPanel production={state.production} />
        </div>
        <HistoryDashboard />
        <Controls state={state} busy={busy} connected={connection === 'connected'} onCommand={handleCommand} />
      </main>
      <footer><span>MiniFactoryTwin v0.4</span><span>SIMULATED DEVICE</span></footer>
    </div>
  )
}

export default App
