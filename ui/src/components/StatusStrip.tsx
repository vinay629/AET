import type { StatusData } from '../types'

interface Props {
  status: StatusData | null
  wsConnected: boolean
}

export function StatusStrip({ status, wsConnected }: Props) {
  if (!status) {
    return (
      <div className="bg-bg-secondary border-b border-border-default px-4 py-2 flex items-center justify-between">
        <span className="text-text-muted text-sm">Connecting...</span>
      </div>
    )
  }

  const pnlColor = parseFloat(status.total_pnl) >= 0 ? 'text-accent-green' : 'text-accent-red'
  const engineStatusClass =
    status.engine === 'RUNNING' ? 'status-running' :
    status.engine === 'HALTED' ? 'status-halted' : 'status-stopped'

  return (
    <div className="bg-bg-secondary border-b border-border-default px-4 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center gap-6">
        {/* Connection */}
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-accent-green' : 'bg-accent-red'}`} />
          <span className="text-text-muted">{wsConnected ? 'LIVE' : 'POLLING'}</span>
        </div>

        {/* Engine Status */}
        <div className="flex items-center gap-2">
          <span className="text-text-muted">ENGINE:</span>
          <span className={`status-badge ${engineStatusClass}`}>{status.engine}</span>
        </div>

        {/* Equity */}
        <div className="flex items-center gap-2">
          <span className="text-text-muted">EQUITY:</span>
          <span className="font-bold">${parseFloat(status.equity).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>

        {/* PnL */}
        <div className="flex items-center gap-2">
          <span className="text-text-muted">P&L:</span>
          <span className={`font-bold ${pnlColor}`}>
            {parseFloat(status.total_pnl) >= 0 ? '+' : ''}${parseFloat(status.total_pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}
            <span className="text-xs ml-1">({parseFloat(status.total_pnl_pct).toFixed(2)}%)</span>
          </span>
        </div>

        {/* Risk Score */}
        <div className="flex items-center gap-2">
          <span className="text-text-muted">RISK:</span>
          <span className={`status-badge ${
            status.risk_score === 'low' ? 'status-healthy' :
            status.risk_score === 'medium' ? 'status-degraded' :
            'status-unhealthy'
          }`}>{status.risk_score.toUpperCase()}</span>
        </div>

        {/* Kill Switch */}
        {status.kill_switch && (
          <span className="status-badge status-unhealthy animate-pulse">⛔ KILL SWITCH</span>
        )}
      </div>

      <div className="flex items-center gap-4 text-text-muted text-xs">
        <span>Events: {status.event_count.toLocaleString()}</span>
        <span>Seq: {status.latest_sequence.toLocaleString()}</span>
        <span>Invariants: {status.invariants}</span>
      </div>
    </div>
  )
}
