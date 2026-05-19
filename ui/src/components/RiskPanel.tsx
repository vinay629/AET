import { useApi } from '../hooks/useApi'
import type { RiskData } from '../types'

export function RiskPanel() {
  const { data, loading } = useApi<RiskData>('risk', undefined, 2000)

  if (loading && !data) return <div className="text-text-muted p-4">Loading...</div>
  if (!data) return <div className="text-accent-red p-4">No risk data</div>

  const riskColor =
    data.risk_score === 'low' ? 'text-accent-green' :
    data.risk_score === 'medium' ? 'text-accent-yellow' :
    data.risk_score === 'high' ? 'text-accent-red' : 'text-accent-red'

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Risk Score */}
      <div className="panel">
        <div className="panel-header">Risk Score</div>
        <div className="flex items-center gap-4 mb-4">
          <span className={`text-4xl font-bold ${riskColor}`}>{data.risk_score.toUpperCase()}</span>
          {data.kill_switch.active && (
            <span className="status-badge status-unhealthy animate-pulse">⛔ KILL SWITCH ACTIVE</span>
          )}
        </div>
        {data.kill_switch.reasons.length > 0 && (
          <div className="bg-red-900/20 border border-red-800 rounded p-3 mb-4">
            <div className="text-accent-red text-xs font-semibold mb-1">Kill Switch Reasons:</div>
            {data.kill_switch.reasons.map((r, i) => (
              <div key={i} className="text-accent-red text-sm">• {r}</div>
            ))}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Metric label="Daily P&L" value={`$${parseFloat(data.daily_pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
          <Metric label="Drawdown" value={`${parseFloat(data.drawdown.current_pct).toFixed(2)}%`} />
        </div>
      </div>

      {/* Exposure */}
      <div className="panel">
        <div className="panel-header">Exposure</div>
        <div className="grid grid-cols-2 gap-3 mb-4">
          <Metric label="Total Exposure" value={`$${parseFloat(data.total_exposure).toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
          <Metric label="Exposure %" value={`${parseFloat(data.exposure_pct).toFixed(1)}%`} />
          <Metric label="Positions" value={data.position_count.toString()} />
          <Metric label="Max Exposure" value={data.limits.max_total_exposure ? `${(parseFloat(data.limits.max_total_exposure) * 100).toFixed(0)}%` : 'N/A'} />
        </div>
        {data.positions.length > 0 && (
          <div className="space-y-2">
            {data.positions.map((pos) => (
              <div key={pos.symbol} className="flex justify-between items-center bg-bg-tertiary rounded px-3 py-2">
                <span className="font-mono text-sm">{pos.symbol}</span>
                <div className="flex gap-4 text-xs">
                  <span className="text-text-muted">${parseFloat(pos.notional).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  <span className="text-accent-blue">{parseFloat(pos.pct_of_equity).toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Risk Limits */}
      <div className="panel lg:col-span-2">
        <div className="panel-header">Risk Limits</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(data.limits).map(([key, value]) => (
            <div key={key} className="bg-bg-tertiary rounded p-2">
              <div className="metric-label">{key.replace(/_/g, ' ')}</div>
              <div className="text-sm font-mono">
                {value.includes('.') && !value.includes('%')
                  ? `${(parseFloat(value) * 100).toFixed(1)}%`
                  : value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-bg-tertiary rounded p-2">
      <div className="metric-label">{label}</div>
      <div className="text-lg font-bold">{value}</div>
    </div>
  )
}
