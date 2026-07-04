/* 回测净值图纯逻辑 — 旧 static/js/pages/backtests.js 计算部分的对等抽取:
 * 基准对齐/同窗超额/叠加重定基/买卖标记聚合/回撤/共享轴对齐/tooltip 组装。
 * 无 Vue/ECharts 依赖, Vitest 直测; 边界语义逐条平移, 以旧代码为 source of truth。 */

import type { BacktestRun, BacktestStrategy, BacktestTrade } from '@/api/types'

export const pct = (v: number): string => `${(v * 100).toFixed(2)}%`
export const f3 = (v: number): string => v.toFixed(3)

/* y 轴刻度: 万元缩写 */
export const wan = (v: number): string =>
  Math.abs(v) >= 10000 ? `${(v / 10000).toFixed(1)}万` : `${v}`

/* params/trades 来自 DB(历史 CLI 写入不可假定干净) — tooltip 走 HTML 渲染必须转义;
 * 模板插值由 Vue 自动转义, 此函数只服务字符串拼 HTML 的场景 */
export function esc(s: unknown): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/* 有净值曲线的策略 — 旧 CLI 行可能无曲线 */
export function strategiesWithCurve(run: BacktestRun): BacktestStrategy[] {
  return run.strategies.filter((s) => (s.equity_curve.dates ?? []).length > 0)
}

/* 基准/超额/缩放一律配对首个有曲线的策略(全无曲线时回退首策略) */
export function firstStrategy(run: BacktestRun): BacktestStrategy | undefined {
  return strategiesWithCurve(run)[0] ?? run.strategies[0]
}

/* 非首策略日期轴可能不一致 — 一律按自身日期映射到共享轴 */
export function alignToAxis(
  axisDates: string[],
  s: BacktestStrategy,
  first: BacktestStrategy | undefined,
  values: (number | null)[],
): (number | null)[] {
  if (s === first) return values
  const own = new Map((s.equity_curve.dates ?? []).map((d, i) => [d, i]))
  return axisDates.map((d) => {
    const i = own.get(d)
    return i === undefined ? null : (values[i] ?? null)
  })
}

/* 回撤序列: v / 历史峰值 - 1 (%, 两位小数; 与净值同轴联动) */
export function drawdown(values: number[]): number[] {
  let peak = -Infinity
  return values.map((v) => {
    peak = Math.max(peak, v)
    return peak > 0 ? +((v / peak - 1) * 100).toFixed(2) : 0
  })
}

/* 基准: 同额资金买入持有 — 对齐净值日期, 取当日或之前最近收盘价折算。
 * - 基准晚于回测起点上市 → 前段 null
 * - 基准日期与净值日期完全不相交 → null(等同无行情, 不许显示 0.00% 假基准) */
export function buildBenchmarkValues(
  equityDates: string[],
  barDates: string[],
  closes: (number | null)[],
  initialCapital: number | null,
): (number | null)[] | null {
  if (!barDates.length) return null
  const closeByDate = new Map(barDates.map((d, i) => [d, closes[i] ?? null]))
  const cap = initialCapital ?? 0 // 旧代码 null * x → 0 语义
  let base: number | null = null
  let last: number | null = null
  const values = equityDates.map((d) => {
    if (closeByDate.has(d)) last = closeByDate.get(d) ?? null
    if (last === null) return null
    if (base === null) base = last
    return +(cap * (last / base)).toFixed(2)
  })
  if (values.every((v) => v === null)) return null
  return values
}

export interface BenchmarkStats {
  benchReturn: number
  stratReturn: number
  alpha: number
  /* 基准晚于回测起点(首个有效点 k>0) → 同窗口径起始日; 否则 null */
  fromDate: string | null
}

/* 同窗口径超额: 基准晚于回测起点时, 策略收益重算到同一子窗口再比, 不许窗口错配。
 * 区间内基准有效点 <2 → null(调用方按"区间内行情不足"处理并丢弃基准线)。 */
export function benchmarkStats(
  benchSeries: (number | null)[],
  stratValues: number[],
  axisDates: string[],
): BenchmarkStats | null {
  const k = benchSeries.findIndex((v) => v !== null)
  const bv = benchSeries.filter((v): v is number => v !== null)
  if (bv.length < 2) return null
  const benchReturn = bv[bv.length - 1] / bv[0] - 1
  const stratReturn = stratValues[k] > 0 ? stratValues[stratValues.length - 1] / stratValues[k] - 1 : 0
  return {
    benchReturn,
    stratReturn,
    alpha: stratReturn - benchReturn,
    fromDate: k > 0 ? axisDates[k] : null,
  }
}

export interface OverlayLine {
  name: string
  data: (number | null)[]
  /* 该策略在叠加轮 strategies 中的原始序号(配色对位, 含被跳过者占号) */
  colorIdx: number
}

/* 叠加对比: 另一轮 run 重定基到当前 run 的初始资金(防窗口外收益误读)。
 * 锚 = 进入当前轴的首个 >0 净值; 锚点对齐 first.initial_capital(缺省 1);
 * 完全无重叠日期 → anyOverlap=false(调用方显示警示)。 */
export function rebaseOverlays(
  axisDates: string[],
  other: BacktestRun,
  first: BacktestStrategy | undefined,
): { lines: OverlayLine[]; anyOverlap: boolean } {
  const axisIdx = new Map(axisDates.map((d, i) => [d, i]))
  const cap = first?.initial_capital || 1
  const lines: OverlayLine[] = []
  let anyOverlap = false
  other.strategies.forEach((s, si) => {
    const od = s.equity_curve.dates ?? []
    if (!od.length) return
    const values = s.equity_curve.values ?? []
    let anchor: number | null = null
    const data: (number | null)[] = new Array<number | null>(axisDates.length).fill(null)
    od.forEach((d, i) => {
      const j = axisIdx.get(d)
      if (j === undefined) return
      const v = values[i]
      if (anchor === null && v > 0) anchor = v
      if (anchor !== null) data[j] = +(cap * (v / anchor)).toFixed(2)
    })
    if (anchor === null) return
    anyOverlap = true
    const rebased = s.start_date !== first?.start_date
    lines.push({
      name: `${other.run_id.slice(-6)}·${s.strategy}${rebased ? '(重定基)' : ''}`,
      data,
      colorIdx: si,
    })
  })
  return { lines, anyOverlap }
}

export interface TradeMarkerPoint {
  /* ECharts scatter 点: [日期, 该策略自身日期轴上的净值] */
  value: [string, number]
  trades: BacktestTrade[]
}

/* 买卖事件 → 散点: 按 (日期, 方向) 聚合(截面策略调仓日几十笔不糊成一团);
 * y 取该策略自己日期上的净值(多策略日期轴可能不一致);
 * 不在共享轴或不在自身日期轴上的成交丢弃; 未知方向丢弃。 */
export function groupTradeMarkers(
  s: BacktestStrategy,
  axisIdx: Map<string, number>,
): { BUY: TradeMarkerPoint[]; SELL: TradeMarkerPoint[] } {
  const own = new Map((s.equity_curve.dates ?? []).map((d, i) => [d, i]))
  const grouped: Record<'BUY' | 'SELL', Map<string, BacktestTrade[]>> = {
    BUY: new Map(),
    SELL: new Map(),
  }
  for (const tr of s.trades ?? []) {
    const g = tr.direction === 'BUY' || tr.direction === 'SELL' ? grouped[tr.direction] : undefined
    if (!g || !axisIdx.has(tr.date) || !own.has(tr.date)) continue
    const bucket = g.get(tr.date)
    if (bucket) bucket.push(tr)
    else g.set(tr.date, [tr])
  }
  const values = s.equity_curve.values ?? []
  const toPoints = (m: Map<string, BacktestTrade[]>): TradeMarkerPoint[] =>
    [...m.entries()].map(([d, ts]) => ({ value: [d, values[own.get(d)!]], trades: ts }))
  return { BUY: toPoints(grouped.BUY), SELL: toPoints(grouped.SELL) }
}

/* 密集判定: 有成交标记的日数(买日+卖日)超阈值 → 高频截面策略(如周调仓小市值)
 * 沿用稀疏样式会重叠成一坨大箭头糊图, 退化为小符号 */
export const DENSE_MARKER_DAYS = 120
export const isDenseMarkers = (buyDays: number, sellDays: number): boolean =>
  buyDays + sellDays > DENSE_MARKER_DAYS

/* 聚合笔数 → 符号尺寸: 稀疏 9px 起步每多一笔 +1.6 封顶 16; 密集恒 6px 不随笔数放大 */
export const markerSize = (n: number, dense = false): number =>
  dense ? 6 : Math.min(9 + (n - 1) * 1.6, 16)

/* path 字形(而非 triangle+rotate): 图例也能正确显示 ▲买/▼卖 区分形状 */
export const MARKER_UP = 'path://M0,-9 L9,7 L-9,7 Z' // ▲ 顶点朝上
export const MARKER_DOWN = 'path://M0,9 L9,-7 L-9,-7 Z' // ▼ 顶点朝下

/* 入库端 trades 截断上限(backtest_run_mapper._TRADES_CAP) */
export const TRADES_CAP = 2000

/* 截断的买卖留痕必须明示, 不许后段标记凭空消失 */
export function truncatedTradesStrategy(run: BacktestRun): BacktestStrategy | undefined {
  return run.strategies.find(
    (s) => (s.trades ?? []).length === TRADES_CAP && (s.trade_count ?? 0) > TRADES_CAP,
  )
}

export interface EChartsTooltipParam {
  axisValueLabel?: string
  marker?: string
  seriesName?: string
  value?: unknown
  data?: unknown
}

/* axis tooltip: 成交点显前 3 笔明细(+等N笔), 其余序列显数值(回撤带 %)。
 * tooltip 走 HTML 渲染 — DB 字符串一律 esc, 数值经 Number 收口。 */
export function chartTooltipFormatter(params: EChartsTooltipParam[]): string {
  if (!params.length) return ''
  const lines = [params[0].axisValueLabel ?? '']
  for (const q of params) {
    const ts = (q.data as { trades?: BacktestTrade[] } | null | undefined)?.trades
    if (ts) {
      const head = ts.slice(0, 3).map(
        (t) =>
          `${t.direction === 'BUY' ? '买入' : '卖出'} ${esc(t.symbol)} ` +
          `${Number(t.volume)}股@${Number(t.price)}` +
          (t.direction === 'SELL'
            ? `（${t.pnl >= 0 ? '+' : ''}${Number(t.pnl).toFixed(2)}）`
            : ''),
      )
      lines.push(`${q.marker ?? ''}${head.join('；')}` + (ts.length > 3 ? ` 等${ts.length}笔` : ''))
    } else if (q.value !== null && q.value !== undefined) {
      const name = q.seriesName ?? ''
      const v = name.startsWith('回撤')
        ? `${q.value as number}%`
        : Math.round(q.value as number).toLocaleString()
      lines.push(`${q.marker ?? ''}${esc(name)}: ${v}`)
    }
  }
  return lines.join('<br>')
}
