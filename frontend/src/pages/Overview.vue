<script setup lang="ts">
import { NButton, NDatePicker } from 'naive-ui'
import { computed, ref } from 'vue'

import { fetchJSON, postJSON } from '@/api/fetch'
import type { BacktestRun, Job, OverviewData, StrategyMeta, VerdictRun } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import JobCard from '@/components/JobCard.vue'
import KpiCard from '@/components/KpiCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import PipelineMap from '@/components/PipelineMap.vue'

import { backtestActivity, latestOf, verdictActivity } from './overview/recent-activity'

/* 数据资产总览 — 旧 pages/overview.js 对等:
 * 单次加载 /api/research/overview; 四表卡片; 空态; 数据刷新表单(data-refresh job)。 */

const TABLE_LABELS: Record<string, string> = {
  instruments: '股票池',
  bars: '日线行情',
  fundamental_snapshots: '基本面快照',
  stock_features: '截面特征',
}
// 主数值单位: 行数表标"行", 股票池主值即标的数标"只"
const TABLE_UNITS: Record<string, string> = {
  instruments: '只',
  bars: '行',
  fundamental_snapshots: '行',
  stock_features: '行',
}

const data = ref<OverviewData | null>(null)
const loading = ref(true)
const error = ref('')

async function load(): Promise<void> {
  try {
    data.value = await fetchJSON<OverviewData>('/api/research/overview')
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

void load()

const totalRows = computed(() =>
  Object.values(data.value?.tables ?? {}).reduce((acc, s) => acc + s.rows, 0),
)

const metaLine = computed(() => {
  if (!data.value) return ''
  return data.value.db_exists
    ? `判决轮次 ${data.value.verdict_runs} · 特征版本 v${data.value.feature_version} · ${data.value.db_path}`
    : '数据库不存在'
})

/* 副行语义: 股票池的区间是"上市日期", 其余表是"数据覆盖" — 两种含义显式标注不混淆 */
function subOf(table: string, s: { symbols: number; min_date: string | null; max_date: string | null }): string {
  const range = s.min_date ? `${s.min_date} ~ ${s.max_date}` : '—'
  if (table === 'instruments') return `上市日期 ${range}`
  return `${s.symbols.toLocaleString()} 只标的 · 数据覆盖 ${range}`
}

/* ---- 最近动态(发射台): 最新判决轮/回测轮, 整卡深链直达对应详情 ----
 * 附加区不拖垮总览主体: 任一端点失败 → 静默藏对应卡(双双失败整区不渲染), 不占 ErrorBanner;
 * meta 失败仅降级策略命名(buildRunLabel 回退原名), 不藏回测卡。 */
const verdictRuns = ref<VerdictRun[] | null>(null)
const backtestRuns = ref<BacktestRun[] | null>(null)
const strategyMeta = ref<StrategyMeta[]>([])

async function loadActivity(): Promise<void> {
  const [v, b, m] = await Promise.allSettled([
    fetchJSON<{ runs: VerdictRun[] }>('/api/research/verdicts'),
    fetchJSON<{ runs: BacktestRun[] }>('/api/research/backtests'),
    fetchJSON<{ strategies: StrategyMeta[] }>('/api/meta/strategies'),
  ])
  if (v.status === 'fulfilled') verdictRuns.value = v.value.runs
  if (b.status === 'fulfilled') backtestRuns.value = b.value.runs
  if (m.status === 'fulfilled') strategyMeta.value = m.value.strategies
}

void loadActivity()

const verdictCard = computed(() => {
  const run = verdictRuns.value ? latestOf(verdictRuns.value) : null
  return run ? verdictActivity(run) : null
})

const backtestCard = computed(() => {
  const run = backtestRuns.value ? latestOf(backtestRuns.value) : null
  return run ? backtestActivity(run, strategyMeta.value) : null
})

// ---- 数据刷新表单(旧 initRefreshForm 对等) ----
const drStart = ref<string | null>(null)
const drEnd = ref<string | null>(null)
const submitting = ref(false)
const refreshJobIds = ref<string[]>([])

async function submitRefresh(): Promise<void> {
  error.value = ''
  submitting.value = true
  try {
    const job = await postJSON<Job>('/api/jobs/data-refresh', {
      start_date: drStart.value ?? '',
      end_date: drEnd.value ?? '',
    })
    refreshJobIds.value.unshift(job.job_id)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    submitting.value = false
  }
}

function onRefreshDone(): void {
  void load()
}
</script>

<template>
  <section data-testid="page-overview">
    <PageHeader title="数据资产总览" :meta="metaLine">
      本系统的研究工作是一条流水线：数据资产喂给因子判决，过闸因子组成策略去回测，回测通过的策略上纸面（实盘 dry_run）验证。下方四步即对应四个页签，点击可直接跳转。
    </PageHeader>

    <PipelineMap :overview="data" />

    <ErrorBanner v-if="error" :msg="error" />

    <p v-if="data && totalRows === 0" class="t-muted" data-testid="overview-empty">
      暂无数据 — 先运行下方数据刷新（或 quant data refresh）。
    </p>

    <!-- 加载骨架: 固定高度占位, 数据到达不跳版 -->
    <div v-if="loading && !data" class="kpi-row">
      <div v-for="i in 4" :key="i" class="card kpi-skeleton"></div>
    </div>

    <p v-if="data" class="section-label t-muted">
      本地行情库（DuckDB）四张核心表 — 流水线①"数据资产"的明细
    </p>
    <div v-if="data" class="kpi-row">
      <KpiCard
        v-for="(stat, table) in data.tables"
        :key="table"
        :label="TABLE_LABELS[table] ?? String(table)"
        :value="stat.rows"
        :unit="TABLE_UNITS[table] ?? ''"
        count-up
        :sub="subOf(String(table), stat)"
      />
    </div>

    <!-- 最近动态(发射台): 总览下半不再空白 — 最新判决/回测一眼可见, 整卡深链直达详情;
         端点失败静默藏卡(不占 ErrorBanner), 空库显引导空态 -->
    <template v-if="verdictRuns || backtestRuns">
      <p class="section-label t-muted">最近动态 — 最新一轮判决与回测，点击卡片直达详情</p>
      <div class="activity-row" data-testid="recent-activity">
        <RouterLink
          v-if="verdictCard"
          class="card card--hoverable activity-card"
          :to="{ name: 'verdicts', query: { run: verdictCard.runId } }"
          data-testid="activity-verdict"
        >
          <span class="activity-kicker">最新判决轮</span>
          <span class="activity-main">
            {{ verdictCard.factorCount }} 因子 ·
            <b class="t-pass">PASS {{ verdictCard.passCount }}</b><span class="t-muted"> / </span><b class="t-fail">FAIL {{ verdictCard.failCount }}</b>
          </span>
          <span class="activity-sub t-muted">{{ verdictCard.splitText }} · 入库 <span class="num">{{ verdictCard.createdAt }}</span></span>
        </RouterLink>
        <RouterLink
          v-else-if="verdictRuns"
          class="card card--hoverable activity-card"
          :to="{ name: 'verdicts' }"
          data-testid="activity-verdict-empty"
        >
          <span class="activity-kicker">最新判决轮</span>
          <span class="activity-main t-muted">暂无判决记录 — 去提交第一轮</span>
        </RouterLink>

        <RouterLink
          v-if="backtestCard"
          class="card card--hoverable activity-card"
          :to="{ name: 'backtests', query: { run: backtestCard.runId } }"
          data-testid="activity-backtest"
        >
          <span class="activity-kicker">最新回测轮</span>
          <span class="activity-main">
            {{ backtestCard.title }} ·
            <b class="num" :class="backtestCard.ret.cls">{{ backtestCard.ret.text }}</b>
          </span>
          <span class="activity-sub t-muted">入库 <span class="num">{{ backtestCard.createdAt }}</span></span>
        </RouterLink>
        <RouterLink
          v-else-if="backtestRuns"
          class="card card--hoverable activity-card"
          :to="{ name: 'backtests' }"
          data-testid="activity-backtest-empty"
        >
          <span class="activity-kicker">最新回测轮</span>
          <span class="activity-main t-muted">暂无回测记录 — 去提交第一轮</span>
        </RouterLink>
      </div>
    </template>

    <details class="card form-card" :open="data !== null && totalRows === 0">
      <summary>数据刷新（QMT 增量, 只刷缺口）</summary>
      <div class="form-row">
        <label>起始 <NDatePicker v-model:formatted-value="drStart" value-format="yyyy-MM-dd" type="date" clearable data-testid="dr-start" /></label>
        <label>结束 <NDatePicker v-model:formatted-value="drEnd" value-format="yyyy-MM-dd" type="date" clearable data-testid="dr-end" /></label>
        <NButton type="primary" :loading="submitting" :disabled="submitting" data-testid="dr-submit" @click="submitRefresh">提交刷新任务</NButton>
      </div>
      <p class="form-help t-muted">留空 = 按库内缺口自动补齐（默认全区间）；需 QMT 客户端在线。</p>
      <div data-testid="dr-job-area">
        <JobCard v-for="id in refreshJobIds" :key="id" :job-id="id" @done="onRefreshDone" />
      </div>
    </details>
  </section>
</template>

<style scoped>
.section-label {
  font-size: 12px;
  margin: 0 0 8px;
}

.kpi-row {
  display: grid;
  gap: var(--gap);
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  margin-bottom: var(--gap);
}

.kpi-skeleton {
  animation: skeleton-pulse 1.4s ease-in-out infinite;
  min-height: 92px;
}

@keyframes skeleton-pulse {
  50% {
    opacity: 0.55;
  }
}

/* 最近动态: 两张发射台小卡并排(窄屏自动堆叠) — 整卡即 RouterLink */
.activity-row {
  display: grid;
  gap: var(--gap);
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  margin-bottom: var(--gap);
}

/* 覆盖全局 a 基础样式: 卡内正文用文字色, 悬停不整卡变淡(反馈交给 .card--hoverable 抬升) */
.activity-card {
  color: var(--text);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
}

.activity-card:hover {
  opacity: 1;
}

.activity-kicker {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
}

.activity-main {
  font-size: var(--fs-base);
  line-height: var(--lh-base);
}

.activity-main b {
  font-family: var(--font-display);
  font-weight: 600;
}

.activity-sub {
  font-size: var(--fs-sm);
}

.form-card {
  max-width: 720px;
}

.form-help {
  font-size: 12px;
  margin: 6px 0 0;
}

.form-card summary {
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
}

.form-row {
  align-items: end;
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap);
  margin: 14px 0;
}

.form-row label {
  color: var(--text-3);
  display: flex;
  flex-direction: column;
  font-size: 12.5px;
  gap: 6px;
}
</style>
