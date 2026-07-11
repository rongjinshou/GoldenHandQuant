<script setup lang="ts">
import { NPopconfirm, NSelect } from 'naive-ui'
import { computed, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { deleteJSON, fetchJSON } from '@/api/fetch'
import type { BacktestRun, BarsData, StrategyMeta } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import PageHeader from '@/components/PageHeader.vue'

import BacktestForm from './backtests/BacktestForm.vue'
import {
  type BenchmarkStats,
  benchmarkStats,
  buildBenchmarkValues,
  f3,
  firstStrategy,
  type OverlayLine,
  pct,
  rebaseOverlays,
  truncatedTradesStrategy,
} from './backtests/chart-data'
import EquityChart from './backtests/EquityChart.vue'
import { bestByColumn, type Cell, ddCell, marketCell, qualityCell } from './backtests/metric-cell'
import { buildRunLabel, sourceLabel } from './backtests/run-naming'
import {
  overlayFromQuery,
  resolveSelection,
  selectionFromQuery,
  shouldSyncOverlayToUrl,
  shouldSyncRunToUrl,
} from './backtests/run-selection'

/* 回测页 — 旧 backtests.js loadBacktests/renderBtRun 对等:
 * 回测列表(倒序, 同 run 多策略并排, 行点击进详情) + 详情(基准/叠加下拉 + meta 条 +
 * 指标表 + 净值回撤图)。基准异步取行情 → seq 守卫: 切换详情后过期渲染丢弃。
 * 提交表单/JobCard 闭环拆到 BacktestForm; 净值图拆到 EquityChart + 纯逻辑 chart-data.ts。 */

const BENCH_OPTIONS = [
  { label: '首标的买入持有', value: 'first_symbol' },
  { label: '沪深300', value: '000300.SH' },
  { label: '中证1000', value: '000852.SH' },
  { label: '无', value: '' },
]

const error = ref('')
const loading = ref(true)
const runs = ref<BacktestRun[]>([])
const strategyMeta = ref<StrategyMeta[]>([])
const selectedRunId = ref<string | null>(null)
const benchSel = ref('first_symbol')
const overlaySel = ref<string | null>(null)

// URL 深链(设计 §12 P7): 选中回测轮 ↔ ?run=、叠加对比 ↔ ?overlay=, 可深链/刷新/收藏恢复
const route = useRoute()
const router = useRouter()
// ?overlay= 首载恢复只做一次(runs 载入后才有列表可验合法性), 见 loadBacktests 内注释
let overlayRestored = false

const selectedRun = computed(() => runs.value.find((r) => r.run_id === selectedRunId.value) ?? null)
const first = computed(() => (selectedRun.value ? (firstStrategy(selectedRun.value) ?? null) : null))

function typeOf(name: string): string | undefined {
  return strategyMeta.value.find((s) => s.name === name)?.strategy_type
}

async function loadBacktests(): Promise<void> {
  try {
    const data = await fetchJSON<{ runs: BacktestRun[] }>('/api/research/backtests')
    runs.value = data.runs
    // 选中决策交给纯函数(run-selection.ts, 已单测): 原选中仍在则保留(删他轮/完成刷新不弹走
    // 当前详情); 否则 URL ?run= 命中则恢复深链(首次载入/刷新/收藏); 都不命中落最新(倒序首条)
    const urlRun = typeof route.query.run === 'string' ? route.query.run : null
    selectedRunId.value = resolveSelection(runs.value, urlRun, selectedRunId.value)
    // ?overlay= 挂载恢复: 首次载入成功后(选中已落定, 才能判"等于当前选中")合法则恢复叠加,
    // 非法静默忽略(URL 值保留)。仅首载回读一次 —— 之后会话内状态为准, 防后台刷新(任务完成/
    // 删轮触发的重载)让残留 URL 值凭空弹出叠加
    if (!overlayRestored) {
      overlayRestored = true
      const ov = overlayFromQuery(route.query.overlay, runs.value, selectedRunId.value)
      if (ov !== overlaySel.value) overlaySel.value = ov
    }
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function loadStrategyMeta(): Promise<void> {
  try {
    const data = await fetchJSON<{ strategies: StrategyMeta[] }>('/api/meta/strategies')
    strategyMeta.value = data.strategies
  } catch (e) {
    error.value = (e as Error).message
  }
}

void loadStrategyMeta()
void loadBacktests()

function selectRun(runId: string): void {
  selectedRunId.value = runId
}

/* URL 深链两向同步(设计 §12 P7) — router.replace(不 push)不污染历史; 两向 watch 靠
 * run-selection.ts 的幂等函数(shouldSyncRunToUrl/selectionFromQuery)互相刹车防死循环:
 * 选中→写URL 与 URL→选中 各自遇"两边已一致"即止步, 不会无限往返。 */
// 选中 → URL: 仅当 URL 现值与选中不同才 replace(幂等挡回环)
watch(selectedRunId, (id) => {
  const cur = typeof route.query.run === 'string' ? route.query.run : null
  if (!shouldSyncRunToUrl(cur, id)) return
  const query = { ...route.query }
  if (id) query.run = id
  else delete query.run
  void router.replace({ query })
})
// URL ?run= → 选中: 响应浏览器前进/后退, 命中列表且非当前才切(幂等挡回环)
watch(
  () => route.query.run,
  (raw) => {
    const id = selectionFromQuery(raw, runs.value, selectedRunId.value)
    if (id !== null) selectedRunId.value = id
  },
)

/* 叠加对比 ↔ ?overlay= 深链(批三收尾) — 与 ?run= 同模式两向 watch + 幂等刹车。 */
// 叠加 → URL: 现值不同才 replace; 「因 URL 值非法被置空」不回写(shouldSyncOverlayToUrl
// 静默容错分支, 保住用户手输的值); null 时 rest-omit 摘键(同 Explorer.vue 深链写法)
watch(overlaySel, (id) => {
  const cur = typeof route.query.overlay === 'string' ? route.query.overlay : null
  if (!shouldSyncOverlayToUrl(cur, id, runs.value, selectedRunId.value)) return
  const { overlay: _omit, ...rest } = route.query // 摘掉旧 overlay, 保留其余 query 参数
  void router.replace({ query: id ? { ...rest, overlay: id } : rest })
})
// URL ?overlay= → 叠加: 前进/后退; 缺席=清空, 非法(不在列表/等于当前选中)=忽略置空,
// 合法=采用(语义见 overlayFromQuery)。注册在 ?run= watch 之后 —— 同一次导航两键齐变时,
// 选中轮先落定, 本回调读到的 selectedRunId 已是新值
watch(
  () => route.query.overlay,
  (raw) => {
    const next = overlayFromQuery(raw, runs.value, selectedRunId.value)
    if (next !== overlaySel.value) overlaySel.value = next
  },
)

/* 研究记录退役(设计 docs/feat/0705-research-retire) — 整轮硬删除, 无回收站;
 * 重删的是当前选中项时, loadBacktests 重载后按既有语义自动落最新一条, 无需特判。 */
const deletingId = ref<string | null>(null)

async function deleteRun(runId: string): Promise<void> {
  deletingId.value = runId
  try {
    await deleteJSON(`/api/research/backtests/${runId}`)
    await loadBacktests()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    deletingId.value = null
  }
}

/* run 业务化标题(设计 0705 §3.B) — 展示层纯函数, 不改 run_id/不入库 */
const runLabels = computed(() => new Map(runs.value.map((r) => [r.run_id, buildRunLabel(r, strategyMeta.value)])))

/* 左轨行原生 tooltip: 标题/副行窄轨下 ellipsis 截断, 悬停读全(标题换行 + 副行含 run_id)。
 * 挂行容器而非内部按钮 — 无 title 的后代悬停时继承祖先 title, 整行同一提示。 */
function runRowTitle(runId: string): string {
  const label = runLabels.value.get(runId)
  return label ? `${label.title}\n${label.subtitle} · ${runId}` : runId
}

// ---- 基准: 同额买入持有(异步取 /bars 现算, seq 守卫过期丢弃) ----
const benchRaw = shallowRef<{ series: (number | null)[] | null; note: string }>({
  series: null,
  note: '',
})
// 切 run/基准时基准异步重算, 加载期占位防控制条塌陷抖动(设计 P5)
const benchLoading = ref(false)
let benchSeq = 0

const currentBenchSym = computed(() => {
  const symbols = (first.value?.params?.symbols ?? []) as string[]
  return benchSel.value === 'first_symbol' ? (symbols[0] ?? '') : benchSel.value
})

async function loadBenchmark(): Promise<void> {
  const fst = first.value
  benchRaw.value = { series: null, note: '' }
  const dates = fst?.equity_curve.dates ?? []
  const sym = currentBenchSym.value
  if (!fst || !sym || !dates.length) {
    benchLoading.value = false
    return
  }
  const mySeq = ++benchSeq
  benchLoading.value = true
  try {
    const bars = await fetchJSON<BarsData>(
      `/api/research/bars/${sym}?start=${dates[0]}&end=${dates[dates.length - 1]}`,
    )
    if (mySeq !== benchSeq) return // 切换详情后迟到响应丢弃(不动 loading, 归更新的那次拥有)
    const closes = bars.ohlc.map((o) => o[1]) // ECharts 约定 [o,c,l,h]
    const series = buildBenchmarkValues(dates, bars.dates, closes, fst.initial_capital)
    benchRaw.value = { series, note: series ? '' : `基准 ${sym} 无本地行情` }
  } catch {
    if (mySeq !== benchSeq) return
    benchRaw.value = { series: null, note: '基准行情加载失败' }
  } finally {
    if (mySeq === benchSeq) benchLoading.value = false
  }
}

watch([selectedRunId, benchSel], () => void loadBenchmark(), { immediate: true })

/* 基准展示: 有效点 <2 撤线并转"区间内行情不足"; 同窗口径超额随 stats */
const benchInfo = computed<{
  series: (number | null)[] | null
  stats: BenchmarkStats | null
  warn: string
}>(() => {
  const series = benchRaw.value.series
  const fst = first.value
  const sym = currentBenchSym.value
  if (!series || !fst) return { series: null, stats: null, warn: benchRaw.value.note }
  const dates = fst.equity_curve.dates ?? []
  const stats = benchmarkStats(series, fst.equity_curve.values ?? [], dates)
  if (!stats) return { series: null, stats: null, warn: `基准 ${sym} 区间内行情不足` }
  return { series, stats, warn: '' }
})

// ---- 叠加对比: 另一轮重定基到当前 run(排除自身) ----
// 叠加选项 value 用 run_id(非数组下标): 删任意轮后 runs 重排, 下标会静默指向另一条 run
// 的曲线(数据误读); run_id 稳定, 找不到即无叠加(设计 P5 修 bug)
const overlayOptions = computed(() =>
  runs.value.map((r) => ({
    label: `${runLabels.value.get(r.run_id)?.title ?? r.run_id}（${r.run_id}）`,
    value: r.run_id,
  })),
)
const overlayRun = computed(() => {
  if (overlaySel.value === null) return null
  const r = runs.value.find((x) => x.run_id === overlaySel.value)
  if (!r || r.run_id === selectedRun.value?.run_id) return null
  return r
})
const overlayComputed = computed<{ lines: OverlayLine[]; anyOverlap: boolean }>(() => {
  const fst = first.value
  const other = overlayRun.value
  const dates = fst?.equity_curve.dates ?? []
  // other 已选但当前 run 无曲线(无 fst/无 dates) → anyOverlap:false 触发"无重叠"警示(对等旧版)
  if (!fst || !other || !dates.length) return { lines: [], anyOverlap: !other }
  return rebaseOverlays(dates, other, fst)
})

// ---- meta 条 ----
const createdAt = computed(() => (selectedRun.value?.created_at ?? '').slice(0, 19))
const source = computed(() => sourceLabel(first.value?.params?.source as string | undefined))
const initialCapitalText = computed(() => {
  const c = first.value?.initial_capital
  return c ? c.toLocaleString() : '?'
})
const targetNames = computed(() => (first.value?.params?.strategies ?? []) as string[])
const targetBadges = computed(() =>
  targetNames.value.map((n) => {
    const ty = typeOf(n)
    if (ty === 'cross_section') return { name: n, badge: '[截面]', gloss: 'cs_strategy' }
    if (ty === undefined) return { name: n, badge: '', gloss: '' }
    return { name: n, badge: '[时序]', gloss: 'ts_strategy' }
  }),
)
const anyCross = computed(() => targetNames.value.some((n) => typeOf(n) === 'cross_section'))
const targetSymbols = computed(() => (first.value?.params?.symbols ?? []) as string[])
const shownSymbols = computed(() => targetSymbols.value.slice(0, 8))
const moreSymbols = computed(() => targetSymbols.value.length - shownSymbols.value.length)
const truncated = computed(() =>
  selectedRun.value ? (truncatedTradesStrategy(selectedRun.value) ?? null) : null,
)

// ---- 指标表(全部策略, 含无曲线的旧 CLI 行) ----
// 配色: 收益/超额走行情色(marketCell 涨红跌绿), 质量指标中性(qualityCell), 回撤超阈红(ddCell)
const metricRows = computed(() =>
  (selectedRun.value?.strategies ?? []).map((s) => ({
    name: s.strategy,
    range: `${s.start_date ?? '?'} ~ ${s.end_date ?? '?'}`,
    // 裸值与 cells 列序严格一致(供 bestByColumn 按 METRIC_DIRECTIONS 逐列评优)
    values: [
      s.total_return,
      s.annualized_return,
      s.max_drawdown,
      s.sharpe_ratio,
      s.sortino_ratio,
      s.calmar_ratio,
      s.win_rate,
      s.trade_count,
      s.turnover_rate,
    ],
    cells: [
      marketCell(s.total_return, pct),
      marketCell(s.annualized_return, pct),
      ddCell(s.max_drawdown, pct),
      qualityCell(s.sharpe_ratio, f3),
      qualityCell(s.sortino_ratio, f3),
      qualityCell(s.calmar_ratio, f3),
      qualityCell(s.win_rate, pct),
      { text: s.trade_count === null || s.trade_count === undefined ? '-' : String(s.trade_count), cls: '' },
      qualityCell(s.turnover_rate, pct),
    ] as Cell[],
  })),
)

// 多策略同轮对比(≥2 行)才评优: 每列最优单元格键集 "ri-ci"(纯函数已单测, 单行返回空集)
const bestCells = computed(() => bestByColumn(metricRows.value.map((r) => r.values)))

function onFormDone(): void {
  void loadBacktests()
}
</script>

<template>
  <section data-testid="page-backtests">
    <PageHeader title="回测">
      把策略放回历史行情模拟交易。<GlossaryTip term="ts_strategy">时序策略</GlossaryTip>（如双均线）回测你填的标的；<GlossaryTip
        term="cs_strategy"
        >截面策略</GlossaryTip
      >（如小市值）在全市场抽样池上选股，标的框不生效。提交后任务卡实时滚日志，完成自动刷新下方结果。
    </PageHeader>

    <ErrorBanner v-if="error" :msg="error" />

    <BacktestForm :strategy-meta="strategyMeta" @done="onFormDone" />

    <p v-if="loading" class="empty t-muted">加载回测记录中…</p>

    <!-- 工作区: 左轨(轮次列表, 限高滚动) + 右详情(图表主角) -->
    <div v-else-if="runs.length" class="bt-workspace">
      <aside class="run-rail card">
        <!-- 内层宽屏下绝对定位: 左轨不参与撑高, 高度完全跟随右侧详情 → 两栏底边对齐 -->
        <div class="rail-inner">
          <div class="rail-head">
            <span class="rail-title">回测轮次</span>
            <span class="rail-count num">{{ runs.length }}</span>
          </div>
          <div class="run-scroll" data-testid="bt-run-list">
            <!-- 容器改 div: 内部拆平级两真 button(选择/删除), 不再交互元素嵌套(WCAG 4.1.2);
                 删除钮 :focus-visible 显形, 键盘可见可达(2.1.1/1.4.13) -->
            <div
              v-for="r in runs"
              :key="r.run_id"
              class="run-row"
              :class="{ active: r.run_id === selectedRunId }"
              :title="runRowTitle(r.run_id)"
              data-testid="bt-run-row"
            >
              <!-- 选择钮不设 title(设了会遮住行容器完整提示), 悬停继承行容器 tooltip -->
              <button
                type="button"
                class="run-select"
                data-testid="bt-run-select"
                :aria-current="r.run_id === selectedRunId ? 'true' : undefined"
                @click="selectRun(r.run_id)"
              >
                <span class="run-title">{{ runLabels.get(r.run_id)?.title }}</span>
                <span class="run-row-bottom">
                  <span class="run-subtitle">{{ runLabels.get(r.run_id)?.subtitle }}</span>
                  <span class="run-id num">{{ r.run_id }}</span>
                </span>
              </button>
              <NPopconfirm positive-text="删除" negative-text="取消" @positive-click="deleteRun(r.run_id)">
                <template #trigger>
                  <button
                    type="button"
                    class="run-delete"
                    :class="{ 'run-delete--busy': deletingId === r.run_id }"
                    data-testid="bt-run-delete"
                    :disabled="deletingId === r.run_id"
                    :aria-label="`删除这轮回测: ${runLabels.get(r.run_id)?.title}`"
                  >✕</button>
                </template>
                <div class="confirm-body">
                  <div>删除这轮回测？</div>
                  <div><b>{{ runLabels.get(r.run_id)?.title }}</b></div>
                  <div class="t-muted">{{ r.run_id }} · 不可恢复</div>
                </div>
              </NPopconfirm>
            </div>
          </div>
        </div>
      </aside>

      <!-- 详情 -->
      <div class="bt-detail">
        <template v-if="selectedRun">
          <!-- 本轮信息 + 图表控制: 一张卡两行, 不再留半空工具条卡 -->
          <div class="detail-head card" data-testid="bt-run-meta">
            <div class="meta-strip">
              <span class="rm"><i>入库</i><b class="num">{{ createdAt }}</b></span>
              <span class="rm"><i>来源</i><b>{{ source }}</b></span>
              <span class="rm"><i>初始资金</i><b class="num">{{ initialCapitalText }}</b></span>
              <span class="rm">
                <GlossaryTip term="bt_data_lineage"><i>数据</i></GlossaryTip>
                <b>本地日线库<template v-if="anyCross"> · 截面特征</template></b>
              </span>
              <span class="rm-div"></span>
              <span class="rm rm-wide">
                <template v-for="(b, i) in targetBadges" :key="i">
                  <GlossaryTip v-if="b.gloss" :term="b.gloss"><span class="type-badge">{{ b.badge }}</span></GlossaryTip><span class="strat-name">{{ b.name }}</span>
                </template>
                <template v-if="anyCross">
                  ·
                  <GlossaryTip term="cs_strategy"><span class="run-target">对象: 全市场抽样池</span></GlossaryTip>
                </template>
                <template v-else-if="targetSymbols.length">
                  · 标的
                  <span v-for="sym in shownSymbols" :key="sym" class="chip-ro">{{ sym }}</span>
                  <span v-if="moreSymbols > 0" class="chip-ro" :title="targetSymbols.join(', ')">+{{ moreSymbols }}</span>
                </template>
              </span>
              <span v-if="truncated" class="rm rm-warn">⚠ 买卖标记仅前 2000 笔 (共 {{ truncated.trade_count }})</span>
            </div>

            <div class="controls-row">
              <label class="ctl">
                <GlossaryTip term="benchmark">基准</GlossaryTip>
                <NSelect
                  v-model:value="benchSel"
                  :options="BENCH_OPTIONS"
                  size="small"
                  style="width: 170px"
                  aria-label="基准"
                  data-testid="bt-benchmark"
                />
              </label>
              <label class="ctl">
                <GlossaryTip term="overlay_run">叠加对比</GlossaryTip>
                <NSelect
                  v-model:value="overlaySel"
                  :options="overlayOptions"
                  size="small"
                  clearable
                  placeholder="无"
                  style="width: 280px"
                  aria-label="叠加对比另一轮回测"
                  data-testid="bt-overlay"
                />
              </label>

              <!-- 基准统计占位: 加载期保留骨架 chip(固定 min-width), 消除控制条宽度跳变 -->
              <span class="bench-slot">
                <span v-if="benchLoading" class="rm rm-note bench-skel" aria-live="polite">基准计算中…</span>
                <template v-else-if="benchInfo.stats">
                  <span class="rm">
                    <i>基准·{{ currentBenchSym }}买入持有</i>
                    <b class="num">{{ pct(benchInfo.stats.benchReturn) }}</b>
                  </span>
                  <span class="rm">
                    <i>{{ benchInfo.stats.alpha >= 0 ? '跑赢基准' : '跑输基准' }}</i>
                    <b class="num" :class="benchInfo.stats.alpha >= 0 ? 't-up' : 't-down'">{{ pct(Math.abs(benchInfo.stats.alpha)) }}</b>
                  </span>
                  <span v-if="benchInfo.stats.fromDate" class="rm rm-note">自 {{ benchInfo.stats.fromDate }} 同窗口径</span>
                </template>
                <span v-else-if="benchInfo.warn" class="rm rm-warn">{{ benchInfo.warn }}</span>
              </span>
              <span v-if="overlayRun && !overlayComputed.anyOverlap" class="rm rm-warn">
                叠加轮与当前区间无重叠日期
              </span>

              <GlossaryTip term="trade_marker">
                <span class="rm rm-note marker-note"><span class="t-buy">▲买</span> <span class="t-sell">▼卖</span> 为实际成交</span>
              </GlossaryTip>
            </div>
          </div>

      <div class="table-wrap card">
        <table data-testid="bt-table">
          <caption class="table-legend t-muted">
            红=正收益/涨，绿=负收益/跌（A股行情色）；夏普等质量指标为中性<template v-if="bestCells.size">；<b class="legend-best">加粗橙底线</b>=该列最优</template>
          </caption>
          <thead>
            <tr>
              <th scope="col">策略</th>
              <th scope="col">区间</th>
              <th scope="col" class="th-num"><GlossaryTip term="total_return">总收益</GlossaryTip></th>
              <th scope="col" class="th-num"><GlossaryTip term="annualized">年化</GlossaryTip></th>
              <th scope="col" class="th-num"><GlossaryTip term="max_drawdown">最大回撤</GlossaryTip></th>
              <th scope="col" class="th-num"><GlossaryTip term="sharpe">夏普</GlossaryTip></th>
              <th scope="col" class="th-num"><GlossaryTip term="sortino">索提诺</GlossaryTip></th>
              <th scope="col" class="th-num"><GlossaryTip term="calmar">Calmar</GlossaryTip></th>
              <th scope="col" class="th-num"><GlossaryTip term="win_rate">胜率</GlossaryTip></th>
              <th scope="col" class="th-num"><GlossaryTip term="trade_count">交易数</GlossaryTip></th>
              <th scope="col" class="th-num"><GlossaryTip term="turnover">换手</GlossaryTip></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in metricRows" :key="ri">
              <td>{{ row.name }}</td>
              <td class="num range-cell">{{ row.range }}</td>
              <td
                v-for="(c, ci) in row.cells"
                :key="ci"
                class="num"
                :class="[c.cls, { 'cell-best': bestCells.has(`${ri}-${ci}`) }]"
              >{{ c.text }}</td>
            </tr>
          </tbody>
        </table>
      </div>

          <EquityChart
            :run="selectedRun"
            :bench-series="benchInfo.series"
            :overlay-lines="overlayComputed.lines"
          />
        </template>
      </div>
    </div>
    <div v-else class="empty t-muted" data-testid="bt-empty">
      <p class="empty-lead">
        还没有回测记录。用上方<b>「新建回测 / 多策略对比」</b>表单选好策略与区间提交，完成后结果会自动出现在这里。
      </p>
      <p class="empty-alt">
        也可命令行运行 <code>python -m src.interfaces.cli.run_backtest</code>，结果同样写入 backtest_runs。
      </p>
    </div>
  </section>
</template>

<style scoped>
/* 工作区: 窄屏堆叠, 宽屏左轨(268px)+右详情; 图表始终随选即见, 不被长列表推走 */
.bt-workspace {
  display: grid;
  gap: var(--gap);
  grid-template-columns: 1fr;
  margin-bottom: var(--gap);
}

.run-rail {
  padding: 10px;
}

.rail-inner {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rail-head {
  align-items: baseline;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  padding: 2px 6px 8px;
}

.rail-title {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.rail-count {
  background: var(--bg-3);
  border-radius: 10px;
  color: var(--text-2);
  font-size: 11.5px;
  padding: 1px 8px;
}

.run-scroll {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 268px;
  overflow-y: auto;
  padding-right: 2px;
}

/* 宽屏双栏(置于基础定义之后, 覆盖生效): 左轨与右详情等高, 底边对齐 */
@media (min-width: 1080px) {
  .bt-workspace {
    /* 默认 align-items:stretch → 两栏底边同线 */
    grid-template-columns: 268px minmax(0, 1fr);
  }

  .run-rail {
    /* detail 空/矮时兜底, 列表不塌陷 */
    min-height: 320px;
    position: relative;
  }

  /* 绝对定位脱离高度计算: 行高只由右侧决定, 左轨填满行高、列表内滚 */
  .rail-inner {
    inset: 10px;
    position: absolute;
  }

  .run-scroll {
    flex: 1;
    max-height: none;
    min-height: 0;
  }
}

/* 行容器: 只做定位锚点(删除钮相对它绝对定位)与激活轨道; 视觉/交互交给内部两真 button */
.run-row {
  border-radius: var(--radius-sm);
  position: relative;
}

/* 主体选择钮: 承接原 .run-row 行样式; 右留白给删除钮, 长标题不被 ✕ 压住 */
.run-select {
  align-items: stretch;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 8px 30px 8px 10px;
  text-align: left;
  transition: background var(--dur-fast) var(--ease-out);
  width: 100%;
}

.run-row:hover .run-select {
  background: var(--accent-soft);
}

.run-row.active .run-select {
  background: var(--accent-soft);
  box-shadow: inset 2px 0 0 var(--accent);
}

/* 删除入口: 常驻透明, hover 该行 或 键盘聚焦(focus-visible) 才显现 —— 真 button,
   键盘可 Tab 到、聚焦即可见可达, 避免列表常态视觉噪音(WCAG 2.1.1/1.4.13) */
.run-delete {
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-3);
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  opacity: 0;
  padding: 3px 6px;
  position: absolute;
  right: 6px;
  top: 8px;
  transition:
    opacity var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
}

.run-row:hover .run-delete,
.run-delete:focus-visible {
  opacity: 1;
}

.run-delete:hover {
  background: color-mix(in srgb, var(--c-fail) 14%, transparent);
  color: var(--c-fail);
}

/* 删除在途(deletingId 接线): 半透明 + 禁点, 防重复触发 */
.run-delete--busy {
  cursor: default;
  opacity: 0.5;
}

/* NPopconfirm 默认插槽是 flex 布局, <br/> 不生效 — 显式 block 分行 */
.confirm-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-width: 260px;
}

/* 人话标题为主行(设计 0705 §3.B) — 机器 run_id 降级到副行小字, 不再是主标题 */
.run-title {
  font-size: 13px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-row-bottom {
  align-items: baseline;
  display: flex;
  gap: 8px;
  justify-content: space-between;
  min-width: 0;
}

.run-subtitle {
  color: var(--text-3);
  flex: 1;
  font-size: 11px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* F-03: 原 opacity 0.75 把 run-id 拉到 3.97(暗)/3.22(亮), 去透明度回 text-3 实色(5.98/5.36);
   层级弱于主标题靠字号(10.5px vs 13px)与 text-3 维持 */
.run-id {
  color: var(--text-3);
  flex: none;
  font-size: 10.5px;
}

/* 激活/悬停行换 accent-soft 合成底(暗 #392a24 / 亮 #efe1d7), text-3 只剩 4.90/4.80 边缘、
   带透明度的 run-id 曾低至 3.43 — 小字整体抬 text-2: 暗 9.19 / 亮 7.07(F-03) */
.run-row:hover .run-subtitle,
.run-row:hover .run-id,
.run-row.active .run-subtitle,
.run-row.active .run-id {
  color: var(--text-2);
}

.empty {
  font-size: 13px;
  margin-bottom: var(--gap);
  padding: 18px 6px;
}

.empty code {
  color: var(--accent-blue);
  font-size: 12px;
}

.empty-lead {
  margin: 0 0 6px;
}

.empty-alt {
  font-size: 12px;
  margin: 0;
  opacity: 0.85;
}

/* 本轮信息+图表控制 一卡两行: 上=meta, 下=控制条(分隔线隔开) */
.detail-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: var(--gap);
  padding: 12px 16px;
}

.meta-strip {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
}

.controls-row {
  align-items: center;
  border-top: 1px solid var(--border);
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  padding-top: 10px;
}

.ctl {
  align-items: center;
  color: var(--text-3);
  display: inline-flex;
  font-size: 12.5px;
  gap: 8px;
}

.marker-note {
  margin-left: auto;
}

.rm {
  align-items: baseline;
  display: inline-flex;
  gap: 6px;
}

.rm i {
  color: var(--text-3);
  font-size: 12px;
  font-style: normal;
}

.rm b {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
}

.rm-wide {
  flex-wrap: wrap;
  gap: 4px;
}

.rm-div {
  background: var(--border);
  height: 16px;
  width: 1px;
}

.rm-warn {
  color: var(--c-warn);
  font-size: 12px;
}

.rm-note {
  color: var(--text-3);
  font-size: 11.5px;
}

/* 基准统计占位槽: 固定 min-width, 加载/有值/警示三态切换不塌陷、控制条不抖 */
.bench-slot {
  align-items: baseline;
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  min-width: 240px;
}

.bench-skel {
  opacity: 0.7;
}

.type-badge {
  color: var(--accent-blue);
  font-family: var(--font-display);
  font-size: 11.5px;
  font-weight: 700;
}

.strat-name {
  font-size: 13px;
  margin-right: 4px;
}

.run-target {
  color: var(--text-2);
  font-size: 12.5px;
}

.chip-ro {
  background: var(--bg-3);
  border-radius: 12px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  padding: 1px 8px;
}

.table-wrap {
  margin-bottom: var(--gap);
  overflow-x: auto;
  padding: 6px 10px;
}

.table-legend {
  caption-side: top;
  font-size: var(--fs-xs);
  padding: 2px 0 var(--space-2);
  text-align: left;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th {
  border-bottom: 1px solid var(--border);
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 11.5px;
  padding: 8px 9px;
  text-align: left;
  white-space: nowrap;
}

td {
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  padding: 7px 9px;
  white-space: nowrap;
}

/* 量化指标列右对齐: 小数点/百分号纵向对位, 便于多策略竖排比较 */
th.th-num {
  text-align: right;
}

td.num:not(.range-cell) {
  text-align: right;
}

.range-cell {
  color: var(--text-3);
  font-size: 12px;
}

/* 每列最优(仅多策略同轮对比时标): 2px accent 底线 + 稍重字重 — 只动边线与字重、
   不动文字色, 不与涨跌红绿打架; 沿用 .run-row.active 的 accent 标记语言 */
td.cell-best {
  border-bottom: 2px solid var(--accent);
  font-weight: 600;
}

/* 图例小样: 与单元格标记同款视觉, 见样知义 */
.legend-best {
  border-bottom: 2px solid var(--accent);
  color: inherit;
  font-weight: 600;
}
</style>
