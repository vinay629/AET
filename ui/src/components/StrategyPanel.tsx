import { useApi } from '../hooks/useApi'
import type { StrategyData } from '../types'

export function StrategyPanel() {
  const { data, loading } = useApi<StrategyData>('strategy', undefined, 2000)

  if (loading && !data) return <div className="text-text-muted p-4">Loading...</div>
  if (!data) return <div className="text-accent-red p-4">No strategy data</div>

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Signal Stream */}
      <div className="panel">
        <div className="panel-header">Signal Stream ({data.signal_count})</div>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {data.signals.slice(-20).reverse().map((signal, i) => (
            <div key={i} className="bg-bg-tertiary rounded p-2 text-xs">
              <div className="flex justify-between">
                <span className="font-mono">{signal.symbol}</span>
                <span className={`font-bold ${
                  signal.action === 'BUY' ? 'text-accent-green' :
                  signal.action === 'SELL' ? 'text-accent-red' : 'text-text-muted'
                }`}>{signal.action}</span>
              </div>
              <div className="flex justify-between text-text-muted mt-1">
                <span>{signal.strategy}</span>
                <span>Conf: {(signal.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Strategy Stats */}
      <div className="panel">
        <div className="panel-header">Strategy Stats</div>
        {Object.keys(data.strategy_stats).length === 0 ? (
          <div className="text-text-muted text-sm">No strategy data</div>
        ) : (
          <div className="space-y-3">
            {Object.entries(data.strategy_stats).map(([name, stats]) => (
              <div key={name} className="bg-bg-tertiary rounded p-3">
                <div className="font-bold mb-2">{name}</div>
                <div className="grid grid-cols-4 gap-2 text-xs">
                  <div>
                    <div className="text-text-muted">Signals</div>
                    <div className="font-bold">{stats.signals}</div>
                  </div>
                  <div>
                    <div className="text-text-muted">Buys</div>
                    <div className="font-bold text-accent-green">{stats.buys}</div>
                  </div>
                  <div>
                    <div className="text-text-muted">Sells</div>
                    <div className="font-bold text-accent-red">{stats.sells}</div>
                  </div>
                  <div>
                    <div className="text-text-muted">Holds</div>
                    <div className="font-bold text-text-muted">{stats.holds}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Decision Traces */}
      <div className="panel lg:col-span-2">
        <div className="panel-header">Decision Traces</div>
        {data.decision_traces.length === 0 ? (
          <div className="text-text-muted text-sm">No decision traces</div>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {data.decision_traces.slice(-10).reverse().map((trace, i) => (
              <div key={i} className="bg-bg-tertiary rounded p-3 text-xs">
                <div className="flex justify-between mb-2">
                  <span className="font-mono">{trace.symbol}</span>
                  <span className="text-text-muted">{trace.timestamp.slice(0, 19)}</span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {trace.candle && (
                    <span className="bg-bg-secondary px-2 py-1 rounded">
                      Candle: {trace.candle.close}
                    </span>
                  )}
                  {trace.signal && (
                    <span className={`px-2 py-1 rounded ${
                      trace.signal.action === 'BUY' ? 'bg-green-900/30 text-accent-green' :
                      trace.signal.action === 'SELL' ? 'bg-red-900/30 text-accent-red' :
                      'bg-gray-800 text-text-muted'
                    }`}>
                      Signal: {trace.signal.action} ({(trace.signal.confidence * 100).toFixed(0)}%)
                    </span>
                  )}
                  {trace.risk && (
                    <span className={`px-2 py-1 rounded ${
                      trace.risk.approved ? 'bg-green-900/30 text-accent-green' : 'bg-red-900/30 text-accent-red'
                    }`}>
                      Risk: {trace.risk.approved ? 'PASS' : 'REJECT'}
                    </span>
                  )}
                  {trace.order && (
                    <span className="bg-blue-900/30 text-accent-blue px-2 py-1 rounded">
                      Order: {trace.order.side}
                    </span>
                  )}
                  {trace.fill && (
                    <span className="bg-purple-900/30 text-accent-purple px-2 py-1 rounded">
                      Fill: {trace.fill.price}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
