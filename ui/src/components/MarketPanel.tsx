import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import type { MarketData } from '../types'

export function MarketPanel() {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [timeframe, setTimeframe] = useState('1h')

  const { data, loading } = useApi<MarketData>('market', { symbol, timeframe, limit: '200' }, 5000)

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="panel flex items-center gap-4">
        <div>
          <label className="metric-label">Symbol</label>
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="bg-bg-tertiary border border-border-default rounded px-3 py-1 text-sm"
          >
            <option value="BTCUSDT">BTCUSDT</option>
            <option value="ETHUSDT">ETHUSDT</option>
            <option value="SOLUSDT">SOLUSDT</option>
          </select>
        </div>
        <div>
          <label className="metric-label">Timeframe</label>
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-bg-tertiary border border-border-default rounded px-3 py-1 text-sm"
          >
            <option value="1m">1m</option>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
            <option value="1d">1d</option>
          </select>
        </div>
        {data && (
          <div className="ml-auto flex gap-4 text-sm text-text-muted">
            <span>Candles: {data.candle_count}</span>
            <span className={`status-badge ${
              data.feed_health.status === 'healthy' ? 'status-healthy' :
              data.feed_health.status === 'stale' ? 'status-degraded' : 'status-unhealthy'
            }`}>
              Feed: {data.feed_health.status}
            </span>
          </div>
        )}
      </div>

      {/* Candle Table */}
      {loading && !data ? (
        <div className="text-text-muted p-4">Loading...</div>
      ) : data ? (
        <div className="panel">
          <div className="panel-header">Candles ({data.candle_count})</div>
          <div className="overflow-x-auto max-h-96">
            <table className="w-full text-xs font-mono">
              <thead className="sticky top-0 bg-bg-secondary">
                <tr className="text-text-muted">
                  <th className="text-left py-2 px-2">Time</th>
                  <th className="text-right py-2 px-2">Open</th>
                  <th className="text-right py-2 px-2">High</th>
                  <th className="text-right py-2 px-2">Low</th>
                  <th className="text-right py-2 px-2">Close</th>
                  <th className="text-right py-2 px-2">Volume</th>
                  <th className="text-right py-2 px-2">Trades</th>
                </tr>
              </thead>
              <tbody>
                {data.candles.slice(-50).reverse().map((c, i) => (
                  <tr key={i} className="border-t border-border-default">
                    <td className="py-1 px-2 text-text-muted">{c.timestamp.slice(0, 16)}</td>
                    <td className="py-1 px-2 text-right">{c.open.toLocaleString()}</td>
                    <td className="py-1 px-2 text-right text-accent-green">{c.high.toLocaleString()}</td>
                    <td className="py-1 px-2 text-right text-accent-red">{c.low.toLocaleString()}</td>
                    <td className={`py-1 px-2 text-right ${c.close >= c.open ? 'text-accent-green' : 'text-accent-red'}`}>
                      {c.close.toLocaleString()}
                    </td>
                    <td className="py-1 px-2 text-right text-text-muted">{c.volume.toFixed(2)}</td>
                    <td className="py-1 px-2 text-right text-text-muted">{c.trade_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="text-accent-red p-4">No market data</div>
      )}
    </div>
  )
}
