<script setup lang="ts">
import { NSelect } from 'naive-ui'
import { computed, ref, shallowRef, watch } from 'vue'

import { fetchJSON } from '@/api/fetch'
import type { BacktestRun, BarsData, StrategyMeta } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'

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
const runs = ref<BacktestRun[]>([])
const strategyMeta = ref<StrategyMeta[]>([])
const selectedRunId = ref<string | null>(null)
const benchSel = ref('first_symbol')
const overlaySel = ref<number | null>(null)

const selectedRun = computed(() => runs.value.find((r) => r.run_id === selectedRunId.value) ?? null)
const first = computed(() => (selectedRun.value ? (firstStrategy(selectedRun.value) ?? null) : null))

function typeOf(name: string): string | undefined {
  return strategyMeta.value.find((s) => s.name === name)?.strategy_type
}

async function loadBacktests(): Promise<void> {
  try {
    const data = await fetchJSON<{ runs: BacktestRun[] }>('/api/research/backtests')
    runs.value = data.runs
    // 载入/刷新后选中最新(倒序首条), 对等旧版 currentBtRun = btRuns[0]
    selectedRunId.value = runs.value[0]?.run_id ?? null
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
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

// ---- 基准: 同额买入持有(异步取 /bars 现算, seq 守卫过期丢弃) ----
const benchRaw = shallowRef<{ series: (number | null)[] | null; note: string }>({
  series: null,
  note: '',
})
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
  if (!fst || !sym || !dates.length) return
  const mySeq = ++benchSeq
  try {
    const bars = await fetchJSON<BarsData>(
      `/api/research/bars/${sym}?start=${dates[0]}&end=${dates[dates.length - 1]}`,
    )
    if (mySeq !== benchSeq) return // 切换详情后迟到响应丢弃
    const closes = bars.ohlc.map((o) => o[1]) // ECharts 约定 [o,c,l,h]
    const series = buildBenchmarkValues(dates, bars.dates, closes, fst.initial_capital)
    benchRaw.value = { series, note: series ? '' : `基准 ${sym} 无本地行情` }
  } catch {
    if (mySeq !== benchSeq) return
    benchRaw.value = { series: null, note: '基准行情加载失败' }
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
const overlayOptions = computed(() =>
  runs.value.map((r, i) => ({
    label: `${r.run_id}（${r.strategies.map((s) => s.strategy).join(', ')}）`,
    value: i,
  })),
)
const overlayRun = computed(() => {
  if (overlaySel.value === null) return null
  const r = runs.value[overlaySel.value]
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
const source = computed(() => String(first.value?.params?.source ?? '?'))
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
interface Cell {
  text: string
  cls: string
}
function signedCell(v: number | null, fmt: (x: number) => string): Cell {
  if (v === null || v === undefined) return { text: '-', cls: 't-muted' }
  // 正=好(绿 t-pass) 负=差(红 t-fail) — 判定语义, 非行情涨跌
  return { text: fmt(v), cls: v > 0 ? 't-pass' : v < 0 ? 't-fail' : '' }
}
function plainCell(v: number | null, fmt: (x: number) => string, cls = ''): Cell {
  return { text: v === null || v === undefined ? '-' : fmt(v), cls }
}
const metricRows = computed(() =>
  (selectedRun.value?.strategies ?? []).map((s) => ({
    name: s.strategy,
    range: `${s.start_date ?? '?'} ~ ${s.end_date ?? '?'}`,
    cells: [
      signedCell(s.total_return, pct),
      signedCell(s.annualized_return, pct),
      plainCell(
        s.max_drawdown,
        pct,
        s.max_drawdown !== null && s.max_drawdown > 0.2 ? 't-fail' : '',
      ),
      signedCell(s.sharpe_ratio, f3),
      signedCell(s.sortino_ratio, f3),
      signedCell(s.calmar_ratio, f3),
      plainCell(s.win_rate, pct),
      { text: s.trade_count === null || s.trade_count === undefined ? '-' : String(s.trade_count), cls: '' },
      plainCell(s.turnover_rate, pct),
    ] as Cell[],
  })),
)

function onFormDone(): void {
  void loadBacktests()
}
</script>

<template>
  <section data-testid="page-backtests">
    <header class="page-head"><h2>回测</h2></header>
    <p class="guide t-muted">
      把策略放回历史行情模拟交易。<GlossaryTip term="ts_strategy">时序策略</GlossaryTip>（如双均线）回测你填的标的；<GlossaryTip
        term="cs_strategy"
        >截面策略</GlossaryTip
      >（如小市值）在全市场抽样池上选股，标的框不生效。提交后任务卡实时滚日志，完成自动刷新下方结果。
    </p>

    <ErrorBanner v-if="error" :msg="error" />

    <BacktestForm :strategy-meta="strategyMeta" @done="onFormDone" />

    <!-- 回测列表: 倒序, 行点击进详情 -->
    <div v-if="runs.length" class="runs card">
      <button
        v-for="r in runs"
        :key="r.run_id"
        type="button"
        class="run-row"
        :class="{ active: r.run_id === selectedRunId }"
        data-testid="bt-run-row"
        @click="selectRun(r.run_id)"
      >
        <span class="run-id num">{{ r.run_id }}</span>
        <span class="run-strats">
          <span v-for="(s, i) in r.strategies" :key="i" class="run-strat">{{ s.strategy }}</span>
        </span>
        <span class="run-date num">{{ (r.created_at ?? '').slice(0, 19) }}</span>
      </button>
    </div>
    <p v-else class="empty t-muted" data-testid="bt-empty">
      暂无回测入库 — 运行 <code>python -m src.interfaces.cli.run_backtest</code> 后自动写入 backtest_runs。
    </p>

    <!-- 详情 -->
    <template v-if="selectedRun">
      <div class="toolbar card">
        <label>
          <GlossaryTip term="benchmark">基准</GlossaryTip>
          <NSelect
            v-model:value="benchSel"
            :options="BENCH_OPTIONS"
            size="small"
            style="width: 180px"
            data-testid="bt-benchmark"
          />
        </label>
        <label>
          <GlossaryTip term="overlay_run">叠加对比</GlossaryTip>
          <NSelect
            v-model:value="overlaySel"
            :options="overlayOptions"
            size="small"
            clearable
            placeholder="无"
            style="width: 300px"
            data-testid="bt-overlay"
          />
        </label>
      </div>

      <div class="meta-strip card" data-testid="bt-run-meta">
        <span class="rm"><i>入库</i><b class="num">{{ createdAt }}</b></span>
        <span class="rm"><i>来源</i><b>{{ source }}</b></span>
        <span class="rm"><i>初始资金</i><b class="num">{{ initialCapitalText }}</b></span>
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

        <template v-if="benchInfo.stats">
          <span class="rm-div"></span>
          <span class="rm">
            <GlossaryTip term="benchmark"><i>基准·{{ currentBenchSym }}买入持有</i></GlossaryTip>
            <b class="num">{{ pct(benchInfo.stats.benchReturn) }}</b>
          </span>
          <span class="rm">
            <i>超额</i>
            <b class="num" :class="benchInfo.stats.alpha >= 0 ? 't-pass' : 't-fail'">{{ pct(benchInfo.stats.alpha) }}</b>
          </span>
          <span v-if="benchInfo.stats.fromDate" class="rm rm-note">自 {{ benchInfo.stats.fromDate }} 同窗口径</span>
        </template>
        <span v-else-if="benchInfo.warn" class="rm rm-warn">{{ benchInfo.warn }}</span>

        <span v-if="overlayRun && !overlayComputed.anyOverlap" class="rm rm-warn">
          叠加轮与当前区间无重叠日期
        </span>
      </div>

      <div class="table-wrap card">
        <table data-testid="bt-table">
          <thead>
            <tr>
              <th>策略</th>
              <th>区间</th>
              <th><GlossaryTip term="total_return">总收益</GlossaryTip></th>
              <th><GlossaryTip term="annualized">年化</GlossaryTip></th>
              <th><GlossaryTip term="max_drawdown">最大回撤</GlossaryTip></th>
              <th><GlossaryTip term="sharpe">夏普</GlossaryTip></th>
              <th><GlossaryTip term="sortino">索提诺</GlossaryTip></th>
              <th><GlossaryTip term="calmar">Calmar</GlossaryTip></th>
              <th><GlossaryTip term="win_rate">胜率</GlossaryTip></th>
              <th><GlossaryTip term="trade_count">交易数</GlossaryTip></th>
              <th><GlossaryTip term="turnover">换手</GlossaryTip></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in metricRows" :key="ri">
              <td>{{ row.name }}</td>
              <td class="num range-cell">{{ row.range }}</td>
              <td v-for="(c, ci) in row.cells" :key="ci" class="num" :class="c.cls">{{ c.text }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="chart-caption t-muted">
        <GlossaryTip term="trade_marker"><span class="marker-legend"><span class="t-buy">▲买</span> <span class="t-sell">▼卖</span> 为实际成交</span></GlossaryTip>
      </p>
      <EquityChart
        :run="selectedRun"
        :bench-series="benchInfo.series"
        :overlay-lines="overlayComputed.lines"
      />
    </template>
  </section>
</template>

<style scoped>
.page-head {
  align-items: baseline;
  display: flex;
  gap: 14px;
  margin-bottom: 6px;
}

.page-head h2 {
  margin: 0;
}

.guide {
  font-size: 13px;
  margin: 0 0 var(--gap);
}

.runs {
  display: flex;
  flex-direction: column;
  margin-bottom: var(--gap);
  padding: 6px;
}

.run-row {
  align-items: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text);
  cursor: pointer;
  display: flex;
  gap: 14px;
  padding: 9px 12px;
  text-align: left;
  transition: background var(--dur-fast) var(--ease-out);
  width: 100%;
}

.run-row:hover {
  background: var(--accent-soft);
}

.run-row.active {
  background: var(--accent-soft);
  box-shadow: inset 2px 0 0 var(--accent);
}

.run-id {
  color: var(--accent-blue);
  font-size: 12.5px;
  flex: none;
}

.run-strats {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.run-strat {
  background: var(--bg-3);
  border-radius: var(--radius-sm);
  font-size: 12px;
  padding: 1px 8px;
}

.run-date {
  color: var(--text-3);
  flex: none;
  font-size: 12px;
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

.toolbar {
  align-items: end;
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap);
  margin-bottom: var(--gap);
  padding: 12px 16px;
}

.toolbar label {
  color: var(--text-3);
  display: flex;
  flex-direction: column;
  font-size: 12.5px;
  gap: 6px;
}

.meta-strip {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin-bottom: var(--gap);
  padding: 10px 16px;
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

.type-badge {
  color: var(--accent);
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

.range-cell {
  color: var(--text-3);
  font-size: 12px;
}

.chart-caption {
  font-size: 12px;
  margin: 0 0 6px;
}

.marker-legend {
  font-size: 12px;
}
</style>
