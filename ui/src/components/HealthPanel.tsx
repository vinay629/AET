import { useApi } from '../hooks/useApi'
import type { HealthData } from '../types'

export function HealthPanel() {
  const { data, loading } = useApi<HealthData>('health', undefined, 1000)

  if (loading && !data) return <div className="text-text-muted p-4">Loading...</div>
  if (!data) return <div className="text-accent-red p-4">No health data</div>

  const statusClass =
    data.engine_status === 'RUNNING' ? 'status-running' :
    data.engine_status === 'HALTED' ? 'status-halted' : 'status-stopped'

  const invariantClass =
    data.invariants.status === 'healthy' ? 'status-healthy' : 'status-degraded'

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Engine Status */}
      <div className="panel">
        <div className="panel-header">Engine Status</div>
        <div className="flex items-center gap-3 mb-4">
          <span className={`status-badge ${statusClass} text-lg px-3 py-1`}>
            {data.engine_status}
          </span>
          <span className="text-text-muted text-sm">
            Uptime: {Math.floor(data.uptime_seconds)}s
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Metric label="Total Events" value={data.event_pipeline.total_events.toLocaleString()} />
          <Metric label="Latest Sequence" value={data.event_pipeline.latest_sequence.toLocaleString()} />
          <Metric label="Errors" value={data.event_pipeline.error_count.toString()} />
          <Metric label="Invariant Status" value={data.invariants.status} badge={invariantClass} />
        </div>
      </div>

      {/* Event Pipeline */}
      <div className="panel">
        <div className="panel-header">Event Pipeline</div>
        <div className="grid grid-cols-3 gap-3 mb-4">
          <Metric label="p50 Latency" value={`${data.latency.p50_ms.toFixed(1)}ms`} />
          <Metric label="p95 Latency" value={`${data.latency.p95_ms.toFixed(1)}ms`} />
          <Metric label="p99 Latency" value={`${data.latency.p99_ms.toFixed(1)}ms`} />
        </div>
        <div className="text-text-muted text-xs mb-2">Event Types</div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(data.event_pipeline.event_types).map(([type, count]) => (
            <span key={type} className="bg-bg-tertiary px-2 py-1 rounded text-xs">
              {type}: {count}
            </span>
          ))}
        </div>
      </div>

      {/* Invariant Status */}
      <div className="panel">
        <div className="panel-header">Invariant Status</div>
        <div className="grid grid-cols-2 gap-3">
          <Metric label="Violations (last 100)" value={data.invariants.violations_last_100.toString()} />
          <Metric label="Status" value={data.invariants.status} badge={
            data.invariants.status === 'healthy' ? 'status-healthy' : 'status-degraded'
          } />
        </div>
      </div>

      {/* Connection Status */}
      <div className="panel">
        <div className="panel-header">Connection Status</div>
        <div className="grid grid-cols-2 gap-3">
          <Metric label="WebSocket" value="Connected" badge="status-healthy" />
          <Metric label="REST API" value="Active" badge="status-healthy" />
          <Metric label="Reconnects" value="0" />
          <Metric label="Heartbeat Age" value="<1s" />
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value, badge }: { label: string; value: string; badge?: string }) {
  return (
    <div className="bg-bg-tertiary rounded p-2">
      <div className="metric-label">{label}</div>
      <div className="flex items-center gap-2">
        <span className="metric-value text-lg">{value}</span>
        {badge && <span className={`status-badge ${badge}`}>{value}</span>}
      </div>
    </div>
  )
}
