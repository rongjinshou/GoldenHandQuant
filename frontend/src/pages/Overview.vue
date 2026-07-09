<script setup lang="ts">
import { NButton, NDatePicker } from 'naive-ui'
import { computed, ref } from 'vue'

import { fetchJSON, postJSON } from '@/api/fetch'
import type { Job, OverviewData } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import JobCard from '@/components/JobCard.vue'
import KpiCard from '@/components/KpiCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import PipelineMap from '@/components/PipelineMap.vue'

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
