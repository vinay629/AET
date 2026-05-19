/** Read-only types derived from the API. No mutation, no side effects. */

export interface StatusData {
  engine: string
  equity: string
  total_pnl: string
  total_pnl_pct: string
  drawdown: string
  kill_switch: boolean
  risk_score: string
  event_count: number
  latest_sequence: number
  invariants: string
}

export interface HealthData {
  engine_status: string
  event_pipeline: {
    total_events: number
    latest_sequence: number
    event_types: Record<string, number>
    error_count: number
  }
  latency: {
    p50_ms: number
    p95_ms: number
    p99_ms: number
  }
  invariants: {
    violations_last_100: number
    status: string
  }
  uptime_seconds: number
}

export interface PortfolioData {
  equity: string
  cash: string
  initial_cash: string
  realized_pnl: string
  unrealized_pnl: string
  total_pnl: string
  total_pnl_pct: string
  positions: Position[]
  position_count: number
  trade_count: number
  recent_trades: Trade[]
  equity_curve: EquityPoint[]
  drawdown: {
    current: string
    max: string
    max_pct: string
  }
}

export interface Position {
  symbol: string
  units: string
  avg_entry_price: string
  notional: string
}

export interface Trade {
  symbol: string
  side: string
  price: string
  units: string
  fee: string
  timestamp: string | null
}

export interface EquityPoint {
  timestamp: string
  equity: string
  cash: string
}

export interface RiskData {
  total_equity: string
  total_exposure: string
  exposure_pct: string
  positions: RiskPosition[]
  position_count: number
  drawdown: {
    current: string
    current_pct: string
    peak_equity: string
  }
  daily_pnl: string
  kill_switch: {
    active: boolean
    reasons: string[]
  }
  limits: Record<string, string>
  risk_score: string
}

export interface RiskPosition {
  symbol: string
  notional: string
  pct_of_equity: string
}

export interface MarketData {
  symbol: string
  timeframe: string
  candles: Candle[]
  candle_count: number
  feed_health: {
    status: string
    last_candle_age_seconds: number | null
    gap_count: number
    total_candles: number
  }
}

export interface Candle {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  quote_volume: number
  trade_count: number
  is_closed: boolean
}

export interface ReplayData {
  date: string
  total_events: number
  timeline: TimelineEvent[]
  checkpoints: Checkpoint[]
  certification_status: string
  available_dates: string[]
}

export interface TimelineEvent {
  sequence: number
  type: string
  source: string
  timestamp: string
  summary: string
}

export interface Checkpoint {
  sequence: number
  state_hash: string
  event_count: number
}

export interface StrategyData {
  signals: Signal[]
  signal_count: number
  risk_decisions: RiskDecision[]
  decision_traces: DecisionTrace[]
  strategy_stats: Record<string, StrategyStats>
}

export interface Signal {
  timestamp: string
  symbol: string
  action: string
  confidence: number
  strategy: string
  reason: string
}

export interface RiskDecision {
  timestamp: string
  symbol: string
  action: string
  approved: boolean
  reason: string
  risk_score: number
}

export interface DecisionTrace {
  timestamp: string
  symbol: string
  candle?: { open: number; close: number; volume: number }
  signal?: { action: string; confidence: number; strategy: string }
  risk?: { approved: boolean; reason: string }
  order?: { client_order_id: string; side: string; quantity: string }
  fill?: { price: string; units: string; fee: string }
}

export interface StrategyStats {
  signals: number
  buys: number
  sells: number
  holds: number
}

export interface AuditData {
  events: AuditEvent[]
  total: number
  offset: number
  limit: number
  hash_chain: {
    valid: boolean
    gaps: Array<{ from: number; to: number; missing: number }>
    duplicates: number[]
    total_events: number
    first_sequence: number
    last_sequence: number
  }
  state_diffs: StateDiff[]
}

export interface AuditEvent {
  event_id: string
  sequence: number
  type: string
  source: string
  timestamp_exchange: string
  timestamp_local: string
  payload: Record<string, unknown>
  schema_version: number
}

export interface StateDiff {
  event_id: string
  sequence: number
  type: string
  changes: Record<string, unknown>
}
