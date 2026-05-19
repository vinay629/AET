import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import type { ReplayData } from '../types'

export function ReplayPanel() {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)

  const { data, loading } = useApi<ReplayData>('replay', selectedDate ? { date: selectedDate } : undefined, 5000)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Replay Controls */}
      <div className="panel">
        <div className="panel-header">Replay Console</div>
        <div className="space-y-3">
          <div>
            <label className="metric-label">Date</label>
            <select
              value={selectedDate || ''}
              onChange={(e) => setSelectedDate(e.target.value || null)}
              className="w-full bg-bg-tertiary border border-border-default rounded px-3 py-2 text-sm"
            >
              <option value="">Today</option>
              {data?.available_dates.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>

          {data && (
            <>
              <div className="grid grid-cols-2 gap-2">
                <Metric label="Total Events" value={data.total_events.toLocaleString()} />
                <Metric label="Checkpoints" value={data.checkpoints.length.toString()} />
              </div>

              <div className={`status-badge ${
                data.certification_status === 'passed' ? 'status-healthy' :
                data.certification_status === 'failed' ? 'status-unhealthy' : ''
              }`}>
                Certification: {data.certification_status}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Checkpoints */}
      <div className="panel">
        <div className="panel-header">Checkpoints</div>
        {loading ? (
          <div className="text-text-muted text-sm">Loading...</div>
        ) : data && data.checkpoints.length > 0 ? (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {data.checkpoints.map((cp) => (
              <div key={cp.sequence} className="bg-bg-tertiary rounded p-2 font-mono text-xs">
                <div className="flex justify-between">
                  <span>Seq: {cp.sequence}</span>
                  <span className="text-text-muted">Events: {cp.event_count}</span>
                </div>
                <div className="text-accent-blue">Hash: {cp.state_hash}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-text-muted text-sm">No checkpoints</div>
        )}
      </div>

      {/* Event Timeline */}
      <div className="panel">
        <div className="panel-header">Event Timeline</div>
        {loading ? (
          <div className="text-text-muted text-sm">Loading...</div>
        ) : data && data.timeline.length > 0 ? (
          <div className="space-y-1 max-h-96 overflow-y-auto">
            {data.timeline.slice(-30).reverse().map((event, i) => (
              <div key={i} className="bg-bg-tertiary rounded p-2 text-xs">
                <div className="flex justify-between text-text-muted">
                  <span>#{event.sequence}</span>
                  <span>{event.type}</span>
                </div>
                <div className="font-mono truncate">{event.summary}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-text-muted text-sm">No events</div>
        )}
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-bg-tertiary rounded p-2">
      <div className="metric-label">{label}</div>
      <div className="text-sm font-bold">{value}</div>
    </div>
  )
}
