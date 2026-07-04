<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { fetchJSON, postJSON } from '@/api/fetch'
import type { Job } from '@/api/types'
import { usePolling } from '@/composables/usePolling'

/* 任务卡 — 旧 jobs.js attachJobCard 语义对等:
 * 2s 轮询 tail=120; 连续 5 次失败终止并显"查询失败"; 终态停轮询移除取消钮;
 * done 仅 succeeded 触发一次。 */
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
let failCount = 0

const { data: job, stop } = usePolling<Job>(
  async () => {
    try {
      const j = await fetchJSON<Job>(`/api/jobs/${props.jobId}?tail=120`)
      failCount = 0
      return j
    } catch (e) {
      failCount += 1
      if (failCount >= 5) {
        dead.value = true
        stop()
      }
      throw e
    }
  },
  { intervalMs: 2000 },
)

watch(job, async (j) => {
  if (!j) return
  if (TERMINAL.has(j.status)) {
    stop()
    if (j.status === 'succeeded' && !doneEmitted.value) {
      doneEmitted.value = true
      emit('done')
    }
  }
  await nextTick()
  if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight // 日志跟随
})

const statusText = computed(() => {
  if (dead.value) return '查询失败'
  const s = job.value?.status
  return s ? (STATUS_LABEL[s] ?? s) : '排队中'
})

const badgeClass = computed(() => {
  if (dead.value) return 'failed'
  return job.value?.status ?? 'queued'
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
      <span class="badge" :class="badgeClass">{{ statusText }}</span>
      <span class="meta t-muted"
        >{{ job?.job_type ?? '' }}<template v-if="summary"> · {{ summary }}</template> · 耗时
        <span class="num">{{ duration }}</span></span
      >
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
    <pre ref="logEl" class="log">{{ logText }}</pre>
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

.badge {
  border-radius: 20px;
  font-family: var(--font-display);
  font-size: 11.5px;
  font-weight: 600;
  padding: 3px 10px;
  transition: background var(--dur-base) var(--ease-out), color var(--dur-base) var(--ease-out);
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
  padding: 4px 12px;
  transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
}

.cancel:hover {
  background: var(--c-fail);
  color: var(--bg);
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
</style>
