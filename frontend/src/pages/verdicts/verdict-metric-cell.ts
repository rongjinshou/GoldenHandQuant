/* 判决卡 / 详情弹框 数值格子配色(设计 §6.1「涨跌色统一规则·全站」)。
 *
 * 一个界面一条颜色轴, 三分法:
 *   ① 行情色  正=红 t-up / 负=绿 t-down —— 任何"带符号的收益/超额收益"
 *             (Top超额·多空收益 及其 OOS 版)。语义等价于 backtests/metric-cell.ts 的
 *             marketCell(此处按因子字段名分派, 不跨页 import, 避免与并行流耦合)。
 *   ② 中性色  不上红绿 —— 预测力/质量指标(IC·IR·超额IR·各类正率·单调性)。
 *             理由: 好夏普/高 IC 强行上红会出现"好指标显红"的怪象。
 *   ③ 判定色  PASS/FAIL 徽章与闸门轨道(绿=判定通过, 非价格方向)不走这里,
 *             仍由模板 badge 类 + gates.ts 的 gateClass 承载。
 *
 * 取代 metric 展示处此前一律用 gcell(闸门判定色)着色的旧口径。 */

/** 带符号收益/超额收益字段 → 行情色; 其余因子指标 → 中性色。 */
const MARKET_METRICS: ReadonlySet<string> = new Set([
  'top_excess_return',
  'oos_top_excess_return',
  'long_short_return',
  'oos_long_short_return',
])

export type ColorMode = 'market' | 'neutral'

/** 字段名 → 配色语义。未登记为行情字段者一律中性。 */
export function metricColorMode(name: string): ColorMode {
  return MARKET_METRICS.has(name) ? 'market' : 'neutral'
}

/**
 * 数值格子配色类:
 *  - 行情字段: 正 t-up(红) / 负 t-down(绿) / 零 '' ；
 *  - 中性字段: 恒 '' ；
 *  - 无值: 恒 '' 。
 */
export function metricCellClass(name: string, v: number | null | undefined): string {
  if (v === null || v === undefined) return ''
  if (metricColorMode(name) !== 'market') return ''
  return v > 0 ? 't-up' : v < 0 ? 't-down' : ''
}

export interface MetricCell {
  text: string
  cls: string
}

/** 完整数值格子: 文本(无值 '-') + 配色类。取代 metric 展示处的 gcell(去掉闸门判定色)。 */
export function mcell(
  name: string,
  v: number | null | undefined,
  fmt: (x: number) => string,
): MetricCell {
  return { text: v === null || v === undefined ? '-' : fmt(v), cls: metricCellClass(name, v) }
}
