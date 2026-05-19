import { useState, useEffect, useCallback } from 'react'
import { StatusStrip } from './components/StatusStrip'
import { HealthPanel } from './components/HealthPanel'
import { PortfolioPanel } from './components/PortfolioPanel'
import { RiskPanel } from './components/RiskPanel'
import { MarketPanel } from './components/MarketPanel'
import { ReplayPanel } from './components/ReplayPanel'
import { StrategyPanel } from './components/StrategyPanel'
import { AuditPanel } from './components/AuditPanel'
import { useWebSocket } from './hooks/useWebSocket'
import type { StatusData } from './types'

type TabId = 'health' | 'portfolio' | 'risk' | 'market' | 'replay' | 'strategy' | 'audit'

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'health', label: 'System Health', icon: '⚡' },
  { id: 'portfolio', label: 'Portfolio', icon: '📊' },
  { id: 'risk', label: 'Risk', icon: '🛡️' },
  { id: 'market', label: 'Market', icon: '📈' },
  { id: 'replay', label: 'Replay', icon: '🔄' },
  { id: 'strategy', label: 'Strategy', icon: '🧠' },
  { id: 'audit', label: 'Audit', icon: '🔍' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('health')
  const [status, setStatus] = useState<StatusData | null>(null)

  const handleWsMessage = useCallback((data: { type: string; data: StatusData }) => {
    if (data.type === 'status' || data.type === 'init') {
      setStatus(data.data)
    }
  }, [])

  const { connected } = useWebSocket('ws://localhost:8080/ws', handleWsMessage)

  // Fallback polling if WebSocket is disconnected
  useEffect(() => {
    if (connected) return
    const poll = async () => {
      try {
        const res = await fetch('/api/status')
        if (res.ok) setStatus(await res.json())
      } catch { /* silent */ }
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [connected])

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top Status Strip */}
      <StatusStrip status={status} wsConnected={connected} />

      {/* Tab Navigation */}
      <div className="border-b border-border-default bg-bg-secondary">
        <div className="flex overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-accent-blue text-accent-blue bg-bg-tertiary'
                  : 'border-transparent text-text-secondary hover:text-text-primary hover:bg-bg-tertiary'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-4 overflow-auto">
        {activeTab === 'health' && <HealthPanel />}
        {activeTab === 'portfolio' && <PortfolioPanel />}
        {activeTab === 'risk' && <RiskPanel />}
        {activeTab === 'market' && <MarketPanel />}
        {activeTab === 'replay' && <ReplayPanel />}
        {activeTab === 'strategy' && <StrategyPanel />}
        {activeTab === 'audit' && <AuditPanel />}
      </div>
    </div>
  )
}
