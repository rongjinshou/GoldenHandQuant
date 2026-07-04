import { describe, expect, it } from 'vitest'

import type { BacktestRun, BacktestStrategy, BacktestTrade } from '@/api/types'

import {
  alignToAxis,
  benchmarkStats,
  buildBenchmarkValues,
  chartTooltipFormatter,
  drawdown,
  esc,
  firstStrategy,
  groupTradeMarkers,
  markerSize,
  pct,
  rebaseOverlays,
  strategiesWithCurve,
  truncatedTradesStrategy,
} from '../chart-data'

/* 净值图纯逻辑 — 边界语义逐条对照旧 backtests.js */

function mkStrat(o: Partial<BacktestStrategy> = {}): BacktestStrategy {
  return {
    strategy: 'dual_ma',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    initial_capital: 1000,
    params: {},
    total_return: null,
    annualized_return: null,
    max_drawdown: null,
    sharpe_ratio: null,
    sortino_ratio: null,
    calmar_ratio: null,
    win_rate: null,
    trade_count: null,
    turnover_rate: null,
    equity_curve: {},
    trades: [],
    ...o,
  }
}

function mkTrade(o: Partial<BacktestTrade> = {}): BacktestTrade {
  return { date: 'd1', symbol: '000001.SZ', direction: 'BUY', price: 10, volume: 100, pnl: 0, ...o }
}

function mkRun(strategies: BacktestStrategy[], run_id = 'run_abc123'): BacktestRun {
  return { run_id, created_at: '2024-12-31T10:00:00', strategies }
}

describe('strategiesWithCurve / firstStrategy', () => {
  it('过滤无曲线策略, 参考策略取首个有曲线者', () => {
    const noCurve = mkStrat({ strategy: 'empty', equity_curve: {} })
    const withCurve = mkStrat({ strategy: 'ma', equity_curve: { dates: ['d1'], values: [1000] } })
    const run = mkRun([noCurve, withCurve])
    expect(strategiesWithCurve(run)).toEqual([withCurve])
    expect(firstStrategy(run)).toBe(withCurve)
  })

  it('全无曲线时参考策略回退首条', () => {
    const a = mkStrat({ strategy: 'a' })
    const run = mkRun([a])
    expect(strategiesWithCurve(run)).toEqual([])
    expect(firstStrategy(run)).toBe(a)
  })
})

describe('alignToAxis', () => {
  const axis = ['d1', 'd2', 'd3', 'd4']

  it('首策略直接返回自身值(轴即自身)', () => {
    const first = mkStrat({ equity_curve: { dates: axis, values: [1, 2, 3, 4] } })
    expect(alignToAxis(axis, first, first, [1, 2, 3, 4])).toEqual([1, 2, 3, 4])
  })

  it('非首策略按自身日期映射到共享轴, 缺失补 null', () => {
    const first = mkStrat({ equity_curve: { dates: axis, values: [1, 2, 3, 4] } })
    const other = mkStrat({ equity_curve: { dates: ['d2', 'd3'], values: [20, 30] } })
    expect(alignToAxis(axis, other, first, [20, 30])).toEqual([null, 20, 30, null])
  })
})

describe('drawdown', () => {
  it('相对历史峰值的百分比回撤, 峰值<=0 记 0', () => {
    // 峰值链: 100 -> 120 -> 120 -> 90
    expect(drawdown([100, 120, 108, 90])).toEqual([0, 0, -10, -25])
  })
})

describe('buildBenchmarkValues', () => {
  const axis = ['d1', 'd2', 'd3', 'd4']

  it('对齐净值日期 + 前值补齐 + 前段留 null, 折算到初始资金', () => {
    const series = buildBenchmarkValues(axis, ['d2', 'd3'], [10, 12], 1000)
    // d1 前段无收盘 → null; d2 base=10; d3=12; d4 无收盘取最近=12
    expect(series).toEqual([null, 1000, 1200, 1200])
  })

  it('基准与净值日期完全不相交 → null(不显示假基准)', () => {
    expect(buildBenchmarkValues(axis, ['x1', 'x2'], [10, 12], 1000)).toBeNull()
  })

  it('无 bars → null', () => {
    expect(buildBenchmarkValues(axis, [], [], 1000)).toBeNull()
  })
})

describe('benchmarkStats', () => {
  const axis = ['d1', 'd2', 'd3', 'd4']

  it('区间内有效点 <2 → null', () => {
    expect(benchmarkStats([null, null, 1000, null], [1, 2, 3, 4], axis)).toBeNull()
  })

  it('基准晚于回测起点时策略收益重算到同一子窗口 + fromDate', () => {
    // 基准首个有效点 k=1(d2); 策略同窗从 index 1 起
    const bench = [null, 1000, 1100, 1210]
    const strat = [1000, 1000, 1500, 2000]
    const stats = benchmarkStats(bench, strat, axis)
    expect(stats).not.toBeNull()
    expect(stats!.benchReturn).toBeCloseTo(0.21, 5) // 1210/1000 - 1
    expect(stats!.stratReturn).toBeCloseTo(1.0, 5) // 2000/1000 - 1
    expect(stats!.alpha).toBeCloseTo(0.79, 5)
    expect(stats!.fromDate).toBe('d2')
  })

  it('基准与净值起点对齐时 fromDate 为 null', () => {
    const stats = benchmarkStats([1000, 1100], [1000, 1200], ['d1', 'd2'])
    expect(stats!.fromDate).toBeNull()
  })
})

describe('rebaseOverlays', () => {
  const axis = ['d1', 'd2', 'd3', 'd4']
  const first = mkStrat({ start_date: '2024-01-01', initial_capital: 1000 })

  it('以进入当前轴首个正值为锚, 缩放到当前 run 初始资金 + 起点不同标(重定基)', () => {
    const other = mkRun(
      [mkStrat({ strategy: 'ma', start_date: '2024-02-01', equity_curve: { dates: ['d2', 'd3', 'd4'], values: [500, 600, 750] } })],
      'run_other99',
    )
    const { lines, anyOverlap } = rebaseOverlays(axis, other, first)
    expect(anyOverlap).toBe(true)
    expect(lines).toHaveLength(1)
    // 锚=500 → d2:1000, d3:1200, d4:1500; d1 无重叠留 null
    expect(lines[0].data).toEqual([null, 1000, 1200, 1500])
    expect(lines[0].name).toContain('(重定基)') // 起点不同
    expect(lines[0].colorIdx).toBe(0)
  })

  it('与当前区间无重叠日期 → anyOverlap=false 且不产线', () => {
    const other = mkRun([mkStrat({ equity_curve: { dates: ['z1', 'z2'], values: [100, 200] } })])
    const { lines, anyOverlap } = rebaseOverlays(axis, other, first)
    expect(anyOverlap).toBe(false)
    expect(lines).toHaveLength(0)
  })

  it('跳过无曲线策略', () => {
    const other = mkRun([mkStrat({ equity_curve: {} })])
    expect(rebaseOverlays(axis, other, first).lines).toHaveLength(0)
  })
})

describe('groupTradeMarkers', () => {
  const axisIdx = new Map([
    ['d1', 0],
    ['d2', 1],
    ['d3', 2],
  ])

  it('按(日期,方向)聚合, y 取自身净值; 未知方向/离轴/离自身日期均丢弃', () => {
    const s = mkStrat({
      equity_curve: { dates: ['d1', 'd2', 'd3'], values: [1000, 1100, 1050] },
      trades: [
        mkTrade({ date: 'd1', direction: 'BUY' }),
        mkTrade({ date: 'd1', direction: 'BUY', symbol: '000002.SZ' }),
        mkTrade({ date: 'd2', direction: 'SELL' }),
        mkTrade({ date: 'dX', direction: 'BUY' }), // 离共享轴
        mkTrade({ date: 'd3', direction: 'HOLD' }), // 未知方向
      ],
    })
    const { BUY, SELL } = groupTradeMarkers(s, axisIdx)
    expect(BUY).toHaveLength(1)
    expect(BUY[0].value).toEqual(['d1', 1000])
    expect(BUY[0].trades).toHaveLength(2)
    expect(SELL).toHaveLength(1)
    expect(SELL[0].value).toEqual(['d2', 1100])
  })
})

describe('markerSize', () => {
  it('9 起步, 每多一笔 +1.6, 封顶 16', () => {
    expect(markerSize(1)).toBe(9)
    expect(markerSize(2)).toBeCloseTo(10.6, 5)
    expect(markerSize(100)).toBe(16)
  })
})

describe('truncatedTradesStrategy', () => {
  it('恰 2000 笔且实际成交 >2000 → 命中(留痕明示)', () => {
    const cut = mkStrat({ strategy: 'busy', trades: new Array(2000).fill(mkTrade()), trade_count: 5000 })
    expect(truncatedTradesStrategy(mkRun([mkStrat(), cut]))).toBe(cut)
  })

  it('未截断 → undefined', () => {
    const s = mkStrat({ trades: [mkTrade()], trade_count: 1 })
    expect(truncatedTradesStrategy(mkRun([s]))).toBeUndefined()
  })
})

describe('esc', () => {
  it('转义 HTML 危险字符', () => {
    expect(esc('<a>&"')).toBe('&lt;a&gt;&amp;&quot;')
  })
})

describe('chartTooltipFormatter', () => {
  it('成交点显前3笔明细 + 等N笔; 卖出带盈亏; DB 串转义', () => {
    const out = chartTooltipFormatter([
      { axisValueLabel: '2024-01-02' },
      {
        marker: 'M',
        data: {
          trades: [
            mkTrade({ direction: 'BUY', symbol: '<x>', volume: 200, price: 9.5 }),
            mkTrade({ direction: 'SELL', volume: 100, price: 11, pnl: 5 }),
            mkTrade(),
            mkTrade(),
          ],
        },
      },
    ])
    expect(out).toContain('2024-01-02')
    expect(out).toContain('买入 &lt;x&gt; 200股@9.5')
    expect(out).toContain('卖出 000001.SZ 100股@11（+5.00）')
    expect(out).toContain('等4笔')
  })

  it('数值序列: 回撤带 %, 其余四舍五入', () => {
    const out = chartTooltipFormatter([
      { axisValueLabel: 'd1' },
      { marker: 'A', seriesName: 'dual_ma', value: 12345.6 },
      { marker: 'B', seriesName: '回撤 dual_ma', value: -5.2 },
    ])
    expect(out).toContain('dual_ma:')
    expect(out).toContain('回撤 dual_ma: -5.2%')
  })
})

describe('pct', () => {
  it('百分比两位小数', () => {
    expect(pct(0.1234)).toBe('12.34%')
    expect(pct(-0.05)).toBe('-5.00%')
  })
})
