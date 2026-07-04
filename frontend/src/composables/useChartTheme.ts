import { computed, type ComputedRef } from 'vue'

import { useThemeStore } from '@/stores/theme'

/* ECharts 主题权威(旧 charts.js chartTheme 的品牌化重做, 设计 §4.2):
 * 颜色全由 setOption 显式控制, 不用 ECharts 命名主题 — 主题切换即重渲染换肤。
 * A 股语义: 涨/买=红(up), 跌/卖=绿(down); 品牌橙为主序列色。 */

export interface ChartPalette {
  panelBg: string
  text: string
  dim: string
  split: string
  axis: string
  brand: string
  up: string
  down: string
  benchmark: string
  vol: string
  tipBg: string
  tipBorder: string
  tipText: string
  series: string[]
  overlay: string[]
  brandArea: [string, string]
}

const DARK: ChartPalette = {
  panelBg: '#1f1e1c',
  text: '#faf9f5',
  dim: '#9d9b92',
  split: 'rgba(250,249,245,.05)',
  axis: 'rgba(250,249,245,.14)',
  brand: '#d97757',
  up: '#e5735a',
  down: '#8ba36b',
  benchmark: '#9d9b92',
  vol: 'rgba(106,155,204,.28)',
  tipBg: 'rgba(31,30,28,.96)',
  tipBorder: '#3a3833',
  tipText: '#faf9f5',
  series: ['#d97757', '#6a9bcc', '#788c5d', '#c9a86a', '#a58ec4', '#5f9ea0'],
  overlay: ['#a58ec4', '#c9a86a', '#75736b'],
  brandArea: ['rgba(217,119,87,.30)', 'rgba(217,119,87,0)'],
}

const LIGHT: ChartPalette = {
  panelBg: '#ffffff',
  text: '#141413',
  dim: '#75736b',
  split: 'rgba(20,20,19,.055)',
  axis: 'rgba(20,20,19,.16)',
  brand: '#d97757',
  up: '#c0563c',
  down: '#6d8050',
  benchmark: '#b0aea5',
  tipBg: 'rgba(250,249,245,.97)',
  tipBorder: '#dcd9cd',
  tipText: '#141413',
  vol: 'rgba(106,155,204,.28)',
  series: ['#d97757', '#6a9bcc', '#788c5d', '#b98a3a', '#8a6fb0', '#4f8a8b'],
  overlay: ['#8a6fb0', '#b98a3a', '#9d9b92'],
  brandArea: ['rgba(217,119,87,.22)', 'rgba(217,119,87,0)'],
}

export function useChartTheme(): ComputedRef<ChartPalette> {
  const store = useThemeStore()
  return computed(() => (store.theme === 'dark' ? DARK : LIGHT))
}

/* 通用坐标轴/网格样式 */
export function axisStyle(t: ChartPalette) {
  return {
    axisLine: { lineStyle: { color: t.axis } },
    axisTick: { show: false },
    axisLabel: { color: t.dim, fontSize: 11 },
    splitLine: { lineStyle: { color: t.split } },
  }
}

/* 通用 tooltip 样式 (毛玻璃浮层) */
export function tooltipStyle(t: ChartPalette) {
  return {
    backgroundColor: t.tipBg,
    borderColor: t.tipBorder,
    borderWidth: 1,
    textStyle: { color: t.tipText, fontSize: 12 },
    extraCssText:
      'backdrop-filter: blur(6px); border-radius: 9px;' +
      ' box-shadow: 0 10px 30px rgba(0,0,0,.28); padding: 8px 11px;',
  }
}

/* 竖直渐变 (ECharts JSON LinearGradient) */
export function vGradient(c0: string, c1: string) {
  return {
    type: 'linear' as const,
    x: 0,
    y: 0,
    x2: 0,
    y2: 1,
    colorStops: [
      { offset: 0, color: c0 },
      { offset: 1, color: c1 },
    ],
  }
}
