import { describe, expect, it } from 'vitest'

import type { BarsData, FeatureData } from '@/api/types'
import type { ChartPalette } from '@/composables/useChartTheme'

import {
  alignByDate,
  buildFeaturePanelOption,
  buildKlineOption,
  buildUnionDates,
  DEFAULT_FEATURES,
  featureLabel,
  FEATURE_META,
  featureLineDash,
  type SymbolMeta,
  symbolColor,
} from '../chart-options'

/* 行情页图表 option 纯逻辑 — 单标的分支零回归(逐字断言关键字段), 多标的分支断言日期对齐/基准/配色/虚实线 */

function mkPalette(): ChartPalette {
  return {
    panelBg: '#fff',
    text: '#111',
    dim: '#888',
    split: '#eee',
    axis: '#ccc',
    brand: '#f60',
    up: '#e33',
    down: '#3a3',
    benchmark: '#999',
    vol: '#69c',
    tipBg: '#fff',
    tipBorder: '#ddd',
    tipText: '#111',
    series: ['c0', 'c1', 'c2', 'c3', 'c4', 'c5'],
    overlay: ['o0', 'o1', 'o2'],
    brandArea: ['rgba(0,0,0,.1)', 'rgba(0,0,0,0)'],
  }
}

function mkBars(o: Partial<BarsData> = {}): BarsData {
  return {
    dates: ['2024-01-01', '2024-01-02', '2024-01-03'],
    ohlc: [
      [10, 10, 9, 11],
      [10, 11, 9, 12],
      [11, 12, 10, 13],
    ],
    volume: [100, 110, 120],
    ...o,
  }
}

function mkFeatures(o: Partial<FeatureData> = {}): FeatureData {
  return {
    dates: ['2024-01-01', '2024-01-02', '2024-01-03'],
    series: { return_20d: [0.1, 0.2, 0.3], volatility_20d: [0.01, 0.02, 0.03] },
    ...o,
  }
}

describe('FEATURE_META / featureLabel / DEFAULT_FEATURES', () => {
  it('迁移自 Explorer.vue, 中文标签不变(抽样)', () => {
    expect(FEATURE_META).toHaveLength(13)
    expect(featureLabel('return_20d')).toBe('20日收益')
    expect(featureLabel('rsi_14')).toBe('RSI(14)')
    expect(featureLabel('obv_slope_20d')).toBe('OBV斜率')
  })

  it('未知特征名回退原名', () => {
    expect(featureLabel('unknown_x')).toBe('unknown_x')
  })

  it('默认勾选与改动前一致', () => {
    expect(DEFAULT_FEATURES).toEqual(['return_20d', 'volatility_20d'])
  })
})

describe('symbolColor', () => {
  const palette = mkPalette()

  it('下标在 series 长度内直接取值', () => {
    expect(symbolColor(palette, 0)).toBe('c0')
    expect(symbolColor(palette, 5)).toBe('c5')
  })

  it('下标超出 series 长度时取模循环', () => {
    expect(symbolColor(palette, 6)).toBe('c0')
    expect(symbolColor(palette, 7)).toBe('c1')
    expect(symbolColor(palette, 13)).toBe('c1') // 13 % 6 = 1
  })
})

describe('buildUnionDates', () => {
  it('并集去重排序', () => {
    expect(buildUnionDates([['d2', 'd1'], ['d3', 'd1']])).toEqual(['d1', 'd2', 'd3'])
  })

  it('空输入返回空数组', () => {
    expect(buildUnionDates([])).toEqual([])
  })
})

describe('alignByDate', () => {
  it('按日期查值, 取不到为 null(不按下标位置错位对齐)', () => {
    const union = ['d1', 'd2', 'd3']
    expect(alignByDate(union, ['d1', 'd3'], [1, 3])).toEqual([1, null, 3])
  })

  it('own 序列本身含 null 时原样保留', () => {
    expect(alignByDate(['d1', 'd2'], ['d1', 'd2'], [null, 5])).toEqual([null, 5])
  })
})

describe('featureLineDash', () => {
  it('下标取自 FEATURE_META 声明顺序, solid/dashed/dotted 循环', () => {
    expect(featureLineDash('return_5d')).toBe('solid') // idx 0
    expect(featureLineDash('return_20d')).toBe('dashed') // idx 1
    expect(featureLineDash('return_60d')).toBe('dotted') // idx 2
    expect(featureLineDash('volatility_20d')).toBe('solid') // idx 3 -> %3=0
  })

  it('未知特征名回退 idx 0 → solid', () => {
    expect(featureLineDash('unknown_feature')).toBe('solid')
  })
})

describe('buildKlineOption', () => {
  const palette = mkPalette()

  it('0 个标的返回 null', () => {
    expect(buildKlineOption(palette, [], new Map())).toBeNull()
  })

  it('1 个标的但无数据条目(从未成功加载) → null', () => {
    const symbols: SymbolMeta[] = [{ symbol: '000001.SZ', color: 'c0' }]
    expect(buildKlineOption(palette, symbols, new Map())).toBeNull()
  })

  it('1 个标的逐字复刻蜡烛+成交量双 pane 结构', () => {
    const bars = mkBars()
    const symbols: SymbolMeta[] = [{ symbol: '000001.SZ', color: 'c0' }]
    const option = buildKlineOption(palette, symbols, new Map([['000001.SZ', bars]]))
    expect(option).not.toBeNull()
    const o = option as Record<string, any>
    expect(o.title.text).toBe('000001.SZ 前复权日线')
    expect(o.series).toHaveLength(2)
    expect(o.series[0]).toMatchObject({
      name: '000001.SZ',
      type: 'candlestick',
      data: bars.ohlc,
    })
    expect(o.series[0].itemStyle).toEqual({
      color: palette.up,
      color0: palette.down,
      borderColor: palette.up,
      borderColor0: palette.down,
    })
    expect(o.series[1]).toMatchObject({ name: '成交量', type: 'bar', data: bars.volume })
    expect(o.xAxis[0].data).toEqual(bars.dates)
    expect(o.xAxis).toHaveLength(2)
    expect(o.grid).toHaveLength(2)
  })

  it('2 个标的切换为涨跌幅对比折线图(其中一个标的少一天, 验证基准与对齐不错位)', () => {
    const barsA = mkBars({
      dates: ['2024-01-01', '2024-01-02', '2024-01-03'],
      ohlc: [
        [10, 10, 9, 11],
        [10, 11, 9, 12],
        [11, 13.333, 10, 14],
      ],
    })
    // B 缺 01-01(如次新股未上市/停牌), base 应取 B 自己序列里第一个非 null 收盘价(20), 不是 A 的
    const barsB = mkBars({
      dates: ['2024-01-02', '2024-01-03'],
      ohlc: [
        [20, 20, 19, 21],
        [20, 25, 19, 26],
      ],
      volume: [50, 60],
    })
    const symbols: SymbolMeta[] = [
      { symbol: 'A.SZ', color: 'colorA' },
      { symbol: 'B.SZ', color: 'colorB' },
    ]
    const bars = new Map([
      ['A.SZ', barsA],
      ['B.SZ', barsB],
    ])
    const option = buildKlineOption(palette, symbols, bars) as Record<string, any>
    expect(option).not.toBeNull()
    expect(option.xAxis.data).toEqual(['2024-01-01', '2024-01-02', '2024-01-03'])
    expect(option.series).toHaveLength(2)

    const seriesA = option.series.find((s: any) => s.name === 'A.SZ')
    // A base=10: day1 0%, day2 (11/10-1)*100=10%, day3 (13.333/10-1)*100=33.33 -> round 1位=33.3
    expect(seriesA.data).toEqual([0, 10, 33.3])
    expect(seriesA.lineStyle.color).toBe('colorA')
    expect(seriesA.itemStyle.color).toBe('colorA')

    const seriesB = option.series.find((s: any) => s.name === 'B.SZ')
    // B base=20(自身首个非null, 与 A 无关): day1 无数据(不借用 A 的日期错位对上)=null, day2 0%, day3 25%
    expect(seriesB.data).toEqual([null, 0, 25])
    expect(seriesB.lineStyle.color).toBe('colorB')

    expect(option.title.text).toBe('多标的涨跌幅对比 · 2024-01-01～2024-01-03')
    // 不画成交量: 不应有第二个 grid/xAxis pane
    expect(Array.isArray(option.xAxis)).toBe(false)
  })

  it('全窗口无有效收盘价的标的仍列入图例, 但整条线为 null', () => {
    const barsA = mkBars()
    const barsC: BarsData = {
      dates: ['2024-01-02'],
      // 运行时可能是 null(后端 _nn 把 NaN 转 None), 类型声明层面用 cast 贴合真实荷载
      ohlc: [[10, null, 9, 11]] as unknown as BarsData['ohlc'],
      volume: [50],
    }
    const symbols: SymbolMeta[] = [
      { symbol: 'A.SZ', color: 'colorA' },
      { symbol: 'C.SZ', color: 'colorC' },
    ]
    const bars = new Map([
      ['A.SZ', barsA],
      ['C.SZ', barsC],
    ])
    const option = buildKlineOption(palette, symbols, bars) as Record<string, any>
    const seriesC = option.series.find((s: any) => s.name === 'C.SZ')
    expect(seriesC).toBeDefined()
    expect(seriesC.data).toEqual([null, null, null])
  })

  it('标的完全无数据条目 → 不进入图例(与"有条目但全 null"的标的区分开)', () => {
    const barsA = mkBars()
    const symbols: SymbolMeta[] = [
      { symbol: 'A.SZ', color: 'colorA' },
      { symbol: 'D.SZ', color: 'colorD' },
    ]
    const bars = new Map([['A.SZ', barsA]]) // D.SZ 无条目
    const option = buildKlineOption(palette, symbols, bars) as Record<string, any>
    expect(option.series.some((s: any) => s.name === 'D.SZ')).toBe(false)
    expect(option.series).toHaveLength(1)
  })

  it('2+ 标的但全部无数据条目 → null', () => {
    const symbols: SymbolMeta[] = [
      { symbol: 'A.SZ', color: 'colorA' },
      { symbol: 'B.SZ', color: 'colorB' },
    ]
    expect(buildKlineOption(palette, symbols, new Map())).toBeNull()
  })
})

describe('buildFeaturePanelOption', () => {
  const palette = mkPalette()

  it('pickedFeatures 为空 → null', () => {
    const symbols: SymbolMeta[] = [{ symbol: '000001.SZ', color: 'c0' }]
    const cache = new Map([['000001.SZ', mkFeatures()]])
    expect(buildFeaturePanelOption(palette, symbols, cache, [])).toBeNull()
  })

  it('symbols 为空 → null', () => {
    expect(buildFeaturePanelOption(palette, [], new Map(), ['return_20d'])).toBeNull()
  })

  it('1 个标的但无数据条目 → null', () => {
    const symbols: SymbolMeta[] = [{ symbol: '000001.SZ', color: 'c0' }]
    expect(buildFeaturePanelOption(palette, symbols, new Map(), ['return_20d'])).toBeNull()
  })

  it('1 个标的沿用现状命名(不带标的前缀), 颜色走 palette.series 全局循环', () => {
    const data = mkFeatures()
    const symbols: SymbolMeta[] = [{ symbol: '000001.SZ', color: 'c0' }]
    const option = buildFeaturePanelOption(
      palette,
      symbols,
      new Map([['000001.SZ', data]]),
      ['return_20d', 'volatility_20d'],
    ) as Record<string, any>
    expect(option).not.toBeNull()
    expect(option.title.text).toBe('000001.SZ 截面特征（T-1 信息口径）')
    expect(option.color).toEqual(palette.series)
    expect(option.series).toHaveLength(2)
    expect(option.series[0]).toMatchObject({ name: '20日收益', type: 'line', data: data.series.return_20d })
    expect(option.series[1]).toMatchObject({ name: '20日波动', type: 'line', data: data.series.volatility_20d })
    // 现状不显式指定单系列颜色(交由顶层 color 数组循环取色)
    expect(option.series[0].itemStyle).toBeUndefined()
    expect(option.series[0].lineStyle).toEqual({ width: 1.6 })
    expect(option.xAxis.data).toEqual(data.dates)
  })

  it('2+ 标的按 symbols×pickedFeatures 笛卡尔积命名/配色/虚实线, 日期对齐走并集', () => {
    const dataA = mkFeatures({
      dates: ['2024-01-01', '2024-01-02', '2024-01-03'],
      series: { return_20d: [1, 2, 3], volatility_20d: [0.1, 0.2, 0.3] },
    })
    // B 缺 01-01
    const dataB = mkFeatures({
      dates: ['2024-01-02', '2024-01-03'],
      series: { return_20d: [20, 30], volatility_20d: [0.02, 0.03] },
    })
    const symbols: SymbolMeta[] = [
      { symbol: 'A.SZ', color: 'colorA' },
      { symbol: 'B.SZ', color: 'colorB' },
    ]
    const cache = new Map([
      ['A.SZ', dataA],
      ['B.SZ', dataB],
    ])
    const option = buildFeaturePanelOption(palette, symbols, cache, ['return_20d', 'volatility_20d']) as Record<
      string,
      any
    >
    expect(option.xAxis.data).toEqual(['2024-01-01', '2024-01-02', '2024-01-03'])
    expect(option.series).toHaveLength(4)

    const nameOf = (sym: string, feat: string) => `${sym} · ${featureLabel(feat)}`
    const aReturn = option.series.find((s: any) => s.name === nameOf('A.SZ', 'return_20d'))
    expect(aReturn.data).toEqual([1, 2, 3])
    expect(aReturn.lineStyle.color).toBe('colorA')
    expect(aReturn.itemStyle.color).toBe('colorA')
    expect(aReturn.lineStyle.type).toBe(featureLineDash('return_20d'))

    const aVol = option.series.find((s: any) => s.name === nameOf('A.SZ', 'volatility_20d'))
    expect(aVol.lineStyle.type).toBe(featureLineDash('volatility_20d'))
    expect(aVol.lineStyle.type).not.toBe(aReturn.lineStyle.type) // 同标的不同特征虚实线不同

    const bReturn = option.series.find((s: any) => s.name === nameOf('B.SZ', 'return_20d'))
    // B 缺 01-01 → 对齐并集轴后首日为 null, 不借用 A 的日期错位对上
    expect(bReturn.data).toEqual([null, 20, 30])
    expect(bReturn.lineStyle.color).toBe('colorB')
    // 同一特征跨标的虚实线一致(取自 FEATURE_META 声明顺序, 不受标的影响)
    expect(bReturn.lineStyle.type).toBe(aReturn.lineStyle.type)
  })

  it('标的完全无特征数据条目 → 不进入笛卡尔积', () => {
    const dataA = mkFeatures()
    const symbols: SymbolMeta[] = [
      { symbol: 'A.SZ', color: 'colorA' },
      { symbol: 'D.SZ', color: 'colorD' },
    ]
    const cache = new Map([['A.SZ', dataA]])
    const option = buildFeaturePanelOption(palette, symbols, cache, ['return_20d']) as Record<string, any>
    expect(option.series).toHaveLength(1)
    expect(option.series.some((s: any) => s.name.startsWith('D.SZ'))).toBe(false)
  })
})
