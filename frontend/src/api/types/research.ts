/* /api/research 族类型 — 手写, 对齐 routes/research.py 实际返回 */

export interface TableStat {
  rows: number
  symbols: number
  min_date: string | null
  max_date: string | null
}

export interface OverviewData {
  db_exists: boolean
  db_path: string
  feature_version: number | string
  tables: Record<string, TableStat>
  verdict_runs: number
}

export interface VerdictFactor {
  factor_id: string
  factor_name?: string | null
  expression?: string | null
  ic_mean: number | null
  ir: number | null
  ic_positive_rate: number | null
  monotonicity_score: number | null
  long_short_return: number | null
  oos_ic_mean: number | null
  oos_ir: number | null
  oos_long_short_return: number | null
  excess_ir: number | null
  excess_positive_rate: number | null
  top_excess_return: number | null
  oos_top_excess_return: number | null
  score: number | null
  grade: string | null
  passed: boolean
  reasons: string[] | null
}

export interface VerdictRun {
  run_id: string
  created_at: string
  params: {
    start?: string
    end?: string
    split?: string | null
    rebalance_days?: number
    objective?: string
    universe_count?: number
    feature_version?: number | string
  } | null
  factors: VerdictFactor[]
}

export interface MetaFactor {
  factor_id: string
  name: string
  expression?: string | null
  field_ready?: boolean
}
