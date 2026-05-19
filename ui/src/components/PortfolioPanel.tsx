import { useApi } from '../hooks/useApi'
import type { PortfolioData } from '../types'

export function PortfolioPanel() {
  const { data, loading } = useApi<PortfolioData>('portfolio', undefined, 2000)

  if (loading && !data) return <div className="text-text-muted p-4">Loading...</div>
  if (!data) return <div className="text-accent-red p-4">No portfolio data</div>

  const pnlColor = parseFloat(data.total_pnl) >= 0 ? 'text-accent-green' : 'text-accent-red'

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Equity Overview */}
      <div className="lg:col-span-2 space-y-4">
        <div className="panel">
          <div className="panel-header">Equity</div>
          <div className="grid grid-cols-4 gap-4">
            <div>
              <div className="metric-label">Total Equity</div>
              <div className="metric-value">${parseFloat(data.equity).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
            </div>
            <div>
              <div className="metric-label">Cash</div>
              <div className="metric-value text-lg">${parseFloat(data.cash).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
            </div>
            <div>
              <div className="metric-label">Total P&L</div>
              <div className={`metric-value ${pnlColor}`}>
                {parseFloat(data.total_pnl) >= 0 ? '+' : ''}${parseFloat(data.total_pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className="metric-label">Return</div>
              <div className={`metric-value ${pnlColor}`}>{parseFloat(data.total_pnl_pct).toFixed(2)}%</div>
            </div>
          </div>
        </div>

        {/* Drawdown */}
        <div className="panel">
          <div className="panel-header">Drawdown</div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="metric-label">Current</div>
              <div className="metric-value text-accent-yellow">{(parseFloat(data.drawdown.current) * 100).toFixed(2)}%</div>
            </div>
            <div>
              <div className="metric-label">Max</div>
              <div className="metric-value text-accent-red">{parseFloat(data.drawdown.max_pct).toFixed(2)}%</div>
            </div>
            <div>
              <div className="metric-label">Peak Equity</div>
              <div className="metric-value text-lg">${parseFloat(data.drawdown.peak_equity || data.equity).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
            </div>
          </div>
        </div>

        {/* Recent Trades */}
        <div className="panel">
          <div className="panel-header">Recent Trades ({data.trade_count} total)</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-text-muted text-xs">
                  <th className="text-left py-2">Symbol</th>
                  <th className="text-left py-2">Side</th>
                  <th className="text-right py-2">Price</th>
                  <th className="text-right py-2">Units</th>
                  <th className="text-right py-2">Fee</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_trades.slice(-10).reverse().map((trade, i) => (
                  <tr key={i} className="border-t border-border-default">
                    <td className="py-2 font-mono">{trade.symbol}</td>
                    <td className={`py-2 ${trade.side === 'BUY' ? 'text-accent-green' : 'text-accent-red'}`}>
                      {trade.side}
                    </td>
                    <td className="py-2 text-right font-mono">${parseFloat(trade.price).toLocaleString()}</td>
                    <td className="py-2 text-right font-mono">{parseFloat(trade.units).toFixed(6)}</td>
                    <td className="py-2 text-right font-mono text-text-muted">${parseFloat(trade.fee).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Positions */}
      <div className="panel">
        <div className="panel-header">Positions ({data.position_count})</div>
        {data.positions.length === 0 ? (
          <div className="text-text-muted text-sm py-4 text-center">No open positions</div>
        ) : (
          <div className="space-y-3">
            {data.positions.map((pos) => (
              <div key={pos.symbol} className="bg-bg-tertiary rounded p-3">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-bold">{pos.symbol}</span>
                  <span className="text-text-muted text-xs">{parseFloat(pos.units).toFixed(6)} units</span>
                </div>
                <div className="flex justify-between text-xs text-text-muted">
                  <span>Avg Entry: ${parseFloat(pos.avg_entry_price).toLocaleString()}</span>
                  <span>Notional: ${parseFloat(pos.notional).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
