/* /api/live 族类型 — 手写, 对齐 routes/live.py 实际返回
 * (SELECT * 即 trading.db 表列, 见 infrastructure/persistence/trading_store.py 与
 *  repositories/audit_log_repository.py 的 DDL)。 */

export interface AccountSnapshot {
  snapshot_time: string
  mode: string
  total_asset: number | null
  available_cash: number | null
  frozen_cash: number | null
  market_value: number | null
}

export interface LiveOverview {
  db_exists: boolean
  latest_account: AccountSnapshot | null
  cycles_today: number
  executions_today: number
}

export interface TradingCycle {
  cycle_id: string
  cycle_time: string
  mode: string
  strategy: string
  signals_generated: number
  orders_submitted: number
  orders_rejected: number
  orders_failed: number
  notional_submitted: number | null
  note: string | null
  created_at?: string | null
}

export interface ExecutionRecord {
  order_id: string
  cycle_id: string
  mode: string
  symbol: string
  direction: string
  signal_price: number | null
  exec_price: number | null
  volume: number | null
  notional: number | null
  status: string
  reject_reason: string | null
  strategy_name: string | null
  confidence: number | null
  submitted_at: string
  final_status_at: string | null
  status_trail?: string
}

export interface PositionSnapshot {
  snapshot_time: string
  mode: string
  symbol: string
  total_volume: number | null
  available_volume: number | null
  average_cost: number | null
  last_price: number | null
}

export interface LivePositions {
  positions: PositionSnapshot[]
  snapshot_time: string | null
}

export interface LiveEquity {
  series: AccountSnapshot[]
}

export interface LiveBudget {
  date: string
  submitted_notional: number
  daily_notional_cap: number | null
  per_order_notional_cap: number | null
  remaining: number | null
}

/* trading.yaml auto_trade 段白名单键(_load_auto_trade_section), 全部可缺省 */
export interface AutoTradeConfig {
  enabled?: boolean
  mode?: string
  strategy?: string
  symbols?: string[]
  execution_times?: string[]
  min_confidence?: number
  max_orders_per_cycle?: number
  per_order_notional_cap?: number
  daily_notional_cap?: number
  daily_loss_limit_ratio?: number
}

export interface LiveConfig {
  config_exists: boolean
  auto_trade: AutoTradeConfig
  today: {
    expected_slots: string[]
    cycles_today: number
  }
}

export interface AuditLog {
  log_id: string
  user_id?: string
  action: string
  resource_type: string | null
  resource_id: string | null
  timestamp: string | null
  details: string | null
  ip_address?: string
}

/* ticket 留痕 JSON 内容 — 面板消费的已知字段; 文件内容自由格式故留 index signature,
 * 且 content 本身可能是非对象(损坏文件 json.loads 出 null/标量), 消费侧 unknown 收窄 */
export interface TicketContent {
  symbol?: string | null
  direction?: string | null
  price?: number | string | null
  volume?: number | string | null
  notional?: number | string | null
  status?: string | null
  final_status?: string | null
  order_id?: string | number | null
  submitted_at?: string | null
  requested_at?: string | null
  [key: string]: unknown
}

export interface LiveTicket {
  file: string
  content: unknown
}
