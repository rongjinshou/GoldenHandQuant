<script setup lang="ts">
import { useNotification } from 'naive-ui'
import { computed, nextTick, onUnmounted, ref, shallowRef, watch } from 'vue'

import { fetchJSON, postJSON } from '@/api/fetch'
import type { Job } from '@/api/types'
import AppBadge from '@/components/AppBadge.vue'
import { usePolling, type UsePollingReturn } from '@/composables/usePolling'
import { type BadgeKind, isNearBottom, jobBadgeKind, terminalNotification } from '@/pages/jobs/ui'

/* 任务卡 — 旧 jobs.js attachJobCard 语义对等 + 批二硬化:
 * 2s 轮询 tail=120; 连续 5 次失败终止并显"查询失败"(可「重试」重启轮询);
 * 终态停轮询移除取消钮; done 仅 succeeded 触发一次; 终态弹 useNotification 通知;
 * 日志仅在近底时跟随滚底, 离底显「↓ 回到最新」。 */
const props = defineProps<{ jobId: string }>()
const emit = defineEmits<{ done: []; canceled: [] }>()

const STATUS_LABEL: Record<string, string> = {
  queued: '排队中',
  running: '运行中',
  succeeded: '已完成',
  failed: '失败',
  canceled: '已取消',
}

const TERMINAL = new Set(['succeeded', 'failed', 'canceled'])

const dead = ref(false) // 连续失败终止态
const doneEmitted = ref(false)
const logEl = ref<HTMLPreElement | null>(null)
const logAtBottom = ref(true) // 日志是否在底部附近(离底时显「回到最新」浮钮)
let failCount = 0
let notified = false

// 无 NNotificationProvider(如单测直接挂载)时优雅降级为 no-op, 不阻断组件渲染
const notification = (() => {
  try {
    return useNotification()
  } catch {
    return null
  }
})()

// usePolling 的 stop() 是终态语义(stopped 永久置位, refresh 结果被丢弃) → 重试需重建实例。
// shallowRef 持有当前轮询, retry 停旧建新; 首个实例在 setup 作用域内自动随卸载停止,
// 重试(在事件处理器/setup 作用域外)建的实例由 onUnmounted 兜底停止。
const poller = shallowRef<UsePollingReturn<Job> | null>(null)
const job = computed(() => poller.value?.data.value ?? null)

async function fetcher(): Promise<Job> {
  try {
    const j = await fetchJSON<Job>(`/api/jobs/${props.jobId}?tail=120`)
    failCount = 0
    return j
  } catch (e) {
    failCount += 1
    if (failCount >= 5) {
      dead.value = true
      poller.value?.stop()
    }
    throw e
  }
}

function startPolling(): void {
  poller.value?.stop()
  failCount = 0
  dead.value = false
  poller.value = usePolling<Job>(fetcher, { intervalMs: 2000 })
}

startPolling()
onUnmounted(() => poller.value?.stop())

function retry(): void {
  notified = false
  startPolling()
}

/* paramsSummary 对等旧版拼装规则 */
const summary = computed(() => {
  const p = (job.value?.params ?? {}) as Record<string, unknown>
  const parts: string[] = []
  if (Array.isArray(p.strategies)) parts.push((p.strategies as string[]).join(','))
  if (p.factors) parts.push(String(p.factors))
  if (p.model_name) parts.push(String(p.model_name))
  if (p.symbols) {
    const arr = Array.isArray(p.symbols) ? (p.symbols as string[]) : String(p.symbols).split(',')
    parts.push(arr.length <= 2 ? arr.join(',') : `${arr.slice(0, 2).join(',')}等${arr.length}只`)
  }
  if (p.start_date) parts.push(`${p.start_date}~${p.end_date ?? ''}`)
  if (p.objective) parts.push(String(p.objective))
  return parts.join(' · ').slice(0, 90)
})

function measureAtBottom(): boolean {
  const el = logEl.value
  return !el || isNearBottom(el.scrollHeight, el.scrollTop, el.clientHeight)
}

function onLogScroll(): void {
  logAtBottom.value = measureAtBottom()
}

function scrollToBottom(): void {
  const el = logEl.value
  if (el) el.scrollTop = el.scrollHeight
  logAtBottom.value = true
}

// 终态非阻塞通知(succeeded/failed) + 给标签页标题加「✓」前缀(下次路由切换由 Wave1 afterEach 重置)
function maybeNotify(status: string): void {
  if (notified) return
  const n = terminalNotification(status)
  if (!n) return
  notified = true
  notification?.[n.type]({
    title: n.title,
    content: summary.value || job.value?.job_type || props.jobId,
    duration: 5000,
  })
  if (!document.title.startsWith('✓')) document.title = `✓ ${document.title}`
}

watch(job, async (j) => {
  const stick = measureAtBottom() // 更新内容前测量(此刻 DOM 仍为旧内容)
  if (j && TERMINAL.has(j.status)) {
    poller.value?.stop()
    maybeNotify(j.status)
    if (j.status === 'succeeded' && !doneEmitted.value) {
      doneEmitted.value = true
      emit('done')
    }
  }
  await nextTick()
  if (stick) scrollToBottom()
  else logAtBottom.value = measureAtBottom()
})

const statusText = computed(() => {
  if (dead.value) return '查询失败'
  const s = job.value?.status
  return s ? (STATUS_LABEL[s] ?? s) : '排队中'
})

const badgeKind = computed<BadgeKind>(() => {
  if (dead.value) return 'fail'
  return jobBadgeKind(job.value?.status ?? 'queued')
})

const isActive = computed(
  () => !dead.value && !!job.value && !TERMINAL.has(job.value.status),
)

/* durationOf 对等旧版: sec<90 → "Xs", 否则 "X.Xmin" */
const duration = computed(() => {
  const j = job.value
  if (!j?.started_at) return '-'
  const end = j.finished_at ? new Date(j.finished_at) : new Date()
  const sec = Math.max(0, (end.getTime() - new Date(j.started_at).getTime()) / 1000)
  return sec < 90 ? `${sec.toFixed(0)}s` : `${(sec / 60).toFixed(1)}min`
})

const logText = computed(() => {
  if (dead.value) return '查询失败（服务可能已重启）'
  const tail = job.value?.log_tail
  return tail?.length ? tail.join('\n') : '等待日志…'
})

async function cancel(): Promise<void> {
  try {
    await postJSON(`/api/jobs/${props.jobId}/cancel`)
    emit('canceled')
  } catch {
    /* 已结束(409/404) — 对等旧版静默 */
  }
}
</script>

<template>
  <div class="job-card card" data-testid="job-card">
    <div class="head">
      <AppBadge :kind="badgeKind" size="sm" data-testid="job-card-badge">{{ statusText }}</AppBadge>
      <span class="meta t-muted"
        >{{ job?.job_type ?? '' }}<template v-if="summary"> · {{ summary }}</template> · 耗时
        <span class="num">{{ duration }}</span></span
      >
      <button
        v-if="dead"
        class="retry"
        data-testid="job-retry"
        type="button"
        @click="retry"
      >
        重试
      </button>
      <button
        v-if="isActive"
        class="cancel"
        data-testid="job-cancel"
        type="button"
        @click="cancel"
      >
        取消
      </button>
    </div>
    <div class="log-wrap">
      <pre ref="logEl" class="log" @scroll="onLogScroll">{{ logText }}</pre>
      <button
        v-if="!logAtBottom"
        class="jump-latest"
        data-testid="job-card-jump"
        type="button"
        @click="scrollToBottom"
      >
        ↓ 回到最新
      </button>
    </div>
  </div>
</template>

<style scoped>
.job-card {
  margin-bottom: var(--gap);
  padding: 12px 14px;
}

.head {
  align-items: center;
  display: flex;
  gap: 10px;
}

.meta {
  flex: 1;
  font-size: 12.5px;
  min-width: 0;
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
  padding: 4px 12px;
  transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
}

.cancel:hover {
  background: var(--c-fail);
  color: var(--bg);
}

.retry {
  background: var(--accent);
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  color: var(--text-on-accent);
  cursor: pointer;
  font-size: 12px;
  min-height: 24px;
  padding: 4px 12px;
  transition: opacity var(--dur-fast) var(--ease-out);
}

.retry:hover {
  opacity: 0.88;
}

.log-wrap {
  position: relative;
}

.log {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 12px;
  line-height: 1.5;
  margin: 10px 0 0;
  max-height: 220px;
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
  bottom: 10px;
  color: var(--text-on-accent);
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 11.5px;
  padding: 4px 12px;
  position: absolute;
  right: 12px;
  box-shadow: var(--shadow-sm, 0 2px 8px rgba(0, 0, 0, 0.25));
}
</style>
