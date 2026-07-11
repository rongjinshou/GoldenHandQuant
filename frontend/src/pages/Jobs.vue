<script setup lang="ts">
import { NButton, NDatePicker, NInput, NInputNumber, NPopconfirm } from 'naive-ui'
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

import type { ApiError } from '@/api/fetch'
import { fetchJSON, postJSON } from '@/api/fetch'
import type { Job } from '@/api/types'
import AppBadge from '@/components/AppBadge.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import JobCard from '@/components/JobCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import { usePolling } from '@/composables/usePolling'
import { useJobsStore } from '@/stores/jobs'

import { STATUS_LABEL, TERMINAL_STATUS, durationOf, jobTypeLabel, paramsSummary } from './jobs/format'
import { buildEvalRequest, buildTrainRequest } from './jobs/ml-forms'
import { resultRoute } from './jobs/result-route'
import { filterLogLines, isNearBottom, jobBadgeKind } from './jobs/ui'
import StaleIndicator from './live/StaleIndicator.vue'

/* 任务中心 — 旧 jobs.js loadJobsPage/showJobLog/initMlForms 对等 + 批二硬化:
 * 列表 5s 轮询 + 活跃数写回 store; ID 单元格真 button 承载日志钻取(键盘可达 + aria-expanded);
 * 取消套 NPopconfirm + 行内乐观「取消中…」; 日志仅近底跟随, 离底显「回到最新」;
 * ML 训练/评估提交 pending 排重; JobCard 闭环(done 仅成功触发刷新 + 终态弹通知)。 */

interface JobsListResponse {
  jobs: Job[]
  active: boolean
}

const jobsStore = useJobsStore()
const error = ref('')
// 技术详情(R6-02 同 Overview 样板): 与 error 同生同灭, 经 ErrorBanner :technical title 悬停呈现
const errorTech = ref('')

function setOpError(e: unknown): void {
  error.value = (e as Error).message
  errorTech.value = (e as ApiError).technical ?? ''
}

const {
  data: listData,
  error: listError,
  isStale: listStale,
  lastSuccessAt: listLastSuccessAt,
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

/* 顶部聚合横幅(R7): error=操作错误(取消/ML 提交/前端校验), listError=列表轮询首载错误。
 * ✕ 关闭必清操作错误; listError 在首载成功前每个失败 tick 都会换新对象、常驻不散 —
 * 若只清 error, ✕ 对 listError 是死按钮 → 关闭时同置本地屏蔽标志(简单为先的取舍:
 * 屏蔽跨失败 tick 保持, 下次成功 tick listError 自愈(→null)即复位, 之后新错误照常可见)。 */
const listErrorDismissed = ref(false)
watch(listError, (e) => {
  if (e === null) listErrorDismissed.value = false
})
const bannerMsg = computed(
  () => error.value || (listErrorDismissed.value ? '' : (listError.value?.message ?? '')),
)
// technical 与 msg 同优先级取源: 正文显示哪个错误, title 就透传哪个的技术串
const bannerTech = computed(() =>
  error.value ? errorTech.value || undefined : (listError.value as ApiError | null)?.technical,
)

function closeBanner(): void {
  error.value = ''
  errorTech.value = ''
  if (listError.value) listErrorDismissed.value = true
}

// 取消: 套 NPopconfirm 二次确认 + 行内乐观「取消中…」并禁钮; 仅静默 404/409, 其余走 ErrorBanner
const cancelingIds = ref(new Set<string>())

async function cancelJob(id: string): Promise<void> {
  cancelingIds.value.add(id)
  try {
    await postJSON(`/api/jobs/${id}/cancel`)
  } catch (e) {
    const status = (e as ApiError).status
    if (status !== 404 && status !== 409) {
      setOpError(e) // 已结束(404/409)静默, 其余暴露到横幅
    }
  } finally {
    await refresh()
    cancelingIds.value.delete(id)
  }
}

// ---- 日志钻取面板(旧 showJobLog 对等) ----
const selectedId = ref<string | null>(null)
const logTitle = ref('')
const logText = ref('选择任务查看日志')
const logLive = ref(false)
const logEl = ref<HTMLPreElement | null>(null)
const logAtBottom = ref(true) // 日志是否在底部附近(离底时显「回到最新」浮钮)
// 零任务时终端框纯噪音 — 占位文案联动引导, 不藏区块保布局稳定
const logDisplay = computed(() =>
  listData.value && jobs.value.length === 0 && selectedId.value === null
    ? '暂无任务，提交后此处显示实时日志'
    : logText.value,
)
let logTimer: ReturnType<typeof setInterval> | null = null
let logSeq = 0 // 切换任务后丢弃前一任务迟到响应

// ---- 日志行过滤: 长日志(ML 训练数千行)找关键行 ----
// 面板内容是整串(log_tail join '\n') → 按行 split 交纯函数 filterLogLines;
// 全链 computed 惰性: 未过滤时不 split(直通原串), 计数行 v-if 隐藏也不触发求值。
const logFilter = ref('')
const logFilterOn = computed(() => logFilter.value !== '')
const logAllLines = computed(() => logDisplay.value.split('\n'))
const logShownLines = computed(() => filterLogLines(logAllLines.value, logFilter.value))
const logShown = computed(() =>
  logFilterOn.value ? logShownLines.value.join('\n') : logDisplay.value,
)

// 清空过滤 → 恢复全量并跟随滚底(过滤期间自动滚底暂停, 见 tick; 行集突变抢滚会跳动)
watch(logFilter, async (q) => {
  if (q !== '') return
  await nextTick()
  scrollLogToBottom()
})

function measureLogAtBottom(): boolean {
  const el = logEl.value
  return !el || isNearBottom(el.scrollHeight, el.scrollTop, el.clientHeight)
}

function onLogScroll(): void {
  logAtBottom.value = measureLogAtBottom()
}

function scrollLogToBottom(): void {
  const el = logEl.value
  if (el) el.scrollTop = el.scrollHeight
  logAtBottom.value = true
}

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
  logAtBottom.value = true // 新钻取默认贴底跟随
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
    const stick = measureLogAtBottom() // 更新内容前测量(此刻 DOM 仍为旧内容)
    logText.value = (job.log_tail ?? []).join('\n') || '（无输出）'
    if (TERMINAL_STATUS.has(job.status)) stopLogPolling()
    await nextTick()
    // 仅当用户在底部附近才跟随滚底, 否则保留其滚动位置并显「回到最新」
    // (过滤态整体暂停跟随: 行集随输入/新日志变化, 抢滚会跳动; 清空时恢复, 见 logFilter watch)
    if (stick && !logFilterOn.value) scrollLogToBottom()
    else logAtBottom.value = measureLogAtBottom()
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
// 提交 pending: :loading + 禁钮防双击排重(照 Overview 样板)
const trainSubmitting = ref(false)
const evalSubmitting = ref(false)

/* R7(R6 遗留): 日期 clearable 清空/模型名清空 → 后端 pattern 422 —
 * 必填校验前置(判定+载荷构建在 ml-forms.ts 纯函数), 不发注定失败的请求 */
async function submitTrain(): Promise<void> {
  error.value = ''
  errorTech.value = ''
  const req = buildTrainRequest({
    start: mlStart.value,
    end: mlEnd.value,
    symbols: mlSymbols.value,
    model: mlModel.value,
    trials: mlTrials.value,
  })
  if (!req.ok) {
    error.value = req.error
    return
  }
  trainSubmitting.value = true
  try {
    const job = await postJSON<Job>('/api/jobs/ml-train', req.payload)
    mlJobIds.value.unshift(job.job_id)
  } catch (e) {
    setOpError(e)
  } finally {
    trainSubmitting.value = false
  }
}

async function submitEval(): Promise<void> {
  error.value = ''
  errorTech.value = ''
  const req = buildEvalRequest(mlModel.value, mleStart.value, mleEnd.value)
  if (!req.ok) {
    error.value = req.error
    return
  }
  evalSubmitting.value = true
  try {
    const job = await postJSON<Job>('/api/jobs/ml-evaluate', req.payload)
    mlJobIds.value.unshift(job.job_id)
  } catch (e) {
    setOpError(e)
  } finally {
    evalSubmitting.value = false
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

    <ErrorBanner
      v-if="bannerMsg"
      :msg="bannerMsg"
      :technical="bannerTech"
      dismissible
      @close="closeBanner"
    />

    <details class="card form-card">
      <summary>ML 模型训练 / 评估（高级）</summary>
      <div class="form-row">
        <label>训练起 <NDatePicker v-model:formatted-value="mlStart" value-format="yyyy-MM-dd" type="date" clearable data-testid="ml-start" /></label>
        <label>训练止 <NDatePicker v-model:formatted-value="mlEnd" value-format="yyyy-MM-dd" type="date" clearable data-testid="ml-end" /></label>
        <label>标的 <NInput v-model:value="mlSymbols" style="width: 140px" data-testid="ml-symbols" /></label>
        <label><GlossaryTip term="model_name">模型名</GlossaryTip> <NInput v-model:value="mlModel" style="width: 170px" data-testid="ml-model" /></label>
        <label><GlossaryTip term="n_trials">调参次数 (n-trials)</GlossaryTip> <NInputNumber v-model:value="mlTrials" :min="1" :max="200" style="width: 100px" data-testid="ml-trials" /></label>
        <NButton type="primary" class="row-end" :loading="trainSubmitting" :disabled="trainSubmitting" data-testid="ml-train-submit" @click="submitTrain">训练</NButton>
      </div>
      <div class="form-row">
        <label>评估起 <NDatePicker v-model:formatted-value="mleStart" value-format="yyyy-MM-dd" type="date" clearable data-testid="mle-start" /></label>
        <label>评估止 <NDatePicker v-model:formatted-value="mleEnd" value-format="yyyy-MM-dd" type="date" clearable data-testid="mle-end" /></label>
        <!-- 评估静默复用首行「模型名」— 常驻小字把依赖显式化, 避免评错模型; 评估降为次级钮与训练分主次 -->
        <div class="row-end eval-group">
          <span class="t-muted eval-model-hint" data-testid="ml-eval-model">评估模型：{{ mlModel || '未填' }}</span>
          <NButton :loading="evalSubmitting" :disabled="evalSubmitting" data-testid="ml-eval-submit" @click="submitEval">评估</NButton>
        </div>
      </div>
    </details>

    <div data-testid="ml-job-area">
      <JobCard v-for="id in mlJobIds" :key="id" :job-id="id" @done="onMlDone" />
    </div>

    <div class="list-head-row">
      <h3 class="section-title">任务列表</h3>
      <!-- 列表轮询陈旧指示(R7): 复用实盘 StaleIndicator(props 通用, 无 Live 耦合) —
           常态「数据更新于 HH:mm:ss」, 断连转警示; 首载失败(从未成功)不渲染, 由横幅表达 -->
      <StaleIndicator :is-stale="listStale" :last-success-at="listLastSuccessAt" />
    </div>
    <div class="table-wrap card">
      <table data-testid="jobs-table">
        <thead>
          <tr>
            <th scope="col">ID</th>
            <th scope="col">类型</th>
            <th scope="col">参数</th>
            <th scope="col">状态</th>
            <th scope="col">创建</th>
            <th scope="col">耗时</th>
            <th scope="col">操作</th>
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
            <td>
              <!-- C1: ID 单元格真 button 承载日志钻取(键盘可达), aria-expanded 标注是否选中 -->
              <button
                type="button"
                class="id-btn"
                :aria-expanded="j.job_id === selectedId"
                aria-controls="job-log-panel"
                :aria-label="`查看任务 ${j.job_id} 日志`"
                data-testid="job-row-drill"
                @click.stop="openLog(j.job_id)"
              ><code>{{ j.job_id }}</code></button>
            </td>
            <td>{{ jobTypeLabel(j.job_type) }}</td>
            <td class="params-cell" :title="paramsSummary(j)">{{ paramsSummary(j) }}</td>
            <td>
              <AppBadge :kind="jobBadgeKind(j.status)">{{ STATUS_LABEL[j.status] ?? j.status }}</AppBadge>
            </td>
            <td class="num">{{ (j.created_at ?? '').slice(5, 19) }}</td>
            <td class="num">{{ durationOf(j) }}</td>
            <td>
              <template v-if="j.status === 'queued' || j.status === 'running'">
                <span
                  v-if="cancelingIds.has(j.job_id)"
                  class="canceling t-muted"
                  data-testid="job-row-canceling"
                >取消中…</span>
                <NPopconfirm
                  v-else
                  positive-text="确认取消"
                  negative-text="返回"
                  @positive-click="cancelJob(j.job_id)"
                >
                  <template #trigger>
                    <button
                      class="cancel"
                      data-testid="job-row-cancel"
                      type="button"
                      @click.stop
                    >
                      取消
                    </button>
                  </template>
                  <div class="confirm-body">取消任务 <code>{{ j.job_id }}</code>？</div>
                </NPopconfirm>
              </template>
              <!-- 成功且有结果页的类型(backtest/factor_test)给「查看结果」直达 —
                   落点判定抽纯函数 resultRoute; RouterLink 全局注册(同上空态链接用法),
                   .stop 防触发行 click 的日志钻取 -->
              <RouterLink
                v-else-if="resultRoute(j.job_type, j.status)"
                :to="resultRoute(j.job_type, j.status)!"
                class="result-link"
                data-testid="job-row-result"
                @click.stop
              >查看结果</RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
      <!-- 首载未返回时 7 列孤表头下给 loading 占位; 空态仍要求列表已返回 -->
      <p v-if="!listData" class="t-muted empty" data-testid="jobs-loading">加载中…</p>
      <!-- 空态入口链接化: 三个入口词直达对应页签(全局注册 RouterLink, 同 App.vue 用法 —
           不显式 import, 单测无 router 环境下降级为惰性元素不炸); 链接色承全局 a 样式 -->
      <p v-else-if="jobs.length === 0" class="t-muted empty" data-testid="jobs-empty">
        暂无任务 — 在各页签提交<RouterLink :to="{ name: 'backtests' }">回测</RouterLink>/<RouterLink :to="{ name: 'verdicts' }">因子检验</RouterLink>/<RouterLink :to="{ name: 'overview' }">数据刷新</RouterLink>。
      </p>
    </div>

    <div class="log-head-row">
      <h3 class="section-title log-head">
        任务日志
        <span v-if="logLive" class="live-dot" aria-hidden="true"></span>
        <span class="t-muted log-title num" data-testid="job-log-title">{{ logTitle }}</span>
      </h3>
      <!-- 行过滤: 非空仅显含子串行(大小写不敏感); 过滤期间暂停自动滚底, 清空恢复全量+滚底 -->
      <input
        v-model="logFilter"
        type="search"
        class="log-filter"
        placeholder="过滤日志行"
        aria-label="过滤日志行"
        data-testid="job-log-filter"
      />
    </div>
    <p v-if="logFilterOn" class="t-muted filter-count num" data-testid="job-log-filter-count">
      {{ logShownLines.length }}/{{ logAllLines.length }} 行
    </p>
    <div class="log-wrap">
      <pre ref="logEl" id="job-log-panel" class="job-log" data-testid="job-log" @scroll="onLogScroll">{{ logShown }}</pre>
      <button
        v-if="!logAtBottom"
        class="jump-latest"
        data-testid="job-log-jump"
        type="button"
        @click="scrollLogToBottom"
      >
        ↓ 回到最新
      </button>
    </div>
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

/* 任务列表标题行(R7): 陈旧指示贴标题右侧同基线;
 * 指示器自带负上距为实盘页头场景设计, 此处 :deep 归零, 行距由本行统一承担 */
.list-head-row {
  align-items: baseline;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: var(--gap-lg) 0 10px;
}

.list-head-row > .section-title {
  margin: 0;
}

.list-head-row :deep(.conn-line) {
  margin: 0;
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

/* ID 钻取钮: 呈现为纯文本(承载键盘可达 + aria), 去按钮默认外观 */
.id-btn {
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: inherit; /* button UA 不继承 color(R5 教训) */
  cursor: pointer;
  font: inherit;
  padding: 0;
  text-align: left;
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

.cancel {
  background: transparent;
  border: 1px solid var(--c-fail);
  border-radius: var(--radius-sm);
  color: var(--c-fail);
  cursor: pointer;
  font-size: 12px;
  min-height: 24px;
  padding: 3px 12px;
  transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
}

.cancel:hover {
  background: var(--c-fail);
  color: var(--bg);
}

.canceling {
  font-size: 12px;
}

/* 「查看结果」链接: 色承全局 a(accent-strong), 只收字号与断行 */
.result-link {
  font-size: var(--fs-xs);
  white-space: nowrap;
}

/* NPopconfirm 默认插槽是 flex 布局 — 显式约束宽度 */
.confirm-body {
  max-width: 240px;
}

.empty {
  font-size: 13px;
  padding: 12px 6px;
}

/* F-06: 空态段内链接与正文几乎同亮度(实算 1.04~1.06:1), 色彩不足以当区分手段 —
   补常显下划线(WCAG 1.4.1 非色彩区分最稳解) */
.empty a {
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* 日志面板: 终端质感 + 轮询呼吸灯 */
.log-head {
  margin-bottom: 8px;
}

/* 标题行 + 右缘过滤框成一行(输入框不放 h3 内, 免污染标题可及名) */
.log-head-row {
  align-items: center;
  display: flex;
  gap: 12px;
  margin: var(--gap-lg) 0 8px;
}

.log-head-row .log-head {
  flex: 1;
  margin: 0;
  min-width: 0;
}

/* 过滤框: 轻量原生 input(不引 NInput 重主题), 终端配色对齐日志面板 */
.log-filter {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-2);
  flex: none;
  font: inherit;
  font-size: var(--fs-xs);
  padding: 4px 9px;
  width: 180px;
}

.log-filter::placeholder {
  color: var(--text-3);
}

/* R6-06: border 变色保留; 不再 outline:none 吞焦点环 — 键盘/文本输入聚焦时
 * base.css 全局 :focus-visible 环(2px accent, offset 2px)照常生效 */
.log-filter:focus {
  border-color: var(--accent);
}

/* 过滤命中统计: 右对齐贴过滤框正下方 */
.filter-count {
  font-size: var(--fs-xs);
  margin: 0 0 6px;
  text-align: right;
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

.log-wrap {
  position: relative;
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

/* 离底时浮于日志右下: 一键回到最新(不再无条件抢滚动条) */
.jump-latest {
  background: var(--accent);
  border: none;
  border-radius: 14px;
  bottom: 12px;
  color: var(--text-on-accent);
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 11.5px;
  padding: 5px 14px;
  position: absolute;
  right: 16px;
  box-shadow: var(--shadow-sm, 0 2px 8px rgba(0, 0, 0, 0.25));
}
</style>
