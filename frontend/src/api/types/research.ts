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
