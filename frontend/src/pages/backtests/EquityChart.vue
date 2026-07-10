<script setup lang="ts">
import { LineChart, ScatterChart } from 'echarts/charts'
import {
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'

import type { BacktestRun, BacktestStrategy } from '@/api/types'
import { type ChartPalette, tooltipStyle, useChartTheme, vGradient } from '@/composables/useChartTheme'

import {
  alignToAxis,
  chartTooltipFormatter,
  drawdown,
  firstStrategy,
  groupTradeMarkers,
  isDenseMarkers,
  MARKER_DOWN,
  MARKER_UP,
  markerSize,
  type OverlayLine,
  strategiesWithCurve,
  type TradeMarkerPoint,
  wan,
} from './chart-data'

use([
  LineChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  TitleComponent,
  LegendComponent,
  DataZoomComponent,
  AxisPointerComponent,
  CanvasRenderer,
])

/* 净值与回撤图 — 旧 backtests.js renderBtRun 的 setOption 部分对等:
 * 策略净值线(主策略品牌渐变面积)/基准灰虚线/叠加重定基虚线/买卖 ▲▼path 字形标记/
 * 回撤渐变子图; 配色全由 useChartTheme 提供, 主题切换即随 computed 重渲染换肤。
 * 纯计算(轴对齐/标记聚合/超额)已抽 chart-data.ts, 此处只做 option 装配。 */
const props = defineProps<{
  run: BacktestRun
  benchSeries: (number | null)[] | null
  overlayLines: OverlayLine[]
}>()

const palette = useChartTheme()

/* 图表替代文本(WCAG 1.1.1): 容器 role=img + 动态摘要, 供屏幕阅读器读到
 * run_id / 区间 / 曲线数 / 是否含基准·叠加, 而非把 canvas 当空图。 */
const ariaSummary = computed(() => {
  const run = props.run
  const first = firstStrategy(run)
  const dates = first?.equity_curve.dates ?? []
  if (!first || !dates.length) return `回测 ${run.run_id} 无净值曲线`
  const parts = [
    `回测 ${run.run_id} 净值与回撤图`,
    `区间 ${dates[0]} 至 ${dates[dates.length - 1]}`,
    `策略曲线 ${strategiesWithCurve(run).length} 条`,
  ]
  if (props.benchSeries) parts.push('含基准对照')
  if (props.overlayLines.length) parts.push(`叠加 ${props.overlayLines.length} 条`)
  return parts.join('，')
})

/* path 字形 buy/sell 散点(A股: 买红▲落线下方, 卖绿▼落线上方)
 * 标记日超阈值(高频截面策略)切密集模式: 恒 6px 小符号/细边/无阴影/收拢偏移,
 * 与稀疏轮次(如 dual_ma)的精致大标记两种形态各自可读 */
function tradeScatters(s: BacktestStrategy, axisIdx: Map<string, number>, t: ChartPalette) {
  const { BUY, SELL } = groupTradeMarkers(s, axisIdx)
  const dense = isDenseMarkers(BUY.length, SELL.length)
  const mk = (
    dir: 'BUY' | 'SELL',
    points: TradeMarkerPoint[],
    color: string,
    sym: string,
    offY: number,
  ) => ({
    name: `${dir === 'BUY' ? '买' : '卖'}·${s.strategy}`,
    type: 'scatter',
    xAxisIndex: 0,
    yAxisIndex: 0,
    symbol: sym,
    symbolOffset: [0, dense ? Math.sign(offY) * 6 : offY],
    z: 14,
    itemStyle: {
      color,
      borderColor: t.panelBg,
      borderWidth: dense ? 0.5 : 2,
      shadowBlur: dense ? 0 : 6,
      shadowColor: 'rgba(0,0,0,.4)',
    },
    symbolSize: (_: unknown, q: { data: TradeMarkerPoint }) =>
      markerSize(q.data.trades.length, dense),
    data: points,
  })
  const out: Record<string, unknown>[] = []
  // 买 红▲(t.up) 落线下方; 卖 绿▼(t.down) 落线上方
  if (BUY.length) out.push(mk('BUY', BUY, t.up, MARKER_UP, 11))
  if (SELL.length) out.push(mk('SELL', SELL, t.down, MARKER_DOWN, -11))
  return out
}

const option = computed(() => {
  const run = props.run
  const first = firstStrategy(run)
  const withCurve = strategiesWithCurve(run)
  const dates = first?.equity_curve.dates ?? []
  if (!first || !dates.length) return null

  const t = palette.value
  const axisIdx = new Map(dates.map((d, i) => [d, i]))
  const seriesColor = (si: number): string => t.series[si % t.series.length]

  const benchSeries = props.benchSeries
    ? [
        {
          name: '基准买入持有',
          type: 'line',
          data: props.benchSeries,
          smooth: 0.25,
          showSymbol: false,
          xAxisIndex: 0,
          yAxisIndex: 0,
          connectNulls: true,
          lineStyle: { width: 1.5, type: 'dashed', color: t.benchmark },
          itemStyle: { color: t.benchmark },
          z: 4,
        },
      ]
    : []

  const overlaySeries = props.overlayLines.map((ln) => {
    const color = t.overlay[ln.colorIdx % t.overlay.length]
    return {
      name: ln.name,
      type: 'line',
      data: ln.data,
      smooth: 0.25,
      showSymbol: false,
      xAxisIndex: 0,
      yAxisIndex: 0,
      connectNulls: true,
      lineStyle: { width: 1.2, type: 'dashed', opacity: 0.85, color },
      itemStyle: { color },
    }
  })

  return {
    backgroundColor: 'transparent',
    animation: false,
    aria: { enabled: true }, // ECharts 生成图元级替代描述, 与容器 role=img 互补
    textStyle: { color: t.text },
    color: t.series,
    title: {
      text: `净值与回撤 · ${run.run_id}`,
      left: 14,
      top: 10,
      textStyle: { fontSize: 13, fontWeight: 600, color: t.text },
    },
    tooltip: {
      trigger: 'axis',
      formatter: chartTooltipFormatter,
      ...tooltipStyle(t),
      axisPointer: { type: 'line', lineStyle: { color: t.axis, type: 'dashed' } },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    legend: {
      top: 9,
      right: 14,
      itemWidth: 16,
      itemHeight: 8,
      itemGap: 14,
      textStyle: { color: t.dim, fontSize: 11 },
    },
    // 回撤子图 19%→17%: 底部让出 slider dataZoom 一条, 子图 x 轴日期标签不被压住
    grid: [
      { left: 66, right: 26, top: 46, height: '50%' },
      { left: 66, right: 26, top: '72%', height: '17%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0,
        boundaryGap: false,
        axisLine: { lineStyle: { color: t.axis } },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        boundaryGap: false,
        axisLine: { lineStyle: { color: t.axis } },
        axisTick: { show: false },
        axisLabel: { color: t.dim, fontSize: 11 },
        splitLine: { show: false },
      },
    ],
    yAxis: [
      {
        type: 'value',
        scale: true,
        gridIndex: 0,
        axisLine: { lineStyle: { color: t.axis } },
        splitLine: { lineStyle: { color: t.split } },
        axisLabel: { color: t.dim, fontSize: 11, formatter: wan },
      },
      {
        type: 'value',
        gridIndex: 1,
        max: 0,
        axisLine: { lineStyle: { color: t.axis } },
        splitLine: { lineStyle: { color: t.split } },
        axisLabel: { color: t.dim, fontSize: 11, formatter: '{value}%' },
      },
    ],
    // inside 滚轮缩放不可见 → 加底部 slider 让缩放能力可发现, 样式对齐 K 线图
    // (explorer/chart-options.ts): 品牌色柔和填充/透明边框, 两图缩放形态一致
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1] },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        height: 14,
        bottom: 6,
        borderColor: 'transparent',
        fillerColor: `${t.brand}22`,
        handleStyle: { color: t.brand },
        textStyle: { color: t.dim },
      },
    ],
    series: [
      // 策略净值: 平滑; 主策略品牌渐变面积, 其余仅描线避免叠加糊面
      ...withCurve.map((s, si) => ({
        name: s.strategy,
        type: 'line',
        smooth: 0.25,
        data: alignToAxis(dates, s, first, s.equity_curve.values ?? []),
        showSymbol: false,
        xAxisIndex: 0,
        yAxisIndex: 0,
        connectNulls: true,
        z: 6 - si,
        lineStyle: { color: seriesColor(si), width: si === 0 ? 2.4 : 1.6 },
        itemStyle: { color: seriesColor(si) },
        ...(si === 0
          ? { areaStyle: { color: vGradient(t.brandArea[0], t.brandArea[1]) } }
          : {}),
      })),
      ...benchSeries,
      ...overlaySeries,
      ...withCurve.flatMap((s) => tradeScatters(s, axisIdx, t)),
      // 回撤子图: 各策略同轴联动, 渐变面积
      ...withCurve.map((s, si) => ({
        name: `回撤 ${s.strategy}`,
        type: 'line',
        smooth: 0.25,
        data: alignToAxis(dates, s, first, drawdown(s.equity_curve.values ?? [])),
        showSymbol: false,
        xAxisIndex: 1,
        yAxisIndex: 1,
        connectNulls: true,
        areaStyle: { color: vGradient(`${seriesColor(si)}33`, `${seriesColor(si)}00`) },
        lineStyle: { width: 1, color: seriesColor(si) },
        itemStyle: { color: seriesColor(si) },
      })),
    ],
  }
})
</script>

<template>
  <div class="chart-card card" data-testid="bt-chart" role="img" :aria-label="ariaSummary">
    <VChart v-if="option" :option="option" autoresize class="chart" />
    <p v-else class="t-muted empty">该轮次无净值曲线可绘</p>
  </div>
</template>

<style scoped>
.chart-card {
  padding: 8px;
}

.chart {
  height: 460px;
  width: 100%;
}

.empty {
  padding: 60px 0;
  text-align: center;
}
</style>
