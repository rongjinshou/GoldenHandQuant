<script setup lang="ts">
import { NButton, NDatePicker, NInput, NInputNumber } from 'naive-ui'
import { computed, nextTick, onUnmounted, ref } from 'vue'

import { fetchJSON, postJSON } from '@/api/fetch'
import type { Job } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import JobCard from '@/components/JobCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import { usePolling } from '@/composables/usePolling'
import { useJobsStore } from '@/stores/jobs'

import { STATUS_LABEL, TERMINAL_STATUS, durationOf, paramsSummary } from './jobs/format'

/* 任务中心 — 旧 jobs.js loadJobsPage/showJobLog/initMlForms 对等:
 * 列表 5s 轮询 + 活跃数写回 store; 行点击日志钻取(2s 轮询/终态停/5 连败停);
 * 取消静默容错后刷列表; ML 训练/评估表单 + JobCard 闭环(done 仅成功触发刷新)。 */

interface JobsListResponse {
  jobs: Job[]
  active: boolean
}

const jobsStore = useJobsStore()
const error = ref('')

const {
  data: listData,
  error: listError,
  refresh,
} = usePolling<JobsListResponse>(
  async () => {
    const d = await fetchJSON<JobsListResponse>('/api/jobs?limit=100')
    // 顶栏徽章与 503 写锁文案都靠这笔写回
    jobsStore.setActive(
      d.jobs.filter((j) => j.status === 'queued' || j.status === 'running').length,
    )
    return d
  },
  { intervalMs: 5000 },
)

const jobs = computed(() => listData.value?.jobs ?? [])
const bannerMsg = computed(() => error.value || listError.value?.message || '')

async function cancelJob(id: string): Promise<void> {
  try {
    await postJSON(`/api/jobs/${id}/cancel`)
  } catch {
    /* 已结束(404/409) — 对等旧版静默 */
  }
  void refresh()
}

// ---- 日志钻取面板(旧 showJobLog 对等) ----
const selectedId = ref<string | null>(null)
const logTitle = ref('')
const logText = ref('选择任务查看日志')
const logLive = ref(false)
const logEl = ref<HTMLPreElement | null>(null)
// 零任务时终端框纯噪音 — 占位文案联动引导, 不藏区块保布局稳定
const logDisplay = computed(() =>
  listData.value && jobs.value.length === 0 && selectedId.value === null
    ? '暂无任务，提交后此处显示实时日志'
    : logText.value,
)
let logTimer: ReturnType<typeof setInterval> | null = null
let logSeq = 0 // 切换任务后丢弃前一任务迟到响应

function stopLogPolling(): void {
  logLive.value = false
  if (logTimer !== null) {
    clearInterval(logTimer)
    logTimer = null
  }
}

function openLog(jobId: string): void {
  stopLogPolling()
  selectedId.value = jobId
  const mySeq = ++logSeq
  let failCount = 0
  logLive.value = true

  async function tick(): Promise<void> {
    let job: Job
    try {
      job = await fetchJSON<Job>(`/api/jobs/${jobId}?tail=300`)
    } catch {
      if (mySeq !== logSeq) return
      failCount += 1
      // 连续 5 次失败停轮询并提示(对等旧 Fix #3)
      if (failCount >= 5) {
        stopLogPolling()
        logText.value = '任务查询失败（服务可能已重启）'
      }
      return
    }
    if (mySeq !== logSeq) return
    failCount = 0
    logTitle.value = `${jobId} · ${STATUS_LABEL[job.status] ?? job.status}`
    logText.value = (job.log_tail ?? []).join('\n') || '（无输出）'
    if (TERMINAL_STATUS.has(job.status)) stopLogPolling()
    await nextTick()
    if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight // 滚动跟随
  }

  void tick()
  logTimer = setInterval(() => void tick(), 2000)
}

onUnmounted(stopLogPolling)

// ---- ML 训练/评估表单(旧 initMlForms 对等, 默认值照旧 HTML) ----
const mlStart = ref<string | null>('2021-01-01')
const mlEnd = ref<string | null>('2024-12-31')
const mlSymbols = ref('000300.SH')
const mlModel = ref('lgbm_return_5d') // 训练/评估共用同一模型名输入(对等旧 #ml-model)
const mlTrials = ref<number | null>(50)
const mleStart = ref<string | null>('2025-01-01')
const mleEnd = ref<string | null>('2025-12-31')
const mlJobIds = ref<string[]>([])

async function submitTrain(): Promise<void> {
  error.value = ''
  try {
    const job = await postJSON<Job>('/api/jobs/ml-train', {
      start_date: mlStart.value ?? '',
      end_date: mlEnd.value ?? '',
      symbols: mlSymbols.value.trim(),
      model_name: mlModel.value.trim(),
      n_trials: Number(mlTrials.value),
    })
    mlJobIds.value.unshift(job.job_id)
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function submitEval(): Promise<void> {
  error.value = ''
  try {
    const job = await postJSON<Job>('/api/jobs/ml-evaluate', {
      model_name: mlModel.value.trim(),
      eval_start: mleStart.value ?? '',
      eval_end: mleEnd.value ?? '',
    })
    mlJobIds.value.unshift(job.job_id)
  } catch (e) {
    error.value = (e as Error).message
  }
}

function onMlDone(): void {
  void refresh() // done 仅 succeeded 触发(JobCard 语义), 对等旧 onDone 刷列表
}
</script>

<template>
  <section data-testid="page-jobs">
    <PageHeader title="任务中心">
      网页触发的所有后台任务——点击行查看实时日志，排队/运行中可取消。<GlossaryTip
        term="ml_train"
        >ML 训练</GlossaryTip
      >属高级功能，耗时可达数十分钟。
    </PageHeader>

    <ErrorBanner v-if="bannerMsg" :msg="bannerMsg" />

    <details class="card form-card">
      <summary>ML 模型训练 / 评估（高级）</summary>
      <div class="form-row">
        <label>训练起 <NDatePicker v-model:formatted-value="mlStart" value-format="yyyy-MM-dd" type="date" clearable data-testid="ml-start" /></label>
        <label>训练止 <NDatePicker v-model:formatted-value="mlEnd" value-format="yyyy-MM-dd" type="date" clearable data-testid="ml-end" /></label>
        <label>标的 <NInput v-model:value="mlSymbols" style="width: 140px" data-testid="ml-symbols" /></label>
        <label><GlossaryTip term="model_name">模型名</GlossaryTip> <NInput v-model:value="mlModel" style="width: 170px" data-testid="ml-model" /></label>
        <label><GlossaryTip term="n_trials">调参次数 (n-trials)</GlossaryTip> <NInputNumber v-model:value="mlTrials" :min="1" :max="200" style="width: 100px" data-testid="ml-trials" /></label>
        <NButton type="primary" class="row-end" data-testid="ml-train-submit" @click="submitTrain">训练</NButton>
      </div>
      <div class="form-row">
        <label>评估起 <NDatePicker v-model:formatted-value="mleStart" value-format="yyyy-MM-dd" type="date" clearable data-testid="mle-start" /></label>
        <label>评估止 <NDatePicker v-model:formatted-value="mleEnd" value-format="yyyy-MM-dd" type="date" clearable data-testid="mle-end" /></label>
        <!-- 评估静默复用首行「模型名」— 常驻小字把依赖显式化, 避免评错模型; 评估降为次级钮与训练分主次 -->
        <div class="row-end eval-group">
          <span class="t-muted eval-model-hint" data-testid="ml-eval-model">评估模型：{{ mlModel || '未填' }}</span>
          <NButton data-testid="ml-eval-submit" @click="submitEval">评估</NButton>
        </div>
      </div>
    </details>

    <div data-testid="ml-job-area">
      <JobCard v-for="id in mlJobIds" :key="id" :job-id="id" @done="onMlDone" />
    </div>

    <h3 class="section-title">任务列表</h3>
    <div class="table-wrap card">
      <table data-testid="jobs-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>类型</th>
            <th>参数</th>
            <th>状态</th>
            <th>创建</th>
            <th>耗时</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="j in jobs"
            :key="j.job_id"
            class="job-row"
            :class="{ selected: j.job_id === selectedId }"
            data-testid="job-row"
            @click="openLog(j.job_id)"
          >
            <td><code>{{ j.job_id }}</code></td>
            <td>{{ j.job_type }}</td>
            <td class="params-cell" :title="paramsSummary(j)">{{ paramsSummary(j) }}</td>
            <td>
              <span class="badge" :class="j.status">{{ STATUS_LABEL[j.status] ?? j.status }}</span>
            </td>
            <td class="num">{{ (j.created_at ?? '').slice(5, 19) }}</td>
            <td class="num">{{ durationOf(j) }}</td>
            <td>
              <button
                v-if="j.status === 'queued' || j.status === 'running'"
                class="cancel"
                data-testid="job-row-cancel"
                type="button"
                @click.stop="cancelJob(j.job_id)"
              >
                取消
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <!-- 首载未返回时 7 列孤表头下给 loading 占位; 空态仍要求列表已返回 -->
      <p v-if="!listData" class="t-muted empty" data-testid="jobs-loading">加载中…</p>
      <p v-else-if="jobs.length === 0" class="t-muted empty" data-testid="jobs-empty">
        暂无任务 — 在各页签提交回测/因子检验/数据刷新。
      </p>
    </div>

    <h3 class="section-title log-head">
      任务日志
      <span v-if="logLive" class="live-dot" aria-hidden="true"></span>
      <span class="t-muted log-title num" data-testid="job-log-title">{{ logTitle }}</span>
    </h3>
    <pre ref="logEl" class="job-log" data-testid="job-log">{{ logDisplay }}</pre>
  </section>
</template>

<style scoped>
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

.form-card {
  margin-bottom: var(--gap);
}

/* 两行提交按钮统一靠右收口, 消除位置漂移 */
.row-end {
  margin-left: auto;
}

/* 评估提示与按钮成组, 提示紧贴按钮左侧 */
.eval-group {
  align-items: center;
  display: flex;
  gap: 10px;
}

.eval-model-hint {
  font-size: 12.5px;
}

/* 分节标题: 承旧驾驶舱 accent 竖签(结构=信息, 标记独立分节) */
.section-title {
  align-items: center;
  display: flex;
  font-size: 14.5px;
  gap: 8px;
  margin: var(--gap-lg) 0 10px;
}

.section-title::before {
  background: var(--accent);
  border-radius: 2px;
  content: '';
  height: 13px;
  width: 3px;
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
}

td code {
  color: var(--accent-blue);
  font-size: 12px;
}

.job-row {
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
}

.job-row:hover {
  background: var(--accent-soft);
}

/* 选中行: accent 左轨, 与下方日志面板呼应 */
.job-row.selected {
  background: var(--accent-soft);
}

.job-row.selected td:first-child {
  box-shadow: inset 2px 0 0 var(--accent);
}

.params-cell {
  max-width: 380px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 状态徽章: 与 JobCard 同一配方 */
.badge {
  border-radius: 20px;
  font-family: var(--font-display);
  font-size: 11.5px;
  font-weight: 600;
  padding: 3px 10px;
  white-space: nowrap;
}

.badge.queued {
  background: var(--bg-3);
  color: var(--text-2);
}

.badge.running {
  background: var(--accent-soft);
  color: var(--accent);
}

.badge.succeeded {
  background: color-mix(in srgb, var(--c-pass) 16%, transparent);
  color: var(--c-pass);
}

.badge.failed {
  background: color-mix(in srgb, var(--c-fail) 16%, transparent);
  color: var(--c-fail);
}

.badge.canceled {
  background: var(--bg-3);
  color: var(--text-3);
}

.cancel {
  background: transparent;
  border: 1px solid var(--c-fail);
  border-radius: var(--radius-sm);
  color: var(--c-fail);
  cursor: pointer;
  font-size: 12px;
  padding: 3px 12px;
  transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
}

.cancel:hover {
  background: var(--c-fail);
  color: var(--bg);
}

.empty {
  font-size: 13px;
  padding: 12px 6px;
}

/* 日志面板: 终端质感 + 轮询呼吸灯 */
.log-head {
  margin-bottom: 8px;
}

.log-title {
  font-size: 12.5px;
  font-weight: 400;
}

.live-dot {
  animation: pulse 1.6s var(--ease-out) infinite;
  background: var(--accent);
  border-radius: 50%;
  flex: none;
  height: 8px;
  width: 8px;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.35;
    transform: scale(0.85);
  }

  50% {
    opacity: 1;
    transform: scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-dot {
    animation: none;
  }
}

.job-log {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-2);
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
  max-height: 340px;
  min-height: 56px;
  overflow: auto;
  padding: 10px 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
