<script setup lang="ts">
import { NButton, NDatePicker } from 'naive-ui'
import { computed, ref } from 'vue'

import { fetchJSON, postJSON } from '@/api/fetch'
import type { Job, OverviewData } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import JobCard from '@/components/JobCard.vue'
import KpiCard from '@/components/KpiCard.vue'

/* 数据资产总览 — 旧 pages/overview.js 对等:
 * 单次加载 /api/research/overview; 四表卡片; 空态; 数据刷新表单(data-refresh job)。 */

const TABLE_LABELS: Record<string, string> = {
  instruments: '股票池',
  bars: '日线行情',
  fundamental_snapshots: '基本面快照',
  stock_features: '截面特征',
}

const data = ref<OverviewData | null>(null)
const error = ref('')

async function load(): Promise<void> {
  try {
    data.value = await fetchJSON<OverviewData>('/api/research/overview')
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  }
}

void load()

const totalRows = computed(() =>
  Object.values(data.value?.tables ?? {}).reduce((acc, s) => acc + s.rows, 0),
)

const metaLine = computed(() => {
  if (!data.value) return ''
  return data.value.db_exists
    ? `判决轮次 ${data.value.verdict_runs} · 特征版本 v${data.value.feature_version}`
    : '数据库不存在'
})

function rangeOf(s: { min_date: string | null; max_date: string | null }): string {
  // 股票池等静态表没有日期区间, 显示 "—" 而非误导性的 "无数据"
  return s.min_date ? `${s.min_date} ~ ${s.max_date}` : '—'
}

// ---- 数据刷新表单(旧 initRefreshForm 对等) ----
const drStart = ref<string | null>(null)
const drEnd = ref<string | null>(null)
const refreshJobIds = ref<string[]>([])

async function submitRefresh(): Promise<void> {
  error.value = ''
  try {
    const job = await postJSON<Job>('/api/jobs/data-refresh', {
      start_date: drStart.value ?? '',
      end_date: drEnd.value ?? '',
    })
    refreshJobIds.value.unshift(job.job_id)
  } catch (e) {
    error.value = (e as Error).message
  }
}

function onRefreshDone(): void {
  void load()
}
</script>

<template>
  <section data-testid="page-overview">
    <header class="page-head">
      <h2>数据资产总览</h2>
      <span v-if="metaLine" class="t-muted meta-line">{{ metaLine }}</span>
    </header>

    <ErrorBanner v-if="error" :msg="error" />

    <p v-if="data && totalRows === 0" class="t-muted" data-testid="overview-empty">
      数据库为空 — 先运行数据刷新（下方表单或 quant data refresh）
    </p>

    <div v-if="data" class="kpi-row">
      <KpiCard
        v-for="(stat, table) in data.tables"
        :key="table"
        :label="TABLE_LABELS[table] ?? String(table)"
        :value="stat.rows"
        count-up
        :sub="`${stat.symbols.toLocaleString()} 只标的 · ${rangeOf(stat)}`"
      />
    </div>

    <p v-if="data" class="t-muted db-path num">{{ data.db_path }}</p>

    <details class="card form-card">
      <summary>数据刷新（QMT 增量, 只刷缺口）</summary>
      <div class="form-row">
        <label>起始 <NDatePicker v-model:formatted-value="drStart" value-format="yyyy-MM-dd" type="date" clearable data-testid="dr-start" /></label>
        <label>结束 <NDatePicker v-model:formatted-value="drEnd" value-format="yyyy-MM-dd" type="date" clearable data-testid="dr-end" /></label>
        <NButton type="primary" data-testid="dr-submit" @click="submitRefresh">提交刷新任务</NButton>
      </div>
      <div data-testid="dr-job-area">
        <JobCard v-for="id in refreshJobIds" :key="id" :job-id="id" @done="onRefreshDone" />
      </div>
    </details>
  </section>
</template>

<style scoped>
.page-head {
  align-items: baseline;
  display: flex;
  gap: 14px;
  margin-bottom: var(--gap);
}

.page-head h2 {
  margin: 0;
}

.meta-line {
  font-size: 13px;
}

.kpi-row {
  display: grid;
  gap: var(--gap);
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  margin-bottom: var(--gap);
}

.db-path {
  font-size: 12px;
  margin: 0 0 var(--gap-lg);
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
