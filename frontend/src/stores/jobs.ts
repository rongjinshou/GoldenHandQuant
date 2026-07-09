import { defineStore } from 'pinia'
import { ref } from 'vue'

import { fetchJSON } from '@/api/fetch'
import type { Job, JobStatus } from '@/api/types'
import { usePolling, type UsePollingReturn } from '@/composables/usePolling'

/* 活跃任务计数 — 旧版 window.__activeJobs 的正经化(设计 §4.1 / §10)。
 * 顶栏「任务」徽章与 fetch 层 503 写锁文案共用它, 必须始终鲜活。
 *
 * 两个写入源:
 *  1) 任务页自身 5s 轮询 → setActive()(维护完整列表, 顺带回填计数)
 *  2) App 级全局轮询(startGlobalPolling)→ 别页也让徽章鲜活(修"别页提交徽章永不亮")
 * 去重: 全局轮询发现某页最近已 setActive(回填)则跳过自身请求, 避免双拉风暴。 */

interface JobsListResponse {
  jobs: Job[]
  active: boolean
}

/** 活跃 = 排队中 + 运行中(纯函数, 便于单测)。 */
export function activeJobCount(jobs: readonly { status: JobStatus }[]): number {
  return jobs.reduce((n, j) => n + (j.status === 'queued' || j.status === 'running' ? 1 : 0), 0)
}

export const useJobsStore = defineStore('jobs', () => {
  const activeCount = ref(0)
  let lastExternalUpdate = 0 // 页面级 poller 最近一次 setActive 回填的时刻
  let poll: UsePollingReturn<JobsListResponse | null> | null = null

  function setActive(n: number): void {
    activeCount.value = n
    lastExternalUpdate = Date.now() // 标记"有页面正在维护计数"
  }

  function startGlobalPolling(intervalMs = 5000): void {
    if (poll) return // 幂等: 全局仅一个
    const dedupWindow = intervalMs + 2000 // 略大于一个页面轮询周期, 页面在轮询时全局恒跳过
    poll = usePolling<JobsListResponse | null>(
      async (signal) => {
        // 某页(如任务页)正高频回填 → 跳过自身请求, 避免对 /api/jobs 双拉
        if (Date.now() - lastExternalUpdate < dedupWindow) return null
        const d = await fetchJSON<JobsListResponse>('/api/jobs?limit=100', signal)
        activeCount.value = activeJobCount(d.jobs)
        return d
      },
      // 徽章后台轮询: /api/jobs 连挂时退避降载, 恢复即复位
      { intervalMs, immediate: true, backoff: true },
    )
  }

  function stopGlobalPolling(): void {
    poll?.stop()
    poll = null
  }

  return { activeCount, setActive, startGlobalPolling, stopGlobalPolling }
})
