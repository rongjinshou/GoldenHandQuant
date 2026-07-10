export interface Cell {
  text: string
  cls: string
}

/** 带符号收益/盈亏 → A股行情色（涨/正=红 t-up, 跌/负=绿 t-down） */
export function marketCell(v: number | null | undefined, fmt: (x: number) => string): Cell {
  if (v === null || v === undefined) return { text: '-', cls: 't-muted' }
  return { text: fmt(v), cls: v > 0 ? 't-up' : v < 0 ? 't-down' : '' }
}

/** 质量指标（夏普/Calmar/胜率等）→ 中性，不上红绿（越大越好但非涨跌） */
export function qualityCell(v: number | null | undefined, fmt: (x: number) => string): Cell {
  return { text: v === null || v === undefined ? '-' : fmt(v), cls: '' }
}

/** 最大回撤 → 超 20% 标失败红，否则中性 */
export function ddCell(v: number | null | undefined, fmt: (x: number) => string): Cell {
  if (v === null || v === undefined) return { text: '-', cls: '' }
  return { text: fmt(v), cls: v > 0.2 ? 't-fail' : '' }
}

/** 列最优方向: 'max'=越大越优, 'min'=越小越优, null=不参与评优(如交易数) */
export type MetricDirection = 'max' | 'min' | null

/** 指标表列方向表 — 与 Backtests.vue metricRows 的 cells 列序一一对应 */
export const METRIC_DIRECTIONS: readonly MetricDirection[] = [
  'max', // 总收益
  'max', // 年化
  'min', // 最大回撤
  'max', // 夏普
  'max', // 索提诺
  'max', // Calmar
  'max', // 胜率
  null, // 交易数(多寡无优劣)
  'min', // 换手
]

/**
 * 多策略同轮对比: 按方向表求每列最优单元格, 返回 `${rowIdx}-${colIdx}` 键集合。
 * 规则: 单行(<2 行)不评优返回空集; null/undefined/NaN 跳过不参赛; 并列最优全标。
 */
export function bestByColumn(
  rows: readonly (number | null | undefined)[][],
  directions: readonly MetricDirection[] = METRIC_DIRECTIONS,
): Set<string> {
  const best = new Set<string>()
  if (rows.length < 2) return best
  directions.forEach((dir, ci) => {
    if (!dir) return
    let bestVal: number | null = null
    for (const row of rows) {
      const v = row[ci]
      if (typeof v !== 'number' || Number.isNaN(v)) continue
      if (bestVal === null || (dir === 'max' ? v > bestVal : v < bestVal)) bestVal = v
    }
    if (bestVal === null) return
    rows.forEach((row, ri) => {
      if (row[ci] === bestVal) best.add(`${ri}-${ci}`)
    })
  })
  return best
}
