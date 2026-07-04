<script setup lang="ts">
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts'
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
import { NButton, NCheckbox, NDatePicker, NInput } from 'naive-ui'
import { computed, ref, shallowRef, watch } from 'vue'
import VChart from 'vue-echarts'

import { fetchJSON } from '@/api/fetch'
import type { BarsData, FeatureData, SymbolHit } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import { axisStyle, tooltipStyle, useChartTheme } from '@/composables/useChartTheme'

use([
  CandlestickChart,
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  TitleComponent,
  LegendComponent,
  DataZoomComponent,
  AxisPointerComponent,
  CanvasRenderer,
])

/* 个股查看页 — 旧 pages/explorer.js 对等:
 * 标的联想(200ms 防抖, 失败静默)/日期区间/加载=K线+特征并行/13特征选择即重载/主题重渲染。 */

const DEFAULT_FEATURES = ['return_20d', 'volatility_20d']
const FEATURE_CHOICES = [
  'return_5d', 'return_20d', 'return_60d', 'volatility_20d', 'volatility_60d',
  'turnover_rate', 'avg_turnover_20d', 'rsi_14', 'macd', 'ma_20',
  'skewness_20d', 'illiquidity_20d', 'obv_slope_20d',
]

const palette = useChartTheme()
const error = ref('')

const symbolInput = ref('')
const startDate = ref<string | null>(null)
const endDate = ref<string | null>(null)
const pickedFeatures = ref<string[]>([...DEFAULT_FEATURES])
const suggestions = ref<SymbolHit[]>([])

const lastKline = shallowRef<{ symbol: string; data: BarsData } | null>(null)
const lastFeature = shallowRef<{ symbol: string; names: string[]; data: FeatureData } | null>(null)

function pickedSymbol(): string {
  return (symbolInput.value || '').split(/\s/)[0].trim()
}

/* 联想: 200ms 防抖, 失败静默 */
let searchTimer: ReturnType<typeof setTimeout> | null = null
function onSymbolInput(): void {
  if (searchTimer) clearTimeout(searchTimer)
  const q = symbolInput.value.trim()
  if (!q) return
  searchTimer = setTimeout(async () => {
    try {
      suggestions.value = await fetchJSON<SymbolHit[]>(
        `/api/research/symbols?q=${encodeURIComponent(q)}`,
      )
    } catch {
      /* 联想失败静默 */
    }
  }, 200)
}

function pickSuggestion(s: SymbolHit): void {
  symbolInput.value = s.symbol
  suggestions.value = []
}

function rangeParams(): URLSearchParams {
  const params = new URLSearchParams()
  if (startDate.value) params.set('start', startDate.value)
  if (endDate.value) params.set('end', endDate.value)
  return params
}

async function loadKline(): Promise<void> {
  const symbol = pickedSymbol()
  if (!symbol) return
  const data = await fetchJSON<BarsData>(`/api/research/bars/${symbol}?${rangeParams()}`)
  lastKline.value = { symbol, data }
}

async function loadFeatures(): Promise<void> {
  const symbol = pickedSymbol()
  if (!symbol) return
  const names = pickedFeatures.value
  if (!names.length) return
  const params = rangeParams()
  params.set('names', names.join(','))
  const data = await fetchJSON<FeatureData>(`/api/research/features/${symbol}?${params}`)
  lastFeature.value = { symbol, names, data }
}

async function loadAll(): Promise<void> {
  error.value = ''
  try {
    await Promise.all([loadKline(), loadFeatures()])
  } catch (e) {
    error.value = (e as Error).message
  }
}

/* 特征勾选变化即重载特征图(对等旧 change 监听) */
watch(pickedFeatures, () => {
  if (lastFeature.value) void loadFeatures().catch((e) => (error.value = (e as Error).message))
})

const klineOption = computed(() => {
  const k = lastKline.value
  if (!k) return null
  const t = palette.value
  return {
    backgroundColor: 'transparent',
    animation: false,
    textStyle: { color: t.text },
    title: {
      text: `${k.symbol} 前复权日线`,
      left: 14,
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
        data: k.data.dates,
        gridIndex: 0,
        ...axisStyle(t),
        splitLine: { show: false },
      },
      {
        type: 'category',
        data: k.data.dates,
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
        name: k.symbol,
        type: 'candlestick',
        data: k.data.ohlc,
        // A 股: 涨红跌绿
        itemStyle: { color: t.up, color0: t.down, borderColor: t.up, borderColor0: t.down },
      },
      {
        name: '成交量',
        type: 'bar',
        data: k.data.volume,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: t.vol },
      },
    ],
  }
})

const featureOption = computed(() => {
  const f = lastFeature.value
  if (!f) return null
  const t = palette.value
  return {
    backgroundColor: 'transparent',
    animation: false,
    textStyle: { color: t.text },
    color: t.series,
    title: {
      text: `${f.symbol} 截面特征（T-1 信息口径）`,
      left: 14,
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
      data: f.data.dates,
      boundaryGap: false,
      ...axisStyle(t),
      splitLine: { show: false },
    },
    yAxis: { type: 'value', scale: true, ...axisStyle(t) },
    dataZoom: [{ type: 'inside' }],
    series: f.names.map((n) => ({
      name: n,
      type: 'line',
      data: f.data.series[n],
      smooth: 0.2,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.6 },
    })),
  }
})
</script>

<template>
  <section data-testid="page-explorer">
    <header class="page-head">
      <h2>个股查看</h2>
      <GlossaryTip term="qfq"><span class="t-muted">前复权</span></GlossaryTip>
      <GlossaryTip term="t1"><span class="t-muted">T-1 口径</span></GlossaryTip>
    </header>

    <ErrorBanner v-if="error" :msg="error" />

    <div class="controls card">
      <div class="symbol-box" data-testid="explorer-symbol-input">
        <NInput
          v-model:value="symbolInput"
          placeholder="标的代码, 如 000021.SZ"
          clearable
          @input="onSymbolInput"
          @keyup.enter="loadAll"
        />
        <ul v-if="suggestions.length" class="suggest card">
          <li v-for="s in suggestions" :key="s.symbol" @click="pickSuggestion(s)">
            <span class="num">{{ s.symbol }}</span> {{ s.name }}
          </li>
        </ul>
      </div>
      <NDatePicker
        v-model:formatted-value="startDate"
        value-format="yyyy-MM-dd"
        type="date"
        placeholder="起始日期"
        clearable
      />
      <NDatePicker
        v-model:formatted-value="endDate"
        value-format="yyyy-MM-dd"
        type="date"
        placeholder="结束日期"
        clearable
      />
      <NButton type="primary" data-testid="explorer-load" @click="loadAll">加载</NButton>
    </div>

    <div class="feature-picker card">
      <span class="t-muted">特征:</span>
      <NCheckbox
        v-for="name in FEATURE_CHOICES"
        :key="name"
        :checked="pickedFeatures.includes(name)"
        size="small"
        @update:checked="
          (v: boolean) => {
            pickedFeatures = v
              ? [...pickedFeatures, name]
              : pickedFeatures.filter((x) => x !== name)
          }
        "
      >
        <span class="num feature-name">{{ name }}</span>
      </NCheckbox>
    </div>

    <div class="chart-card card" data-testid="kline-chart">
      <VChart v-if="klineOption" :option="klineOption" autoresize class="chart chart-kline" />
      <p v-else class="t-muted empty">输入标的并点击加载 — K 线与成交量</p>
    </div>

    <div class="chart-card card" data-testid="feature-chart">
      <VChart v-if="featureOption" :option="featureOption" autoresize class="chart chart-feature" />
      <p v-else class="t-muted empty">特征时序将显示在这里</p>
    </div>
  </section>
</template>

<style scoped>
.page-head {
  align-items: baseline;
  display: flex;
  gap: 10px;
  margin-bottom: var(--gap);
}

.page-head h2 {
  margin: 0;
}

.controls {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap);
  margin-bottom: var(--gap);
  padding: 14px 16px;
}

.symbol-box {
  position: relative;
  width: 260px;
}

.suggest {
  left: 0;
  list-style: none;
  margin: 4px 0 0;
  max-height: 260px;
  overflow-y: auto;
  padding: 4px;
  position: absolute;
  right: 0;
  top: 100%;
  z-index: 50;
}

.suggest li {
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  padding: 6px 10px;
  transition: background var(--dur-fast) var(--ease-out);
}

.suggest li:hover {
  background: var(--accent-soft);
}

.feature-picker {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  font-size: 12.5px;
  gap: 4px 14px;
  margin-bottom: var(--gap);
  padding: 10px 16px;
}

.feature-name {
  font-size: 12px;
}

.chart-card {
  margin-bottom: var(--gap);
  padding: 8px;
}

.chart {
  width: 100%;
}

.chart-kline {
  height: 480px;
}

.chart-feature {
  height: 320px;
}

.empty {
  padding: 60px 0;
  text-align: center;
}
</style>
