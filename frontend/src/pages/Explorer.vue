<script setup lang="ts">
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts'
import {
  AriaComponent,
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { NButton } from 'naive-ui'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { type LocationQuery, useRoute, useRouter } from 'vue-router'

import { fetchJSON } from '@/api/fetch'
import type { BarsData, FeatureData } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useChartTheme } from '@/composables/useChartTheme'

import { useSymbolChips } from './backtests/useSymbolChips'
import {
  buildKlineAriaLabel,
  buildKlineOption,
  DEFAULT_FEATURES,
  symbolColor,
  type SymbolMeta,
} from './explorer/chart-options'
import { parseSymbolsQuery, symbolsToQuery } from './explorer/deep-link'
import FeaturePanel from './explorer/FeaturePanel.vue'

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
  AriaComponent, // 图表容器 role=img 之外, 让 ECharts 生成内部无障碍描述(设计 §8 S5)
  CanvasRenderer,
])

/* 个股查看页 — 多标的叠加改造(设计 docs/feat/0705-explorer-multi-symbol):
 * 标的输入换成 chip(复用 backtests useSymbolChips, 每个 chip 加一枚标的配色圆点);
 * K 线区 option 交给 buildKlineOption 按标的数内部分支(1 个=蜡烛+成交量, 零回归;
 * 2+ 个=涨跌幅对比折线图); 特征区可"新增呈现框"平铺多个 FeaturePanel, 各自独立勾选,
 * 共享 featuresBySymbol 缓存, 拉取时用全部呈现框已勾选特征名的并集(featureUnion)。
 * 去时间选择器: 前端永远不传 start/end, 吃后端 _default_range 默认近一年窗口。
 *
 * loadedSymbols 世代快照(2026-07-05 复核修复 confirmed-bug): chip 输入框的实时数组
 * (chips.symbols)只决定下一次点击"加载"会请求什么 —— 图表分支判定(buildKlineOption 的
 * 标的数)、FeaturePanel 的 symbols prop、refetchFeatures 的请求标的清单, 一律读 loadedSymbols
 * (上一次成功落定的加载轮次快照), 绝不直接读 chips.symbols.value。否则 chip 增删会在点"加载"
 * 之前就让已渲染图表的分支/自动重拉的请求目标瞬间跳变(已复现: 加完第二个 chip 还没点加载,
 * K 线图就从蜡烛图跳成对比折线图; 勾选新特征会连从未加载过的标的一起发请求)。symbolMetas
 * (chip 圆点预览色)例外 —— 设计 §3.1 明确允许圆点用实时数组下标, 点加载前颜色与图表暂不一致
 * 是可接受的纯装饰性差异。 */

const palette = useChartTheme()
const error = ref('')
const loadingData = ref(false)
const hasLoaded = ref(false)

const chips = useSymbolChips()

/* P7 URL 深链: 当前加载的标的组合 ↔ ?symbols=(逗号分隔)。挂载/前进后退从 URL 恢复并加载,
 * 加载成功后 router.replace 写回(不 push, 不污染历史)。序列化/解析纯逻辑在 explorer/deep-link。 */
const route = useRoute()
const router = useRouter()

/* 联想 combobox 键盘(设计 §8 S8): 键盘高亮下标 activeIndex 与移动/收起(onArrowUp/onArrowDown/
 * onEscape/onEnter)全部消费共享 useSymbolChips —— 该 composable 的键盘逻辑由 Backtests 流维护,
 * Explorer 不自持第二套高亮状态, 只在模板侧接 aria 与键盘事件(与 backtests/BacktestForm 同款接线)。 */
const chipsBoxRef = ref<HTMLElement | null>(null)
const SUGGEST_LISTBOX_ID = 'explorer-suggest-listbox'

const suggestOpen = computed(() => chips.suggestions.value.length > 0)
const activeDescId = computed(() =>
  chips.activeIndex.value >= 0 ? `explorer-sug-${chips.activeIndex.value}` : undefined,
)

// 点击标的输入框以外任意处 → 收起候选(仅 Explorer 模板侧接线, 收起逻辑走 composable onEscape)
function onDocPointerDown(e: PointerEvent): void {
  const box = chipsBoxRef.value
  if (box && !box.contains(e.target as Node)) chips.onEscape()
}
onMounted(() => document.addEventListener('pointerdown', onDocPointerDown))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocPointerDown))

let panelSeq = 1 // id 0 已被首个呈现框占用; 简单递增计数器(不用 Date.now()/Math.random())
const panels = ref<{ id: number; features: string[] }[]>([{ id: 0, features: [...DEFAULT_FEATURES] }])

const barsBySymbol = ref<Map<string, BarsData>>(new Map())
const featuresBySymbol = ref<Map<string, FeatureData>>(new Map())
/* 上一次实际发起过 features 请求(首次加载或自动重拉)时用的并集名字 — 判断"并集是否有新增"的基准 */
let lastFeatureNames: string[] = []
/* features 请求世代守卫(confirmed-bug 修复): loadAll 首拉、watch(featureUnion) 触发的自动重拉
 * 共用同一个计数器 —— 每次发起自增并捕获, settle 时比对世代号, 落后的一批(已被更晚一次触发
 * 超越)整批静默丢弃, 不写 featuresBySymbol/lastFeatureNames、不报错(它不代表真实失败, 只是
 * 过期响应)。避免"先发后至"的旧响应覆盖"后发先至"的新响应, 导致已勾选特征的曲线凭空消失。 */
let featureFetchGen = 0

/* 已加载标的快照 —— 上一次成功落定的加载轮次锁定的标的集合。klineOption/FeaturePanel 的
 * symbols prop/refetchFeatures 的请求清单一律读这个, 只在 loadAll 成功或清空时更新。 */
const loadedSymbols = ref<string[]>([])

/* 特征自动重拉在途/失败(任务 2): 勾选新特征触发 refetch 期间给呈现框头部 spinner 反馈,
 * 失败就近在呈现框内提示(featureError), 不再混入顶部 error banner —— 曲线不再凭空出现。 */
const featureFetching = ref(false)
const featureError = ref('')
// 传给每个呈现框的"在途"标志: 首拉(loadingData)与勾选新特征自动重拉(featureFetching)统一口径
const panelFetching = computed(() => loadingData.value || featureFetching.value)

const symbolMetas = computed<SymbolMeta[]>(() =>
  chips.symbols.value.map((symbol, i) => ({ symbol, color: symbolColor(palette.value, i) })),
)

/* 图表/请求真正消费的"当前标的" —— 下标同样按 symbolColor 取色, 但序数来自 loadedSymbols
 * 而非实时 chips, 使 K 线对比图与特征图在同一时刻对同一标的着色一致(设计 §3.2)。 */
const loadedSymbolMetas = computed<SymbolMeta[]>(() =>
  loadedSymbols.value.map((symbol, i) => ({ symbol, color: symbolColor(palette.value, i) })),
)

const featureUnion = computed<string[]>(() => {
  const names = new Set<string>()
  for (const p of panels.value) for (const n of p.features) names.add(n)
  return [...names]
})

const klineOption = computed(() => buildKlineOption(palette.value, loadedSymbolMetas.value, barsBySymbol.value))
/* K 线图容器 role=img 的读屏摘要(设计 §8 S5): 按已加载标的算, 与 klineOption 同口径 */
const klineAriaLabel = computed(() => buildKlineAriaLabel(loadedSymbolMetas.value))
/* K 线 VChart 固定 update-options={notMerge:true}(confirmed-bug 修复, 2026-07-05): 1 标的分支
 * (蜡烛+成交量双 pane, 数组形 xAxis/yAxis/grid)与 2+ 标的分支(单 pane 对比折线图, 对象形)形状
 * 迥异 —— vue-echarts 默认 merge 语义下, 已存在的 ECharts 实例跨越 1↔2+ 标的边界收到新 option 时
 * 会因合并不到旧组件引用而抛 `xAxis "0" not found` 等运行时错误, 且此后持续处于损坏渲染状态
 * (含"新增呈现框"等其他响应式更新一并失效)。notMerge:true 让每次 option 变化整份替换, 规避
 * 该合并路径; FeaturePanel.vue 的特征图同理处理。 */

function onSymInput(e: Event): void {
  chips.input.value = (e.target as HTMLInputElement).value
  chips.onInput(e)
}
function onSymKeydown(e: KeyboardEvent): void {
  switch (e.key) {
    case 'Enter':
      e.preventDefault()
      chips.onEnter() // 有键盘高亮取高亮候选, 否则既有语义(完整代码即时成 chip / 名称搜索取首条)
      break
    case 'ArrowDown':
      e.preventDefault() // 阻止光标跳行尾, 改为在候选间下移高亮
      chips.onArrowDown()
      break
    case 'ArrowUp':
      e.preventDefault()
      chips.onArrowUp()
      break
    case 'Escape':
      chips.onEscape()
      break
    case 'Backspace':
      chips.onBackspace()
      break
  }
}

function addPanel(): void {
  panels.value.push({ id: panelSeq++, features: [] })
}

function removePanel(id: number): void {
  if (panels.value.length <= 1) return
  panels.value = panels.value.filter((p) => p.id !== id)
}

async function fetchBarsFor(symbol: string): Promise<[string, BarsData]> {
  const data = await fetchJSON<BarsData>(`/api/research/bars/${symbol}`)
  return [symbol, data]
}

async function fetchFeaturesFor(symbol: string, names: string[]): Promise<[string, FeatureData]> {
  const params = new URLSearchParams({ names: names.join(',') })
  const data = await fetchJSON<FeatureData>(`/api/research/features/${symbol}?${params}`)
  return [symbol, data]
}

/* names 为空(所有呈现框都清空了勾选)不发请求, 直接给空 Map — 对等旧版"全取消勾选 → 清图" */
async function fetchFeatureMap(symbols: string[], names: string[]): Promise<Map<string, FeatureData>> {
  if (!names.length) return new Map()
  const entries = await Promise.all(symbols.map((s) => fetchFeaturesFor(s, names)))
  return new Map(entries)
}

async function loadAll(): Promise<void> {
  error.value = ''
  featureError.value = ''
  chips.onEscape() // 点"加载"即收起残留的联想候选(走 composable 收起逻辑)
  const symbols = chips.symbols.value
  if (symbols.length === 0) {
    barsBySymbol.value = new Map()
    featuresBySymbol.value = new Map()
    hasLoaded.value = false
    loadedSymbols.value = []
    lastFeatureNames = []
    featureFetchGen++ // 让任何仍在途的旧 features 请求(若有)在落定时被判定过期, 不回填已清空的状态
    return
  }
  loadingData.value = true
  const names = featureUnion.value
  const myFeatureGen = ++featureFetchGen // 与 refetchFeatures 共用同一世代计数器
  try {
    const [barsEntries, featureMap] = await Promise.all([
      Promise.all(symbols.map((s) => fetchBarsFor(s))),
      fetchFeatureMap(symbols, names),
    ])
    // bars/loadedSymbols/hasLoaded 不受 features 世代竞争影响 —— 本轮"加载"点击本身就是权威动作
    // (按钮在 loadingData 期间禁用, 不存在并发的第二次"加载"), 只有 features 缓存的落地需要
    // 世代守卫, 防止期间插入的一次自动重拉(针对旧 loadedSymbols)后发先至覆盖本轮结果。
    barsBySymbol.value = new Map(barsEntries)
    loadedSymbols.value = symbols
    hasLoaded.value = true
    if (myFeatureGen === featureFetchGen) {
      featuresBySymbol.value = featureMap
      lastFeatureNames = names
    }
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loadingData.value = false
  }
}

/* 特征并集扩大(较上次实际请求过的并集有新增特征名)且此前已成功加载过 → 对当前标的集合重新拉一次
 * features(不重拉 bars); 仅缩小(去勾选/删呈现框) → 直接用现有缓存重渲染, 不发请求。watch 默认非
 * immediate, 不会在初始挂载/首次 loadAll 之外被误触发(loadAll 本身不改 panels, 不会自举触发)。 */
watch(featureUnion, (names) => {
  if (!hasLoaded.value) return
  const hasNew = names.some((n) => !lastFeatureNames.includes(n))
  if (!hasNew) return
  void refetchFeatures(names)
})

async function refetchFeatures(names: string[]): Promise<void> {
  featureError.value = ''
  featureFetching.value = true // 呈现框头部 spinner 亮起(任务 2): 在途有反馈, 曲线不再凭空跳出
  const myFeatureGen = ++featureFetchGen // 与 loadAll 首拉共用同一世代计数器(见上方声明处说明)
  try {
    const map = await fetchFeatureMap(loadedSymbols.value, names)
    if (myFeatureGen !== featureFetchGen) return // 已被更晚一次触发超越, 整批静默丢弃(不写缓存不报错)
    featuresBySymbol.value = map
    lastFeatureNames = names
  } catch (e) {
    if (myFeatureGen !== featureFetchGen) return // 过期请求的失败不代表当前真实状态, 不提示
    featureError.value = (e as Error).message // 就近在呈现框内提示, 不进顶部 banner
  } finally {
    // 仅最新一批(未被超越)负责熄灭 spinner; 被超越的旧批把 spinner 让给更新的在途请求
    if (myFeatureGen === featureFetchGen) featureFetching.value = false
  }
}

/* ---- P7 URL 深链: 已加载标的 ↔ ?symbols= 双向同步 ----
 * 防死循环靠两侧共同的「规范化 query 串相等 → 不重复动作」幂等门槛, 一次往返内收敛:
 *  - 恢复侧(URL→状态): query 变 → 解析后若 ≠ 当前 loadedSymbols 的规范串才加载;
 *  - 写回侧(状态→URL): loadedSymbols 变 → 若其规范串 ≠ 当前 query 规范串才 replace。
 * 例: 挂载带 ?symbols=A,B → 恢复加载 → loadedSymbols=[A,B] → 写回侧算出规范串与 query 相等 → 不 replace;
 *     手动加载 [A,B] → 写回 ?symbols=A,B → 恢复侧解析后与 loadedSymbols 相等 → 不重复加载。 */

/** 用给定合法标的清单填充 chips 并复用 loadAll 加载; 与当前已加载集合规范化后一致则跳过(幂等)。 */
async function applySymbolsFromQuery(list: string[]): Promise<void> {
  if (symbolsToQuery(list) === symbolsToQuery(loadedSymbols.value)) return
  chips.clearPending() // 清在途联想防抖, 防旧候选回填
  chips.onEscape() // 收起残留候选浮层
  chips.symbols.value = [...list] // 直接置入(list 已是解析校验过的合法集合)
  chips.input.value = ''
  chips.err.value = ''
  await loadAll()
}

/** 已加载标的 → ?symbols= 写回(replace 不 push, 不污染历史); 规范串与当前 query 一致则不重复写(幂等)。 */
function syncQueryFromLoaded(): void {
  const loadedQ = symbolsToQuery(loadedSymbols.value)
  if (loadedQ === parseSymbolsQuery(route.query.symbols).join(',')) return
  const { symbols: _omit, ...rest } = route.query // 摘掉旧 symbols, 保留其余 query 参数
  const query: LocationQuery = loadedQ ? { ...rest, symbols: loadedQ } : rest
  void router.replace({ query })
}

// 加载落定(成功或清空)即写回 URL; loadAll 每次赋新数组给 loadedSymbols, ref watch 足够触发
watch(loadedSymbols, syncQueryFromLoaded)

// 前进/后退等 URL 变化 → 从 query 恢复(非 immediate; 挂载首恢复交给下方 onMounted, 避免双触发)
watch(
  () => route.query.symbols,
  (raw) => void applySymbolsFromQuery(parseSymbolsQuery(raw)),
)

// 挂载时若带 ?symbols= 则解析并自动加载(复用 loadAll)
onMounted(() => {
  const initial = parseSymbolsQuery(route.query.symbols)
  if (initial.length) void applySymbolsFromQuery(initial)
})
</script>

<template>
  <section data-testid="page-explorer">
    <PageHeader title="个股查看">
      <template #meta>
        <GlossaryTip term="qfq"><span class="t-muted">前复权</span></GlossaryTip>
        <GlossaryTip term="t1"><span class="t-muted">T-1 口径</span></GlossaryTip>
      </template>
      <template #default>
        查看本地库内标的的 K 线与预计算截面特征（近一年窗口），支持添加多个标的叠加对比。特征即因子检验用的原料——悬停任一特征名可看它衡量什么、怎么读数。
      </template>
    </PageHeader>

    <ErrorBanner v-if="error" :msg="error" />

    <div class="controls card">
      <label class="sym-field" for="explorer-symbol-combobox">
        标的
        <div ref="chipsBoxRef" class="chips-box" data-testid="explorer-symbol-input">
          <span v-for="meta in symbolMetas" :key="meta.symbol" class="chip">
            <span class="chip-dot" :style="{ background: meta.color }" />
            {{ meta.symbol }}
            <button
              class="chip-x"
              type="button"
              :aria-label="`移除标的 ${meta.symbol}`"
              @click="chips.remove(meta.symbol)"
            >×</button>
          </span>
          <input
            id="explorer-symbol-combobox"
            class="chip-input"
            :value="chips.input.value"
            placeholder="代码/名称联想，回车或点选添加，可多个叠加对比"
            autocomplete="off"
            role="combobox"
            aria-autocomplete="list"
            :aria-expanded="suggestOpen ? 'true' : 'false'"
            :aria-controls="SUGGEST_LISTBOX_ID"
            :aria-activedescendant="activeDescId"
            aria-label="标的代码或名称联想输入，方向键选择候选，回车添加"
            @input="onSymInput"
            @keydown="onSymKeydown"
          />
          <ul v-if="suggestOpen" :id="SUGGEST_LISTBOX_ID" class="suggest card" role="listbox" aria-label="标的联想候选">
            <li
              v-for="(hit, i) in chips.suggestions.value"
              :id="`explorer-sug-${i}`"
              :key="hit.symbol"
              role="option"
              :aria-selected="chips.activeIndex.value === i ? 'true' : 'false'"
              :class="{ 'is-active': chips.activeIndex.value === i }"
              @click="chips.pickSuggestion(hit)"
            >
              <span class="num">{{ hit.symbol }}</span> {{ hit.name }}
            </li>
          </ul>
        </div>
      </label>
      <NButton type="primary" :loading="loadingData" :disabled="loadingData" data-testid="explorer-load" @click="loadAll">加载</NButton>
    </div>
    <p v-if="chips.err.value" class="form-hint sym-err t-warn" role="alert">{{ chips.err.value }}</p>

    <div class="chart-card card" data-testid="kline-chart">
      <!-- 加载期给骨架, 不让"添加标的并点击加载"空态文案冒充加载态(任务 5) -->
      <div v-if="loadingData" class="chart-skeleton chart-kline" aria-hidden="true" />
      <VChart
        v-else-if="klineOption"
        role="img"
        :aria-label="klineAriaLabel"
        :option="klineOption"
        :update-options="{ notMerge: true }"
        autoresize
        class="chart chart-kline"
      />
      <p v-else class="t-muted empty">添加标的并点击加载 — K 线与成交量</p>
    </div>

    <FeaturePanel
      v-for="(p, i) in panels"
      :key="p.id"
      v-model="p.features"
      :symbols="loadedSymbolMetas"
      :features-by-symbol="featuresBySymbol"
      :removable="panels.length > 1"
      :panel-index="i"
      :fetching="panelFetching"
      :fetch-error="featureError"
      @remove="removePanel(p.id)"
    />
    <button type="button" class="add-panel-btn" data-testid="explorer-add-panel" @click="addPanel">
      + 新增呈现框
    </button>
  </section>
</template>

<style scoped>
.controls {
  align-items: end;
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap);
  margin-bottom: var(--gap);
  padding: 12px 16px;
}

.sym-field {
  color: var(--text-3);
  display: flex;
  flex: 1;
  flex-direction: column;
  font-size: 12.5px;
  gap: 6px;
  min-width: 280px;
}

.chips-box {
  align-items: center;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 38px;
  padding: 5px 8px;
  position: relative;
  transition: border-color var(--dur-fast) var(--ease-out);
}

.chips-box:focus-within {
  border-color: var(--accent);
}

.chip {
  align-items: center;
  background: var(--accent-soft);
  border-radius: 14px;
  color: var(--accent);
  display: inline-flex;
  font-family: var(--font-mono);
  font-size: 12px;
  gap: 4px;
  padding: 2px 6px 2px 10px;
}

.chip-dot {
  border-radius: 50%;
  flex: none;
  height: 8px;
  width: 8px;
}

.chip-x {
  background: transparent;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0 2px;
}

.chip-x:hover {
  color: var(--c-fail);
}

.chip-input {
  background: transparent;
  border: none;
  color: var(--text);
  flex: 1;
  font-family: var(--font-body);
  font-size: 13px;
  min-width: 180px;
  outline: none;
  padding: 4px 2px;
}

.suggest {
  left: 0;
  list-style: none;
  margin: 0;
  max-height: 260px;
  overflow-y: auto;
  padding: 4px;
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  z-index: 50;
}

.suggest li {
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  padding: 6px 10px;
  transition: background var(--dur-fast) var(--ease-out);
}

.suggest li:hover,
.suggest li.is-active {
  background: var(--accent-soft);
}

.form-hint {
  font-size: 12.5px;
  margin: 6px 0 var(--gap);
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

/* 加载骨架: 固定高度占位, 数据到达不跳版(任务 5); reduced-motion 归零 */
.chart-skeleton {
  animation: kline-skeleton-pulse 1.4s ease-in-out infinite;
  background: var(--bg-3);
  border-radius: var(--radius-sm);
  width: 100%;
}

@keyframes kline-skeleton-pulse {
  50% {
    opacity: 0.5;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chart-skeleton {
    animation: none;
    opacity: 0.7;
  }
}

.empty {
  padding: 60px 0;
  text-align: center;
}

.add-panel-btn {
  background: transparent;
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  color: var(--text-3);
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
  padding: 10px 16px;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
  width: 100%;
}

.add-panel-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
</style>
