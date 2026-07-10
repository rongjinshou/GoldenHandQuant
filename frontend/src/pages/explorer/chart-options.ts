/* 行情页图表 option 纯函数 — 多标的叠加对比改造(设计 docs/feat/0705-explorer-multi-symbol):
 * FEATURE_META/featureLabel/DEFAULT_FEATURES 从 Explorer.vue 原样迁移(标签文案不改一字);
 * buildKlineOption/buildFeaturePanelOption 的"1 个标的"分支逐字复刻改动前 klineOption/featureOption
 * computed 的输出结构(零回归); "2+ 个标的"分支改单 pane 对比图(涨跌幅重定基 / 特征笛卡尔积),
 * 日期对齐一律走 buildUnionDates+alignByDate 共享工具, 不允许两处各写一份。
 * 无 Vue/ECharts 渲染依赖, Vitest 直测。 */

import type { BarsData, FeatureData } from '@/api/types'
import { axisStyle, type ChartPalette, tooltipStyle } from '@/composables/useChartTheme'

export const DEFAULT_FEATURES = ['return_20d', 'volatility_20d']

/* 特征中文标签 + glossary 词条(term=特征名) — 勾选框不再裸英文变量名 */
export const FEATURE_META: { name: string; label: string }[] = [
  { name: 'return_5d', label: '5日收益' },
  { name: 'return_20d', label: '20日收益' },
  { name: 'return_60d', label: '60日收益' },
  { name: 'volatility_20d', label: '20日波动' },
  { name: 'volatility_60d', label: '60日波动' },
  { name: 'turnover_rate', label: '换手率' },
  { name: 'avg_turnover_20d', label: '20日均换手' },
  { name: 'rsi_14', label: 'RSI(14)' },
  { name: 'macd', label: 'MACD' },
  { name: 'ma_20', label: '20日均线' },
  { name: 'skewness_20d', label: '20日偏度' },
  { name: 'illiquidity_20d', label: '非流动性' },
  { name: 'obv_slope_20d', label: 'OBV斜率' },
]

export function featureLabel(name: string): string {
  return FEATURE_META.find((f) => f.name === name)?.label ?? name
}

/* 特征勾选分组（Miller 分块，易用性迭代任务 2）— 勾选区按语义分组展示, 组内顺序即展示顺序。
 * 单一真相源仍是 FEATURE_META（中文标签/虚实线次序都从它来）: 这里只声明"哪些名字归哪组",
 * items 的 label 经 featureLabel 查表派生, 不双写文案。约束「分组并集 = FEATURE_META 全集,
 * 无遗漏无重复」由 chart-options.spec.ts 断言防漂移 —— 新增特征忘记归组会在测试期炸出来。 */
export interface FeatureGroup {
  label: string
  items: { name: string; label: string }[]
}

const FEATURE_GROUP_NAMES: { label: string; names: string[] }[] = [
  { label: '收益', names: ['return_5d', 'return_20d', 'return_60d'] },
  { label: '波动', names: ['volatility_20d', 'volatility_60d', 'skewness_20d'] },
  { label: '量能', names: ['turnover_rate', 'avg_turnover_20d', 'illiquidity_20d', 'obv_slope_20d'] },
  { label: '技术', names: ['rsi_14', 'macd', 'ma_20'] },
]

export const FEATURE_GROUPS: FeatureGroup[] = FEATURE_GROUP_NAMES.map((g) => ({
  label: g.label,
  items: g.names.map((n) => ({ name: n, label: featureLabel(n) })),
}))

/* 标的元信息(供多标的叠加图使用): color 由调用方按"当前标的集合"(loadedSymbols)下标算好
 * (symbolColor)后传入 — 本文件的 build* 函数不再自行按下标反查颜色, 避免和调用方对
 * "当前标的是哪几个/顺序如何"产生第二套口径。 */
export interface SymbolMeta {
  symbol: string
  color: string
}

/* ECharts option 是深度嵌套的动态结构, 全仓库现状不引入严格 EChartsOption 类型
 * (eslint 配置里 @typescript-eslint/no-explicit-any 对图表 option 只降级为 warn 就是同一考量);
 * 这里给一个宽松具名别名, 让导出函数的签名可读、可断言。 */
export type ChartOption = Record<string, unknown>

/* 标的配色: 下标 = 该标的在"当前标的集合"(调用方决定是哪个数组、什么顺序)中的位置,
 * 取模循环 6 色板(超过 6 只标的会撞色, 由调用方在 UI 侧做软提示, 这里不管)。 */
export function symbolColor(palette: ChartPalette, index: number): string {
  return palette.series[index % palette.series.length]
}

/* 特征虚实线: 下标固定取自 FEATURE_META 声明顺序(不受呈现框内勾选先后顺序影响) ——
 * 同一特征无论在哪个呈现框、哪个标的下, 虚实线样式恒定一致, 与标的配色的跨图一致性对称。 */
export const DASH_STYLES = ['solid', 'dashed', 'dotted'] as const

export function featureLineDash(name: string): (typeof DASH_STYLES)[number] {
  const idx = FEATURE_META.findIndex((f) => f.name === name)
  return DASH_STYLES[(idx < 0 ? 0 : idx) % DASH_STYLES.length]
}

/* 全部标的日期的并集, 排序去重 — 多标的对比图的共享 x 轴 */
export function buildUnionDates(perSymbolDates: string[][]): string[] {
  const set = new Set<string>()
  for (const dates of perSymbolDates) for (const d of dates) set.add(d)
  return [...set].sort()
}

/* 把某标的"自身日期轴"上的值对齐到共享的并集轴上; 取不到的日期给 null ——
 * 逐日期查表, 不按下标位置 zip, 不能借用其他标的的日期把点错位对上。 */
export function alignByDate<T>(unionDates: string[], ownDates: string[], ownValues: T[]): (T | null)[] {
  const map = new Map(ownDates.map((d, i) => [d, ownValues[i]]))
  return unionDates.map((d) => map.get(d) ?? null)
}

function round1(v: number): number {
  return Math.round(v * 10) / 10
}

/* 涨跌幅%序列: 基准 = 该标的自身序列里第一个非 null 收盘价; 全窗口无有效收盘价 → 整条 null。
 * BarsData.ohlc 声明类型是 number 四元组, 但后端 _nn() 会把 NaN 转成 None —
 * 实际荷载里收盘价确有可能是 null, 这里按运行时真实形状 cast 处理(而非信了动无脑的静态类型)。 */
function pctChangeSeries(bars: BarsData): (number | null)[] {
  const closes = bars.ohlc.map((row) => row[1] as number | null)
  const baseIdx = closes.findIndex((c) => c !== null)
  if (baseIdx === -1) return closes.map(() => null)
  const base = closes[baseIdx] as number
  return closes.map((c) => (c === null ? null : round1((c / base - 1) * 100)))
}

/* K 线区: 0 个标的 → null; 1 个标的 → 逐字复刻改动前 klineOption(蜡烛+成交量双 pane, 零回归);
 * 2+ 个标的 → 换成单 pane"涨跌幅对比"折线图, 不画成交量。 */
export function buildKlineOption(
  palette: ChartPalette,
  symbols: SymbolMeta[],
  barsBySymbol: Map<string, BarsData>,
): ChartOption | null {
  if (symbols.length === 0) return null
  const t = palette

  if (symbols.length === 1) {
    const meta = symbols[0]
    const data = barsBySymbol.get(meta.symbol)
    if (!data) return null
    return {
      backgroundColor: 'transparent',
      animation: false,
      aria: { enabled: true }, // 无障碍(设计 §8 S5): 容器 role=img 之外再让 ECharts 生成内部描述; 需 use(AriaComponent)
      textStyle: { color: t.text },
      title: {
        text: `${meta.symbol} 前复权日线`,
        left: 8,
        top: 10,
        textStyle: { fontSize: 13, fontWeight: 600, color: t.text },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', lineStyle: { color: t.axis } },
        ...tooltipStyle(t),
      },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      grid: [
        { left: 58, right: 22, top: 46, height: '54%' },
        { left: 58, right: 22, top: '74%', height: '17%' },
      ],
      xAxis: [
        {
          type: 'category',
          data: data.dates,
          gridIndex: 0,
          ...axisStyle(t),
          splitLine: { show: false },
        },
        {
          type: 'category',
          data: data.dates,
          gridIndex: 1,
          ...axisStyle(t),
          axisLabel: { show: false },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        { scale: true, gridIndex: 0, ...axisStyle(t) },
        { gridIndex: 1, ...axisStyle(t), axisLabel: { show: false }, splitLine: { show: false } },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1] },
        {
          type: 'slider',
          xAxisIndex: [0, 1],
          height: 16,
          bottom: 8,
          borderColor: 'transparent',
          fillerColor: `${t.brand}22`,
          handleStyle: { color: t.brand },
          textStyle: { color: t.dim },
        },
      ],
      series: [
        {
          name: meta.symbol,
          type: 'candlestick',
          data: data.ohlc,
          // A 股: 涨红跌绿
          itemStyle: { color: t.up, color0: t.down, borderColor: t.up, borderColor0: t.down },
        },
        {
          name: '成交量',
          type: 'bar',
          data: data.volume,
          xAxisIndex: 1,
          yAxisIndex: 1,
          itemStyle: { color: t.vol },
        },
      ],
    }
  }

  // 2+ 标的: 涨跌幅对比折线图(单 pane, 不画成交量)
  const present = symbols.filter((s) => barsBySymbol.has(s.symbol))
  if (present.length === 0) return null
  const unionDates = buildUnionDates(present.map((s) => barsBySymbol.get(s.symbol)!.dates))

  const series = present.map((meta) => {
    const bars = barsBySymbol.get(meta.symbol)!
    return {
      name: meta.symbol,
      type: 'line',
      data: alignByDate(unionDates, bars.dates, pctChangeSeries(bars)),
      showSymbol: false,
      connectNulls: false,
      lineStyle: { color: meta.color, width: 1.6 },
      itemStyle: { color: meta.color },
    }
  })

  return {
    backgroundColor: 'transparent',
    animation: false,
    aria: { enabled: true }, // 无障碍(设计 §8 S5): 多标的分支同启用 ECharts 内部描述; 需 use(AriaComponent)
    textStyle: { color: t.text },
    title: {
      text: `多标的涨跌幅对比 · ${unionDates[0]}～${unionDates[unionDates.length - 1]}`,
      subtext: '以各标的区间内首个可用收盘价为基准 0%',
      left: 8,
      top: 10,
      textStyle: { fontSize: 13, fontWeight: 600, color: t.text },
      subtextStyle: { fontSize: 11, color: t.dim },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: t.axis } },
      ...tooltipStyle(t),
      valueFormatter: (v: unknown): string => {
        if (v === null || v === undefined) return '无数据'
        const n = v as number
        return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
      },
    },
    legend: {
      top: 9,
      right: 14,
      itemWidth: 16,
      itemHeight: 8,
      textStyle: { color: t.dim, fontSize: 11 },
    },
    grid: { left: 58, right: 22, top: 56, bottom: 40 },
    xAxis: {
      type: 'category',
      data: unionDates,
      boundaryGap: false,
      ...axisStyle(t),
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { lineStyle: { color: t.axis } },
      axisTick: { show: false },
      axisLabel: { color: t.dim, fontSize: 11, formatter: '{value}%' },
      splitLine: { lineStyle: { color: t.split } },
    },
    dataZoom: [{ type: 'inside' }],
    series,
  }
}

/* 特征呈现框: pickedFeatures 为空或 symbols 为空 → null;
 * 1 个标的 → 逐字复刻改动前 featureOption(系列名不带标的前缀, 颜色走 palette.series 全局循环, 零回归);
 * 2+ 个标的 → symbols×pickedFeatures 笛卡尔积, 系列名带标的前缀, 颜色=该标的 color
 * (与 K 线对比图同一套映射), 同一标的下不同特征按 solid/dashed/dotted 循环区分。 */
export function buildFeaturePanelOption(
  palette: ChartPalette,
  symbols: SymbolMeta[],
  featuresBySymbol: Map<string, FeatureData>,
  pickedFeatures: string[],
): ChartOption | null {
  if (symbols.length === 0 || pickedFeatures.length === 0) return null
  const t = palette

  if (symbols.length === 1) {
    const meta = symbols[0]
    const data = featuresBySymbol.get(meta.symbol)
    if (!data) return null
    return {
      backgroundColor: 'transparent',
      animation: false,
      aria: { enabled: true }, // 无障碍(设计 §8 S5): 容器 role=img 之外再让 ECharts 生成内部描述; 需 use(AriaComponent)
      textStyle: { color: t.text },
      color: t.series,
      title: {
        text: `${meta.symbol} 截面特征（T-1 信息口径）`,
        left: 8,
        top: 10,
        textStyle: { fontSize: 13, fontWeight: 600, color: t.text },
      },
      tooltip: {
        trigger: 'axis',
        ...tooltipStyle(t),
        axisPointer: { type: 'line', lineStyle: { color: t.axis, type: 'dashed' } },
      },
      legend: {
        top: 9,
        right: 14,
        itemWidth: 16,
        itemHeight: 8,
        textStyle: { color: t.dim, fontSize: 11 },
      },
      grid: { left: 58, right: 22, top: 46, bottom: 40 },
      xAxis: {
        type: 'category',
        data: data.dates,
        boundaryGap: false,
        ...axisStyle(t),
        splitLine: { show: false },
      },
      yAxis: { type: 'value', scale: true, ...axisStyle(t) },
      dataZoom: [{ type: 'inside' }],
      series: pickedFeatures.map((n) => ({
        name: featureLabel(n), // 图例/悬浮提示用中文标签
        type: 'line',
        data: data.series[n],
        smooth: 0.2,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.6 },
      })),
    }
  }

  // 2+ 标的: symbols × pickedFeatures 笛卡尔积
  const present = symbols.filter((s) => featuresBySymbol.has(s.symbol))
  if (present.length === 0) return null
  const unionDates = buildUnionDates(present.map((s) => featuresBySymbol.get(s.symbol)!.dates))

  const series = present.flatMap((meta) => {
    const data = featuresBySymbol.get(meta.symbol)!
    return pickedFeatures.map((n) => ({
      name: `${meta.symbol} · ${featureLabel(n)}`,
      type: 'line',
      data: alignByDate(unionDates, data.dates, data.series[n] ?? []),
      smooth: 0.2,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.6, color: meta.color, type: featureLineDash(n) },
      itemStyle: { color: meta.color },
    }))
  })

  return {
    backgroundColor: 'transparent',
    animation: false,
    aria: { enabled: true }, // 无障碍(设计 §8 S5): 多标的分支同启用 ECharts 内部描述; 需 use(AriaComponent)
    textStyle: { color: t.text },
    title: {
      text: '多标的截面特征对比',
      left: 8,
      top: 10,
      textStyle: { fontSize: 13, fontWeight: 600, color: t.text },
    },
    tooltip: {
      trigger: 'axis',
      ...tooltipStyle(t),
      axisPointer: { type: 'line', lineStyle: { color: t.axis, type: 'dashed' } },
    },
    legend: {
      top: 9,
      right: 14,
      itemWidth: 16,
      itemHeight: 8,
      textStyle: { color: t.dim, fontSize: 11 },
    },
    grid: { left: 58, right: 22, top: 46, bottom: 40 },
    xAxis: {
      type: 'category',
      data: unionDates,
      boundaryGap: false,
      ...axisStyle(t),
      splitLine: { show: false },
    },
    yAxis: { type: 'value', scale: true, ...axisStyle(t) },
    dataZoom: [{ type: 'inside' }],
    series,
  }
}

/* 图表容器 role=img 的动态 aria-label(设计 §8 S5) — 屏幕阅读器一句话摘要:
 * 标的清单 + 图型 + 固定近一年窗口。纯函数, 与 build*Option 分支口径一致(单/多标的)。 */
export function buildKlineAriaLabel(symbols: SymbolMeta[]): string {
  if (symbols.length === 0) return '个股 K 线图，暂无标的'
  if (symbols.length === 1) {
    return `个股 K 线图：${symbols[0].symbol}，前复权日线含成交量，近一年窗口`
  }
  const names = symbols.map((s) => s.symbol).join('、')
  return `多标的涨跌幅对比图：${names}，近一年窗口`
}

export function buildFeatureAriaLabel(symbols: SymbolMeta[], features: string[]): string {
  if (symbols.length === 0 || features.length === 0) return '截面特征图，暂无数据'
  const names = symbols.map((s) => s.symbol).join('、')
  const feats = features.map((f) => featureLabel(f)).join('、')
  return `截面特征图：${names}，特征 ${feats}，近一年窗口`
}
