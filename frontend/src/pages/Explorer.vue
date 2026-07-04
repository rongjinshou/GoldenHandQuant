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
/* 特征中文标签 + glossary 词条(term=特征名) — 勾选框不再裸英文变量名 */
const FEATURE_META: { name: string; label: string }[] = [
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

function featureLabel(name: string): string {
  return FEATURE_META.find((f) => f.name === name)?.label ?? name
}

const palette = useChartTheme()
const error = ref('')
const loadingData = ref(false)

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

/* 联想: 200ms 防抖, 失败静默; seq 守卫 — 加载/选中/失焦后迟到的响应丢弃不再弹出 */
let searchTimer: ReturnType<typeof setTimeout> | null = null
let suggestSeq = 0
function onSymbolInput(): void {
  if (searchTimer) clearTimeout(searchTimer)
  const q = symbolInput.value.trim()
  if (!q) return
  const mySeq = ++suggestSeq
  searchTimer = setTimeout(async () => {
    try {
      const hits = await fetchJSON<SymbolHit[]>(
        `/api/research/symbols?q=${encodeURIComponent(q)}`,
      )
      if (mySeq === suggestSeq) suggestions.value = hits
    } catch {
      /* 联想失败静默 */
    }
  }, 200)
}

function closeSuggestions(): void {
  suggestSeq++ // 使飞行中的联想请求作废
  if (searchTimer) clearTimeout(searchTimer)
  suggestions.value = []
}

function pickSuggestion(s: SymbolHit): void {
  symbolInput.value = s.symbol
  closeSuggestions()
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
  if (!names.length) {
    lastFeature.value = null // 全取消勾选 → 清图, 不残留旧曲线
    return
  }
  const params = rangeParams()
  params.set('names', names.join(','))
  const data = await fetchJSON<FeatureData>(`/api/research/features/${symbol}?${params}`)
  lastFeature.value = { symbol, names, data }
}

async function loadAll(): Promise<void> {
  error.value = ''
  closeSuggestions() // 加载即收起联想下拉(含飞行中请求)
  loadingData.value = true
  try {
    await Promise.all([loadKline(), loadFeatures()])
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loadingData.value = false
  }
}

/* 失焦延迟收起联想(留点击选项的时间窗) */
function onSymbolBlur(): void {
  setTimeout(closeSuggestions, 160)
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
      data: f.data.dates,
      boundaryGap: false,
      ...axisStyle(t),
      splitLine: { show: false },
    },
    yAxis: { type: 'value', scale: true, ...axisStyle(t) },
    dataZoom: [{ type: 'inside' }],
    series: f.names.map((n) => ({
      name: featureLabel(n), // 图例/悬浮提示用中文标签
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
    <p class="guide t-muted">
      查看本地库内任一标的的 K 线与预计算截面特征。特征即因子检验用的原料——悬停任一特征名可看它衡量什么、怎么读数。
    </p>

    <ErrorBanner v-if="error" :msg="error" />

    <div class="controls card">
      <label class="ctl-field">
        标的
        <div class="symbol-box" data-testid="explorer-symbol-input">
          <NInput
            v-model:value="symbolInput"
            placeholder="代码/名称联想, 如 000021.SZ"
            clearable
            @input="onSymbolInput"
            @blur="onSymbolBlur"
            @keyup.enter="loadAll"
          />
          <ul v-if="suggestions.length" class="suggest card">
            <li v-for="s in suggestions" :key="s.symbol" @click="pickSuggestion(s)">
              <span class="num">{{ s.symbol }}</span> {{ s.name }}
            </li>
          </ul>
        </div>
      </label>
      <label class="ctl-field">
        起始
        <NDatePicker
          v-model:formatted-value="startDate"
          value-format="yyyy-MM-dd"
          type="date"
          placeholder="最早"
          clearable
          style="width: 160px"
        />
      </label>
      <label class="ctl-field">
        结束
        <NDatePicker
          v-model:formatted-value="endDate"
          value-format="yyyy-MM-dd"
          type="date"
          placeholder="最新"
          clearable
          style="width: 160px"
        />
      </label>
      <NButton type="primary" :loading="loadingData" :disabled="loadingData" data-testid="explorer-load" @click="loadAll">加载</NButton>
    </div>

    <!-- 标签列固定, 复选框自成一列换行对齐; 中文标签+悬停术语解释 -->
    <div class="feature-picker card">
      <span class="t-muted picker-label">特征</span>
      <div class="feature-list">
        <NCheckbox
          v-for="fm in FEATURE_META"
          :key="fm.name"
          :checked="pickedFeatures.includes(fm.name)"
          size="small"
          @update:checked="
            (v: boolean) => {
              pickedFeatures = v
                ? [...pickedFeatures, fm.name]
                : pickedFeatures.filter((x) => x !== fm.name)
            }
          "
        >
          <GlossaryTip :term="fm.name"><span class="feature-name">{{ fm.label }}</span></GlossaryTip>
        </NCheckbox>
      </div>
    </div>

    <div class="chart-card card" data-testid="kline-chart">
      <VChart v-if="klineOption" :option="klineOption" autoresize class="chart chart-kline" />
      <p v-else class="t-muted empty">输入标的并点击加载 — K 线与成交量</p>
    </div>

    <div class="chart-card card" data-testid="feature-chart">
      <VChart v-if="featureOption" :option="featureOption" autoresize class="chart chart-feature" />
      <p v-else class="t-muted empty">暂无特征曲线 — 勾选上方特征并点击加载。</p>
    </div>
  </section>
</template>

<style scoped>
.page-head {
  align-items: baseline;
  display: flex;
  gap: 10px;
  margin-bottom: 6px;
}

.page-head h2 {
  margin: 0;
}

.guide {
  font-size: 13px;
  margin: 0 0 var(--gap);
}

.controls {
  align-items: end;
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap);
  margin-bottom: var(--gap);
  padding: 12px 16px;
}

.ctl-field {
  color: var(--text-3);
  display: flex;
  flex-direction: column;
  font-size: 12.5px;
  gap: 6px;
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
  align-items: baseline;
  display: flex;
  font-size: 12.5px;
  gap: 14px;
  margin-bottom: var(--gap);
  padding: 10px 16px;
}

.picker-label {
  flex: none;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
}

.feature-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
}

.feature-name {
  font-size: 12px;
}

.chart-card {
  margin-bottom: var(--gap);
  padding: 8px 16px 12px;
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
