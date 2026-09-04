import { Activity, Factory } from 'lucide-react'
import type { ConnectionStatus } from '../types/machine'

interface HeaderProps {
  connection: ConnectionStatus
  timestamp: string
}

const connectionLabel: Record<ConnectionStatus, string> = {
  connected: 'LIVE',
  connecting: 'CONNECTING',
  disconnected: 'OFFLINE',
}

export function Header({ connection, timestamp }: HeaderProps) {
  const hasTimestamp = new Date(timestamp).getTime() > 0
  const time = hasTimestamp
    ? new Intl.DateTimeFormat('en', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(timestamp))
    : '--:--:--'

  return (
    <header className="topbar">
      <div className="brand-mark"><Factory size={22} strokeWidth={1.8} /></div>
      <div className="brand-copy">
        <h1>MiniFactoryTwin</h1>
        <span>CONVEYOR CELL · DT-01</span>
      </div>
      <div className="topbar-spacer" />
      <div className="system-time">{time} KST</div>
      <div className={`connection-badge ${connection}`}>
        <Activity size={15} />
        <span>{connectionLabel[connection]}</span>
      </div>
    </header>
  )
}

