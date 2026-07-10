/* 总览「最近动态」发射台纯逻辑 — 最新判决轮/回测轮的取值与格式化。
 * 无 Vue 依赖, Vitest 直测; 命名与配色口径同源复用: 判决词汇对齐 verdicts/run-naming,
 * 回测标题走 backtests/run-naming.buildRunLabel, 收益行情色走 backtests/metric-cell。 */

import type { BacktestRun, StrategyMeta, VerdictRun } from '@/api/types'

import { firstStrategy, pct } from '../backtests/chart-data'
import { type Cell, marketCell } from '../backtests/metric-cell'
import { buildRunLabel } from '../backtests/run-naming'

/* 最新一轮: 两个列表端点均倒序入库(最新在首), 但不赌端序 — 按 created_at 字典序取最大
 * (时间戳字符串可直接比较), 并列/脏值保持先出现者; 空列表 → null。 */
export function latestOf<T extends { created_at: string }>(runs: T[]): T | null {
  if (!runs.length) return null
  return runs.reduce((best, r) => ((r.created_at ?? '') > (best.created_at ?? '') ? r : best))
}

/* 入库时间短格式 'YYYY-MM-DD HH:mm' — 研究轮 created_at 为空格分隔(DB), 任务类为 ISO 'T',
 * 两种都归一; 保留年份(跨年可分辨, 同 run-naming P8 决策); 空值兜底 '—'。 */
export function shortTime(createdAt: string | null | undefined): string {
  const s = (createdAt ?? '').slice(0, 16).replace('T', ' ')
  return s || '—'
}

export interface VerdictActivity {
  runId: string
  factorCount: number
  passCount: number
  failCount: number
  /* '切分 YYYY-MM-DD' | '未切分' — 词汇同判决页 buildVerdictRunLabel */
  splitText: string
  createdAt: string
}

export function verdictActivity(run: VerdictRun): VerdictActivity {
  const passCount = run.factors.filter((f) => f.passed).length
  const split = run.params?.split
  return {
    runId: run.run_id,
    factorCount: run.factors.length,
    passCount,
    failCount: run.factors.length - passCount,
    splitText: split ? `切分 ${split}` : '未切分',
    createdAt: shortTime(run.created_at),
  }
}

export interface BacktestActivity {
  runId: string
  /* 业务人话标题(策略 · 对象 · 年份) — 复用回测页 buildRunLabel; meta 未载/失败降级原名 */
  title: string
  /* 总收益: A股行情色(涨红 t-up / 跌绿 t-down), 空值 '-' — 口径同回测页指标表 marketCell */
  ret: Cell
  createdAt: string
}

export function backtestActivity(run: BacktestRun, meta: StrategyMeta[]): BacktestActivity {
  return {
    runId: run.run_id,
    title: buildRunLabel(run, meta).title,
    ret: marketCell(firstStrategy(run)?.total_return, pct),
    createdAt: shortTime(run.created_at),
  }
}
