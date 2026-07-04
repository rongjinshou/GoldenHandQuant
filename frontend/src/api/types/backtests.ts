/* /api/research/backtests + /api/meta/strategies 族类型 — 手写,
 * 对齐 routes/research.py backtests handler(equity_curve/params/trades 已解析为对象)
 * 与 backtest_run_mapper.build_backtest_run_row 字段。 */

export interface BacktestTrade {
  date: string
  symbol: string
  /* 正常为 'BUY' | 'SELL'; DB 历史行不可假定干净, 未知方向前端丢弃 */
  direction: string
  price: number
  volume: number
  pnl: number
}

/* 旧 CLI 行可能无曲线 → dates/values 缺省 */
export interface EquityCurve {
  dates?: string[]
  values?: number[]
}

/* run_backtest 源写 strategy(单数), compare_strategies/网页任务写 strategies(复数) */
export interface BacktestRunParams {
  symbols?: string[]
  strategies?: string[]
  strategy?: string
  source?: string
  timeframe?: string
  [key: string]: unknown
}

export interface BacktestStrategy {
  strategy: string
  start_date: string | null
  end_date: string | null
  initial_capital: number | null
  params: BacktestRunParams
  total_return: number | null
  annualized_return: number | null
  max_drawdown: number | null
  sharpe_ratio: number | null
  sortino_ratio: number | null
  calmar_ratio: number | null
  win_rate: number | null
  trade_count: number | null
  turnover_rate: number | null
  equity_curve: EquityCurve
  /* 旧行无留痕 → 空列表(不画买卖标记); 入库端截断上限 2000 笔 */
  trades: BacktestTrade[]
}

export interface BacktestRun {
  run_id: string
  created_at: string
  strategies: BacktestStrategy[]
}

/* /api/meta/strategies 单条 — strategy_type: 'bar'(时序) | 'cross_section'(截面) */
export interface StrategyMeta {
  name: string
  strategy_type: string
  description: string
  default_params: Record<string, unknown>
}
