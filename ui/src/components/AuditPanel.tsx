import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import type { AuditData } from '../types'

export function AuditPanel() {
  const [searchSymbol, setSearchSymbol] = useState('')
  const [searchOrderId, setSearchOrderId] = useState('')
  const [searchType, setSearchType] = useState('')

  const params: Record<string, string | undefined> = {}
  if (searchSymbol) params.symbol = searchSymbol
  if (searchOrderId) params.order_id = searchOrderId
  if (searchType) params.event_type = searchType

  const { data, loading } = useApi<AuditData>('audit', params, 3000)

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="panel flex items-center gap-4 flex-wrap">
        <div>
          <label className="metric-label">Symbol</label>
          <input
            type="text"
            value={searchSymbol}
            onChange={(e) => setSearchSymbol(e.target.value)}
            placeholder="BTCUSDT"
            className="bg-bg-tertiary border border-border-default rounded px-3 py-1 text-sm w-32"
          />
        </div>
        <div>
          <label className="metric-label">Order ID</label>
          <input
            type="text"
            value={searchOrderId}
            onChange={(e) => setSearchOrderId(e.target.value)}
            placeholder="baet-..."
            className="bg-bg-tertiary border border-border-default rounded px-3 py-1 text-sm w-40"
          />
        </div>
        <div>
          <label className="metric-label">Event Type</label>
          <select
            value={searchType}
            onChange={(e) => setSearchType(e.target.value)}
            className="bg-bg-tertiary border border-border-default rounded px-3 py-1 text-sm"
          >
            <option value="">All</option>
            <option value="candle_received">Candle</option>
            <option value="signal_generated">Signal</option>
            <option value="risk_decision">Risk</option>
            <option value="order_submitted">Order Sub</option>
            <option value="order_filled">Order Fill</option>
            <option value="order_cancelled">Order Cancel</option>
            <option value="error">Error</option>
          </select>
        </div>
        {data && (
          <div className="ml-auto text-sm text-text-muted">
            Showing {data.events.length} of {data.total}
          </div>
        )}
      </div>

      {/* Hash Chain Status */}
      {data && (
        <div className="panel">
          <div className="panel-header">Hash Chain Verification</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric
              label="Chain Valid"
              value={data.hash_chain.valid ? 'YES' : 'NO'}
              badge={data.hash_chain.valid ? 'status-healthy' : 'status-unhealthy'}
            />
            <Metric label="Gaps" value={data.hash_chain.gaps.length.toString()} />
            <Metric label="Duplicates" value={data.hash_chain.duplicates.length.toString()} />
            <Metric label="Range" value={`${data.hash_chain.first_sequence} → ${data.hash_chain.last_sequence}`} />
          </div>
          {data.hash_chain.gaps.length > 0 && (
            <div className="mt-3 bg-yellow-900/20 border border-yellow-800 rounded p-2">
              <div className="text-accent-yellow text-xs font-semibold mb-1">Sequence Gaps:</div>
              {data.hash_chain.gaps.map((gap, i) => (
                <div key={i} className="text-xs text-text-muted">
                  {gap.from} → {gap.to} ({gap.missing} missing)
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Event List */}
      <div className="panel">
        <div className="panel-header">Events</div>
        {loading && !data ? (
          <div className="text-text-muted text-sm">Loading...</div>
        ) : data && data.events.length > 0 ? (
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {data.events.map((event) => (
              <div key={event.event_id} className="bg-bg-tertiary rounded p-3 text-xs">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-mono text-text-muted">#{event.sequence}</span>
                  <span className="font-bold">{event.type}</span>
                  <span className="text-text-muted">{event.source}</span>
                  <span className="text-text-muted">{event.timestamp_exchange.slice(0, 19)}</span>
                </div>
                <div className="font-mono text-text-muted truncate">
                  {JSON.stringify(event.payload).slice(0, 200)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-text-muted text-sm">No events found</div>
        )}
      </div>
    </div>
  )
}

function Metric({ label, value, badge }: { label: string; value: string; badge?: string }) {
  return (
    <div className="bg-bg-tertiary rounded p-2">
      <div className="metric-label">{label}</div>
      <div className="flex items-center gap-2">
        <span className="text-sm font-bold">{value}</span>
        {badge && <span className={`status-badge ${badge}`}>{value}</span>}
      </div>
    </div>
  )
}
